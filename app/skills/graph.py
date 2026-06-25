"""
Tier-2: the ESCO occupation -> skill graph.

skills_en.csv alone is a flat vocabulary; the relationship files turn it into a
graph. This loads occupation -> essential/optional skill links so we can answer
"what skills does this occupation require?" — field-accurate, curated priors that
seed persona targets, give the career-strategist a real candidate pool, and let
the rubric check whether a blind spot is essential for the target role.

Source files (from an extracted ESCO classification zip):
  occupations_en.csv             occupation title + altLabels -> URI
  occupationSkillRelations_en.csv occupation URI -> skill URI (essential|optional)
  skills_en.csv                  skill URI -> preferred name

Build: python -m app.skills.graph [esco_dir]   (defaults to data/skills/raw/ then _esco_extract/)
Everything degrades to [] if the graph isn't built — no hard dependency.
"""
import csv
import logging
import re
import sqlite3
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.config import SKILLS_DB_PATH

logger = logging.getLogger(__name__)

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "skills"
_CANDIDATE_DIRS = [_DATA / "raw", _DATA / "_esco_extract"]

# generic tokens that shouldn't drive occupation title matching
_STOP = {"and", "the", "of", "for", "a", "an", "in", "to", "senior", "junior",
         "lead", "manager", "specialist", "officer", "assistant", "worker"}


def _esco_dir(d=None) -> Path | None:
    if d:
        return Path(d)
    for c in _CANDIDATE_DIRS:
        if (c / "occupationSkillRelations_en.csv").exists():
            return c
    return None


def build_graph(esco_dir=None) -> int:
    """Load occupation -> skill links into the skills DB. Returns #occupations with skills."""
    d = _esco_dir(esco_dir)
    if not d:
        logger.warning("No ESCO occupation files found; graph not built.")
        return 0

    skn = {}  # skill URI -> name
    with open(d / "skills_en.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            skn[r["conceptUri"]] = r["preferredLabel"]

    occ_name, occ_aliases = {}, []      # URI -> name ; (alias, URI)
    with open(d / "occupations_en.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            uri = r["conceptUri"]
            occ_name[uri] = r["preferredLabel"]
            labels = [r["preferredLabel"], *r.get("altLabels", "").split("\n")]
            for lbl in labels:
                a = lbl.strip().lower()
                if a:
                    occ_aliases.append((a, uri))

    links = []  # (occ_uri, skill_name, relation)
    with open(d / "occupationSkillRelations_en.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            name = skn.get(r["skillUri"])
            if name:
                links.append((r["occupationUri"], name, r["relationType"]))

    con = sqlite3.connect(SKILLS_DB_PATH)
    try:
        con.executescript("""
            DROP TABLE IF EXISTS occupations;
            DROP TABLE IF EXISTS occupation_aliases;
            DROP TABLE IF EXISTS occupation_skills;
            CREATE TABLE occupations (occ_id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE occupation_aliases (alias TEXT, occ_id TEXT);
            CREATE TABLE occupation_skills (occ_id TEXT, skill_name TEXT, relation TEXT);
            CREATE INDEX idx_occ_alias ON occupation_aliases(alias);
            CREATE INDEX idx_occ_skill ON occupation_skills(occ_id);
        """)
        con.executemany("INSERT OR REPLACE INTO occupations VALUES (?,?)", occ_name.items())
        con.executemany("INSERT INTO occupation_aliases VALUES (?,?)", occ_aliases)
        con.executemany("INSERT INTO occupation_skills VALUES (?,?,?)", links)
        con.commit()
    finally:
        con.close()
    n = len({l[0] for l in links})
    logger.info("Built occupation graph: %d occupations, %d skill links", n, len(links))
    return n


@lru_cache(maxsize=1)
def _occ_alias_map() -> dict:
    try:
        con = sqlite3.connect(SKILLS_DB_PATH)
        try:
            rows = con.execute("SELECT alias, occ_id FROM occupation_aliases").fetchall()
        finally:
            con.close()
        return {a: o for a, o in rows}
    except sqlite3.OperationalError:
        return {}


def match_occupation(title: str) -> str | None:
    """Map a job title / role description to an ESCO occupation URI.

    Exact alias first; else the occupation whose NAME is best *contained* in the
    text. Containment (covered / alias-size), not Jaccard — a verbose query like
    "Registered nurse with ICU experience seeking charge nurse role" must still
    match the short occupation "registered nurse" (Jaccard would dilute it to ~0).
    Score rewards covering more specific tokens so "registered nurse" beats "nurse".
    """
    if not title:
        return None
    amap = _occ_alias_map()
    if not amap:
        return None
    low = title.strip().lower()
    if low in amap:
        return amap[low]
    qtoks = {t for t in re.split(r"[^a-z0-9]+", low) if t not in _STOP and len(t) > 2}
    if not qtoks:
        return None
    best, best_score = None, 0.0
    for alias, occ in amap.items():            # ponytail: linear scan; index if this gets hot
        atoks = {t for t in alias.split() if t not in _STOP and len(t) > 2}
        if not atoks:
            continue
        covered = qtoks & atoks
        coverage = len(covered) / len(atoks)   # fraction of the occupation name present
        if coverage < 0.6:
            continue
        score = len(covered) * coverage        # prefer fully-covered, more specific names
        if score > best_score:
            best, best_score = occ, score
    return best


def essential_skills_for(title: str, n: int = 15) -> list[str]:
    """Essential ESCO skills for the occupation best matching `title`. [] if unavailable."""
    occ = match_occupation(title)
    if not occ:
        return []
    try:
        con = sqlite3.connect(SKILLS_DB_PATH)
        try:
            rows = con.execute(
                "SELECT skill_name FROM occupation_skills WHERE occ_id=? AND relation='essential'",
                (occ,)).fetchall()
        finally:
            con.close()
    except sqlite3.OperationalError:
        return []
    return [r[0] for r in rows][:n]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = build_graph()
    print(f"Built occupation graph for {n} occupations into {SKILLS_DB_PATH}")
