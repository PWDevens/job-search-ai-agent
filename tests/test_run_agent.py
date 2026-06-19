"""Self-check for run_agent.py — assert-based, runs under mock=True."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from run_agent import run_once, append_csv, CSV_FIELDS
from tests.persona_evaluation.personas import ALL_PERSONAS

def test_run_once_returns_all_fields():
    """Check that run_once returns a dict with exactly CSV_FIELDS."""
    p = ALL_PERSONAS[0]
    row = run_once(
        persona=p,
        role_description=p.search_variants[0].role_description,
        geo_preference=p.search_variants[0].geo_preference,
        resume_text=None,
        agent="all",
        mock=True,
    )
    assert set(row.keys()) == set(CSV_FIELDS), f"Fields mismatch: {set(row.keys())} vs {set(CSV_FIELDS)}"
    assert 0 <= row["overall_score"] <= 4, f"Score out of range: {row['overall_score']}"
    print("[OK] run_once returns all CSV_FIELDS and valid score")

def test_append_csv_append_mode():
    """Check that append_csv appends (not overwrites)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test.csv"
        p = ALL_PERSONAS[0]
        row = run_once(
            persona=p,
            role_description=p.search_variants[0].role_description,
            geo_preference=p.search_variants[0].geo_preference,
            resume_text=None,
            agent="all",
            mock=True,
        )
        # Write twice
        append_csv(out_path, row)
        append_csv(out_path, row)
        # Should have header + 2 rows = 3 lines
        lines = out_path.read_text().strip().split("\n")
        assert len(lines) == 3, f"Expected 3 lines (header + 2 rows), got {len(lines)}"
        print("[OK] append_csv appends correctly (3 lines: header + 2 rows)")

if __name__ == "__main__":
    test_run_once_returns_all_fields()
    test_append_csv_append_mode()
    print("\n[OK] All self-checks passed")
