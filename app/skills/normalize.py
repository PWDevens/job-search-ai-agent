"""
Normalize free text to canonical skill IDs.

Two entry points:
- extract_skill_ids(text): which skills does this job/résumé mention? (ingest)
- normalize_one(skill):    map one skill phrase to its canonical id. (rubric grounding)

Strategy: cheap exact alias match on token boundaries first, then an embedding
nearest-neighbor fallback for paraphrases ("lead the nursing unit" -> Charge Nurse)
gated by SKILL_MATCH_FLOOR. Everything degrades gracefully if the skills store
hasn't been built (returns [] / None) so callers never hard-fail.
"""
import logging
import re
import sqlite3
from functools import lru_cache

from app.config import SKILLS_DB_PATH, CHROMA_SKILLS_COL, SKILL_MATCH_FLOOR

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _alias_map() -> dict:
    """alias(lower) -> skill_id. Cached. Empty dict if the DB isn't built yet."""
    try:
        con = sqlite3.connect(SKILLS_DB_PATH)
        try:
            rows = con.execute("SELECT alias, skill_id FROM skill_aliases").fetchall()
        finally:
            con.close()
        return {a: sid for a, sid in rows}
    except sqlite3.OperationalError:
        return {}  # table/db missing — skills layer not built


@lru_cache(maxsize=1)
def _meta_map() -> dict:
    """skill_id -> {name, type}. Cached."""
    try:
        con = sqlite3.connect(SKILLS_DB_PATH)
        try:
            rows = con.execute("SELECT skill_id, name, type FROM skills").fetchall()
        finally:
            con.close()
        return {sid: {"name": n, "type": t} for sid, n, t in rows}
    except sqlite3.OperationalError:
        return {}


def _boundary_hit(alias: str, text: str) -> bool:
    """True if alias appears in text on token boundaries (so 'r' won't hit inside 'word')."""
    return re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text) is not None


def _semantic(query: str, n: int):
    """Return [(skill_id, score)] from the embedding collection, score = 1 - cosine_dist."""
    try:
        from app.retrieval.client import query_collection
        res = query_collection(CHROMA_SKILLS_COL, [query], n_results=n)
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        return [(sid, round(1 - d, 4)) for sid, d in zip(ids, dists)]
    except Exception as e:  # collection missing / chroma unavailable
        logger.debug("skill semantic lookup unavailable: %s", e)
        return []


def extract_skill_ids(text: str, max_skills: int = 30, semantic: bool = False) -> list[dict]:
    """Skills mentioned in `text` -> [{skill_id, name, type, match, score}].

    Exact token-boundary alias matching only, by default. The whole-text embedding
    pass is OFF for extraction: querying a long job description against a large
    taxonomy (e.g. ESCO's ~14k skills) surfaces spurious near-neighbours
    ("electricity principles", "morality" on a nursing post). Semantic matching
    stays where it's precise — normalize_one() on a single short skill phrase.
    """
    if not text:
        return []
    low = text.lower()
    amap = _alias_map()
    mmap = _meta_map()
    found: dict[str, dict] = {}

    # Exact pass — token-boundary alias match.
    # ponytail: O(aliases) substring scan; fine for ingest-time + sample/ESCO sizes.
    # For a 100k-alias taxonomy, swap in an Aho-Corasick automaton.
    for alias, sid in amap.items():
        if sid in found:
            continue
        if _boundary_hit(alias, low):
            m = mmap.get(sid, {})
            found[sid] = {"skill_id": sid, "name": m.get("name", sid),
                          "type": m.get("type"), "match": "exact", "score": 1.0}

    if semantic and amap:  # opt-in only; noisy on large taxonomies (see docstring)
        for sid, score in _semantic(text, n=max_skills):
            if sid in found or score < SKILL_MATCH_FLOOR:
                continue
            m = mmap.get(sid, {})
            found[sid] = {"skill_id": sid, "name": m.get("name", sid),
                          "type": m.get("type"), "match": "semantic", "score": score}

    out = sorted(found.values(), key=lambda d: -d["score"])
    return out[:max_skills]


def normalize_one(skill: str) -> str | None:
    """Map one skill phrase to its canonical skill_id (exact alias -> semantic -> None)."""
    if not skill or not skill.strip():
        return None
    low = skill.strip().lower()
    amap = _alias_map()
    if not amap:
        return None
    if low in amap:                      # direct alias hit (incl. synonyms)
        return amap[low]
    for alias, sid in amap.items():      # alias appears within the phrase
        if _boundary_hit(alias, low):
            return sid
    # Embedding fallback — precision-first. Require the top hit to clear the floor AND
    # beat the runner-up by a margin; otherwise return None (the rubric then falls back
    # to substring, which is safer than a wrong canonical mapping). The margin rejects
    # generic-soft-skill ambiguity, e.g. "lead the nursing unit" -> Leadership 0.72 vs
    # Charge Nurse 0.69 (margin 0.03), where the embedding favors the generic "lead".
    hits = _semantic(skill, n=2)
    if hits and hits[0][1] >= SKILL_MATCH_FLOOR:
        margin = hits[0][1] - (hits[1][1] if len(hits) > 1 else 0.0)
        if margin >= 0.04:
            return hits[0][0]
    return None
