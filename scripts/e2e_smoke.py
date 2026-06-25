#!/usr/bin/env python3
"""
E2E smoke test: verify the full pipeline works end-to-end.

One thin script that reuses existing pieces: verify_deployment checks,
ingest functions, and the pipeline run.

Usage:
  python scripts/e2e_smoke.py          → full test (needs Ollama + running stack)
  python scripts/e2e_smoke.py --mock   → mock test (no Ollama needed; skips live assertions)

Exit codes:
  0 = all checks passed
  1 = one or more checks failed
"""
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import app.config as cfg
from app.pipeline.pipeline import run, SearchRequest
from app.pipeline.ingest import ingest_jobs, ingest_resume
from tests.persona_evaluation.personas import NURSE


def check_deployment():
    """Run existing verify_deployment checks"""
    print("\n[*] Step 1: Checking deployment (Ollama, Flask, model)...")

    # Import and run verify_deployment checks
    from scripts.verify_deployment import (
        check_ollama_version, check_ollama_model, check_flask_health
    )

    checks = [
        ("Ollama Version", check_ollama_version),
        ("Ollama Model", check_ollama_model),
        ("Flask Health", check_flask_health),
    ]

    results = []
    for name, check_fn in checks:
        try:
            passed, message = check_fn()
            results.append((name, passed, message))
            print(f"      {message}")
        except Exception as e:
            results.append((name, False, f"[FAIL] {name}: {e}"))
            print(f"      [FAIL] {name}: {e}")

    passed_count = sum(1 for _, p, _ in results if p)
    return passed_count == len(results), results


def ingest_demo_data():
    """Ensure demo data is ingested"""
    print("\n[*] Step 2: Ensuring demo data is ingested...")

    try:
        # Try to ingest demo jobs
        jobs_file = ROOT / "data" / "demo" / "demo_jobs.csv"
        resume_file = ROOT / "data" / "demo" / "demo_resume.txt"

        if jobs_file.exists():
            job_count = ingest_jobs(str(jobs_file))
            print(f"      [OK] Ingested {job_count} demo jobs")
        else:
            print(f"      [WARN] Demo jobs file not found: {jobs_file}")
            return False

        if resume_file.exists():
            resume_text = resume_file.read_text()
            # Resume is used directly in pipeline request
            print(f"      [OK] Demo resume loaded ({len(resume_text)} chars)")
        else:
            print(f"      [WARN] Demo resume file not found: {resume_file}")
            return False

        return True
    except Exception as e:
        print(f"      [FAIL] Ingestion error: {e}")
        return False


def run_pipeline_search(mock: bool = False):
    """Run one real pipeline search end-to-end"""
    print("\n[*] Step 3: Running live pipeline search...")

    try:
        # Use a simple search request
        req = SearchRequest(
            role_description="Data Engineer Python Flask ChromaDB",
            geo_preference=None,
            resume_text=None,
        )

        if mock:
            # Mock mode: create a dummy result without calling LLM
            print("      [MOCK] Skipping live pipeline (--mock mode)")
            from app.pipeline.pipeline import SearchResult
            result = SearchResult(
                top_jobs=[{"title": "Mock Job", "company": "Mock Co", "document": "mock"}],
                resume_recs=["Mock recommendation"],
                blind_spots=["mock skill"],
                agent_validation={"job_matcher": True, "resume_coach": True, "career_strategist": True},
                raw_agent_output={},
            )
        else:
            # Live mode: run the real pipeline
            result = run(req)

        # Verify results are non-empty
        jobs_count = len(result.top_jobs)
        recs_count = len(result.resume_recs)
        spots_count = len(result.blind_spots)

        if jobs_count == 0 or recs_count == 0 or spots_count == 0:
            print(f"      [FAIL] Incomplete results: jobs={jobs_count}, recs={recs_count}, spots={spots_count}")
            return False

        print(f"      [OK] Pipeline executed: {jobs_count} jobs, {recs_count} recs, {spots_count} blind spots")
        return True

    except Exception as e:
        print(f"      [FAIL] Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="E2E smoke test for job-search-ai-agent")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (no Ollama required)")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("E2E SMOKE TEST: Job-Search AI Agent")
    print("=" * 70)

    if args.mock:
        print("[INFO] Running in MOCK mode (no live services needed)")

    all_passed = True

    # Step 1: Deployment checks (skip Ollama/Flask in mock mode)
    if not args.mock:
        deploy_ok, deploy_results = check_deployment()
        if not deploy_ok:
            all_passed = False
    else:
        print("\n[*] Step 1: Skipping deployment checks (--mock mode)")

    # Step 2: Data ingestion
    ingest_ok = ingest_demo_data()
    if not ingest_ok and not args.mock:
        all_passed = False

    # Step 3: Pipeline search
    pipeline_ok = run_pipeline_search(mock=args.mock)
    if not pipeline_ok:
        all_passed = False

    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("[PASS] All checks passed")
        print("=" * 70 + "\n")
        return 0
    else:
        print("[FAIL] One or more checks failed")
        print("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
