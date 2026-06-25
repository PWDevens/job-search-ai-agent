"""
Offline checks for the Tier-1 skills layer: build the store from the committed
sample, then verify exact + semantic extraction and synonym normalization.

Run: python tests/test_skills.py   (needs chromadb + sentence-transformers; no Ollama)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.skills import loader, normalize


def _fresh_store():
    # Clear cached alias/meta maps so each run reflects the freshly-built DB.
    normalize._alias_map.cache_clear()
    normalize._meta_map.cache_clear()
    n = loader.build(loader.SAMPLE)  # force the committed sample (ignore any raw/ drop)
    normalize._alias_map.cache_clear()
    normalize._meta_map.cache_clear()
    return n


def test_build():
    n = _fresh_store()
    assert n >= 50, f"expected the ~60-skill sample, got {n}"
    print(f"[PASS] build loaded {n} skills")


def test_exact_extraction():
    sk = normalize.extract_skill_ids("Seeking an RN with ACLS certification and Epic EHR experience")
    ids = {s["skill_id"] for s in sk}
    assert "sk_acls" in ids, f"ACLS should be extracted (exact), got {ids}"
    assert any(s["skill_id"] == "sk_acls" and s["match"] == "exact" for s in sk)
    print("[PASS] exact extraction (ACLS, Epic) works")


def test_synonym_normalization():
    assert normalize.normalize_one("advanced cardiac life support") == "sk_acls", \
        "synonym must map to the canonical ACLS id"
    assert normalize.normalize_one("certified public accountant") == "sk_cpa"
    print("[PASS] synonym -> canonical id")


def test_semantic_paraphrase():
    # Confident paraphrase (no literal alias) resolves via the embedding path.
    assert normalize.normalize_one("head nurse running the ward") == "sk_charge_nurse", \
        "confident paraphrase should resolve to Charge Nurse"
    assert normalize.normalize_one("cloud infrastructure on Amazon") == "sk_aws"
    print("[PASS] semantic paraphrase ('head nurse...' -> Charge Nurse, cloud -> AWS)")


def test_semantic_ambiguous_falls_back():
    # Precision-first: an ambiguous generic-word phrase must NOT mis-map (margin reject).
    # 'lead the nursing unit' -> Leadership 0.72 vs Charge Nurse 0.69 (margin 0.03) -> None.
    assert normalize.normalize_one("lead the nursing unit") is None, \
        "ambiguous generic phrase should return None (fall back to substring), not mis-map"
    print("[PASS] ambiguous phrase rejected (precision-first margin)")


def test_nonsense_returns_empty():
    assert normalize.extract_skill_ids("xyzzy frobnicate quux") == []
    assert normalize.normalize_one("xyzzy frobnicate quux") is None
    print("[PASS] nonsense -> empty / None")


def test_graph_degrades_without_data():
    # Tier-2 occupation graph needs the ESCO occupation files (a runtime data drop);
    # without them every lookup must degrade to [] rather than raising. Simulate the
    # unbuilt state so the test is deterministic even after a local graph build.
    import sqlite3
    from app.config import SKILLS_DB_PATH
    from app.skills import graph as G
    con = sqlite3.connect(SKILLS_DB_PATH)
    con.executescript("DROP TABLE IF EXISTS occupation_aliases; DROP TABLE IF EXISTS occupation_skills;")
    con.commit(); con.close()
    G._occ_alias_map.cache_clear()
    assert G.essential_skills_for("registered nurse") == [], \
        "essential_skills_for must return [] when the occupation graph isn't built"
    print("[PASS] occupation graph degrades gracefully when unbuilt")


if __name__ == "__main__":
    tests = [test_build, test_exact_extraction, test_synonym_normalization,
             test_semantic_paraphrase, test_semantic_ambiguous_falls_back,
             test_nonsense_returns_empty, test_graph_degrades_without_data]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {type(e).__name__}: {e}"); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
