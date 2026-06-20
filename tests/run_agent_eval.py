"""Persona eval harness — thin wrapper over run_agent.py. Mock by default, --live for real Ollama."""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from run_agent import run_once, append_csv, _read_resume
from tests.persona_evaluation.personas import ALL_PERSONAS

if __name__ == "__main__":
    live = "--live" in sys.argv
    out = ROOT / "reports" / "agent_eval.csv"
    rows = []
    for p in ALL_PERSONAS:
        print(f"  {p.name} ... ", end="", flush=True)
        try:
            row = run_once(
                persona=p,
                role_description=p.search_variants[0].role_description,
                geo_preference=p.search_variants[0].geo_preference,
                resume_text=_read_resume(p.resume_path),
                agent="all",
                mock=not live,
            )
            append_csv(out, row)
            rows.append(row)
            print(f"{row['quality_label']} ({row['overall_score']}) {row['elapsed_s']}s")
        except Exception as e:
            print(f"ERROR: {e}")
    print(f"\nResults -> {out}")
    if rows:
        avg = sum(r["overall_score"] for r in rows) / len(rows)
        print(f"Overall avg score: {avg:.2f}/4.0")
