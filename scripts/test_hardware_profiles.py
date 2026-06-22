"""
Smoke test: confirm each hardware tier maps to the right model and the mock
pipeline runs under it. No Ollama or GPU required.

    python scripts/test_hardware_profiles.py
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TIERS = ["cpu", "gpu_avg", "gpu_modern"]


def main():
    print(f"{'TIER':<12} {'AGENT_MODEL':<22} MOCK PIPELINE")
    print("-" * 50)
    all_ok = True
    for tier in TIERS:
        env = {**os.environ, "HARDWARE_TIER": tier}
        # Resolve the model the app would pick for this tier.
        model = subprocess.run(
            [sys.executable, "-c", "from app.config import AGENT_MODEL; print(AGENT_MODEL)"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        ).stdout.strip()
        # Run the mock pipeline under this tier.
        run = subprocess.run(
            [sys.executable, "run_agent.py", "--role", "Data Engineer", "--mock"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        ok = run.returncode == 0
        all_ok &= ok
        print(f"{tier:<12} {model:<22} {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(run.stderr[-500:])

    print("-" * 50)
    print("All tiers OK" if all_ok else "SOME TIERS FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
