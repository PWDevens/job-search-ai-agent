"""
Build the skills taxonomy store: a SQLite skills/alias DB + a ChromaDB embedding
collection, from a source-agnostic skills file.

Sources supported (auto-detected by header): Lightcast Open Skills, ESCO, O*NET,
or the committed sample CSV. Drop a raw taxonomy in data/skills/raw/ and run:

    python -m app.skills.loader [path]

With no path (and no raw file) it falls back to data/skills/sample_skills.csv so a
fresh checkout builds offline with zero download.

# skills: one flat schema for every source — Tier-1 deliberately ignores the
# occupation/relationship graph (that's Tier 2).
"""
import csv
import logging
import sqlite3
from pathlib import Path

from app.config import SKILLS_DB_PATH, CHROMA_SKILLS_COL
from app.retrieval.client import upsert_documents, delete_collection

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "skills"
SAMPLE = _DATA_DIR / "sample_skills.csv"
RAW_DIR = _DATA_DIR / "raw"


def detect_source(header: list[str]) -> str:
    """Sniff the source from CSV header columns."""
    cols = {c.strip().lower() for c in header}
    if {"skill_id", "name", "aliases"} <= cols:
        return "sample"
    if "concepturi" in cols or "preferredlabel" in cols:
        return "esco"
    if "elementid" in cols or "element id" in cols or "element name" in cols:
        return "onet"
    if "id" in cols and "name" in cols and ("type" in cols or "category" in cols):
        return "lightcast"
    return "sample"  # safest default — assumes our own schema


# Generic job-prose words that are NOT skills but appear as short ESCO aliases
# (e.g. "CALL" -> Computer Assisted Language Learning matching "call" in a nursing post).
# Kept deliberately small to avoid dropping real single-word skills (leadership, python, sql).
_GENERIC_ALIASES = {
    "call", "work", "staff", "team", "help", "care", "plan", "role", "time", "area",
    "level", "group", "order", "value", "system", "process", "service", "report",
    "review", "run", "need", "make", "set", "meet", "follow", "support", "use", "user",
    "task", "unit", "field", "type", "part", "site", "case", "data", "test", "lead",
}


def _usable_alias(a: str) -> bool:
    """Keep multi-word aliases (specific enough); drop single tokens that are <=2 chars
    or a generic non-skill word — those cause exact-match false positives."""
    if " " in a:
        return True
    return len(a) > 2 and a not in _GENERIC_ALIASES


def _split(val: str, seps=("|", "\n", ";")) -> list[str]:
    """Split a multi-value cell on any of the common separators."""
    out = [val]
    for s in seps:
        out = [p for chunk in out for p in chunk.split(s)]
    return [p.strip() for p in out if p.strip()]


def load_rows(path: Path) -> list[dict]:
    """Parse a source file into {skill_id, name, type, source, aliases} rows."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        source = detect_source(header)
        # lower-case key map for tolerant access
        rows = []
        for raw in reader:
            r = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
            if source == "sample":
                sid, name = r.get("skill_id", "").strip(), r.get("name", "").strip()
                aliases = _split(r.get("aliases", ""))
                typ = r.get("type", "") or None
            elif source == "esco":
                sid = r.get("concepturi", "").strip()
                name = r.get("preferredlabel", "").strip()
                aliases = _split(r.get("altlabels", ""))
                typ = r.get("skilltype", "") or None
            elif source == "onet":
                sid = (r.get("elementid") or r.get("element id", "")).strip()
                name = (r.get("elementname") or r.get("element name", "")).strip()
                aliases = []
                typ = "hard"
            else:  # lightcast
                sid = r.get("id", "").strip()
                name = r.get("name", "").strip()
                aliases = _split(r.get("synonyms", "") or r.get("aliases", ""))
                typ = (r.get("type", "") or r.get("category", "")) or None
            if not name:
                continue
            if not sid:
                sid = "sk_" + name.lower().replace(" ", "_")
            # canonical name is always an alias too; filter generic/short single-word
            # aliases that cause exact-match false positives.
            alias_set = {a for a in {name.lower(), *(a.lower() for a in aliases)}
                         if _usable_alias(a)}
            rows.append({"skill_id": sid, "name": name, "type": typ,
                         "source": source, "aliases": sorted(alias_set)})
    return rows


def _pick_source_file(path) -> Path:
    if path:
        return Path(path)
    if RAW_DIR.is_dir():
        for f in sorted(RAW_DIR.glob("*.csv")):
            return f
    return SAMPLE


def build(path=None) -> int:
    """(Re)build the SQLite skills DB + the Chroma skills collection. Returns count."""
    src = _pick_source_file(path)
    rows = load_rows(src)

    Path(SKILLS_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(SKILLS_DB_PATH)
    try:
        con.executescript("""
            DROP TABLE IF EXISTS skills;
            DROP TABLE IF EXISTS skill_aliases;
            CREATE TABLE skills (skill_id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT, source TEXT);
            CREATE TABLE skill_aliases (alias TEXT NOT NULL, skill_id TEXT NOT NULL);
            CREATE INDEX idx_alias ON skill_aliases(alias);
        """)
        con.executemany("INSERT OR REPLACE INTO skills VALUES (?,?,?,?)",
                        [(r["skill_id"], r["name"], r["type"], r["source"]) for r in rows])
        con.executemany("INSERT INTO skill_aliases VALUES (?,?)",
                        [(a, r["skill_id"]) for r in rows for a in r["aliases"]])
        con.commit()
    finally:
        con.close()

    # Embed canonical names for the semantic-fallback match.
    delete_collection(CHROMA_SKILLS_COL)
    ids   = [r["skill_id"] for r in rows]
    docs  = [r["name"] for r in rows]
    metas = [{"name": r["name"], "type": r["type"] or ""} for r in rows]
    BATCH = 5000  # ChromaDB caps a single upsert (~5461); chunk for full taxonomies (ESCO ~14k)
    for i in range(0, len(rows), BATCH):
        upsert_documents(CHROMA_SKILLS_COL, ids[i:i + BATCH], docs[i:i + BATCH], metas[i:i + BATCH])
    logger.info("Built skills store from %s: %d skills", src.name, len(rows))
    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = build()
    print(f"Loaded {n} skills into {SKILLS_DB_PATH} + collection '{CHROMA_SKILLS_COL}'")
