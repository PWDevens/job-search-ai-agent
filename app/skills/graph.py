"""
Tier-2: the ESCO occupation/skill graph.

Loads two kinds of edges:
  occupation -> skill   (essential | optional)   — "what does this role require?"
  skill -> skill        (essential | optional)   — adjacency, for retrieval expansion

Preferred source: a single pre-joined edge list `esco_relations.csv`
  (relationKind, relationType, sourceUri/Label/Type, targetUri/Label/Type)
plus `occupations_en.csv` for occupation altLabels (needed for title matching).
Falls back to the 3-file layout (occupationSkillRelations + skills_en) if the
relations file isn't present. Everything degrades to [] if nothing is built.

Build: python -m app.skills.graph
"""
import csv
import logging
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from app.config import SKILLS_DB_PATH

logger = logging.getLogger(__name__)

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "skills"
_CANDIDATE_DIRS = [_DATA / "raw", _DATA / "_esco_extract"]

# generic tokens that shouldn't drive occupation title matching
_STOP = {"and", "the", "of", "for", "a", "an", "in", "to", "senior", "junior",
         "lead", "manager", "specialist", "officer", "assistant", "worker"}


def _find(name: str) -> Path | None:
    for c in _CANDIDATE_DIRS:
        if (c / name).exists():
            return c / name
    return None


def build_graph(esco_dir=None) -> int:
    """(Re)build the occupation/skill graph in the skills DB. Returns #occupations linked."""
    occ_name, occ_aliases = {}, []   # uri->name ; (alias, uri)
    occ_file = (Path(esco_dir) / "occupations_en.csv") if esco_dir else _find("occupations_en.csv")
    if occ_file and occ_file.exists():
        with open(occ_file, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                uri = r["conceptUri"]
                occ_name[uri] = r["preferredLabel"]
                for lbl in [r["preferredLabel"], *r.get("altLabels", "").split("\n")]:
                    a = lbl.strip().lower()
                    if a:
                        occ_aliases.append((a, uri))

    occ_links = []   # (occ_uri, skill_name, relation)
    skill_rel = []   # (src_name_lc, tgt_name)
    rel = _find("esco_relations.csv")
    if rel:
        with open(rel, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                kind = r["relationKind"]
                if kind == "occupation-skill" and r["targetLabel"]:
                    occ_links.append((r["sourceUri"], r["targetLabel"], r["relationType"]))
                elif kind == "skill-skill":
                    s, t = r["sourceLabel"].strip().lower(), r["targetLabel"].strip()
                    if s and t:
                        skill_rel.append((s, t))
    else:
        # fallback: occupationSkillRelations + skills_en (no skill-skill edges)
        rels = _find("occupationSkillRelations_en.csv")
        sk = _find("skills_en.csv")
        if rels and sk:
            skn = {r["conceptUri"]: r["preferredLabel"]
                   for r in csv.DictReader(open(sk, encoding="utf-8-sig"))}
            for r in csv.DictReader(open(rels, encoding="utf-8-sig")):
                name = skn.get(r["skillUri"])
                if name:
                    occ_links.append((r["occupationUri"], name, r["relationType"]))

    if not occ_links and not occ_aliases:
        logger.warning("No ESCO graph sources found; graph not built.")
        return 0

    con = sqlite3.connect(SKILLS_DB_PATH)
    try:
        con.executescript("""
            DROP TABLE IF EXISTS occupations;
            DROP TABLE IF EXISTS occupation_aliases;
            DROP TABLE IF EXISTS occupation_skills;
            DROP TABLE IF EXISTS skill_relations;
            CREATE TABLE occupations (occ_id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE occupation_aliases (alias TEXT, occ_id TEXT);
            CREATE TABLE occupation_skills (occ_id TEXT, skill_name TEXT, relation TEXT);
            CREATE TABLE skill_relations (src_lc TEXT, tgt TEXT);
            CREATE INDEX idx_occ_alias ON occupation_aliases(alias);
            CREATE INDEX idx_occ_skill ON occupation_skills(occ_id);
            CREATE INDEX idx_skill_rel ON skill_relations(src_lc);
        """)
        con.executemany("INSERT OR REPLACE INTO occupations VALUES (?,?)", occ_name.items())
        con.executemany("INSERT INTO occupation_aliases VALUES (?,?)", occ_aliases)
        con.executemany("INSERT INTO occupation_skills VALUES (?,?,?)", occ_links)
        con.executemany("INSERT INTO skill_relations VALUES (?,?)", skill_rel)
        con.commit()
    finally:
        con.close()
    n = len({l[0] for l in occ_links})
    logger.info("Built graph: %d occupations, %d occ-skill links, %d skill-skill edges",
                n, len(occ_links), len(skill_rel))
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
    text (containment, not Jaccard — a verbose query must still match a short
    occupation name). Score rewards covering more specific tokens.
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
        coverage = len(covered) / len(atoks)
        if coverage < 0.6:
            continue
        score = len(covered) * coverage
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


def adjacent_skills(skill_names, n: int = 20) -> list[str]:
    """Skills related (skill->skill edges) to any of `skill_names`. [] if unavailable."""
    names = [s.strip().lower() for s in skill_names if s and s.strip()]
    if not names:
        return []
    try:
        con = sqlite3.connect(SKILLS_DB_PATH)
        try:
            ph = ",".join("?" * len(names))
            rows = con.execute(f"SELECT DISTINCT tgt FROM skill_relations WHERE src_lc IN ({ph})",
                               names).fetchall()
        finally:
            con.close()
    except sqlite3.OperationalError:
        return []
    seen = set(names)
    return [r[0] for r in rows if r[0].lower() not in seen][:n]


def role_skill_context(role: str, n_essential: int = 10, n_adjacent: int = 8):
    """(essential_skills, adjacent_skills) for a role — the graph context for an agent."""
    ess = essential_skills_for(role, n=n_essential)
    adj = adjacent_skills(ess, n=n_adjacent) if ess else []
    return ess, adj


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = build_graph()
    print(f"Built graph for {n} occupations into {SKILLS_DB_PATH}")
