#!/bin/bash
# Phase 2: Simplified Direct Testing via Docker Container
# Tests the Job-Search AI Agent with all 11 personas

echo ""
echo "================================================================================"
echo "PHASE 2: INITIAL TESTING (Direct)"
echo "Job-Search AI Agent - 11 Personas x 3 Variants = 33 Total Searches"
echo "================================================================================"
echo ""

# Run the test inside the Docker container
docker compose exec -T app python3 << 'PYTHON_SCRIPT'
import sys
import time
import json
from pathlib import Path
from collections import defaultdict

# Add project to path
sys.path.insert(0, '/app')

from app.pipeline.ingest import ingest_jobs
from app.agents.crew import SearchRequest, run_search_crew

print("[*] Step 1: Ingest synthetic jobs...")
try:
    job_count = ingest_jobs("/app/data/synthetic/synthetic_jobs.csv")
    print(f"[OK] Ingested {job_count} jobs into Weaviate")
except Exception as e:
    print(f"[WARN] Error ingesting jobs: {e}")
    job_count = 0

print("\n[*] Step 2: Running searches with 11 personas...")
print("=" * 80)

# Persona definitions with resumes
personas_with_resumes = {}

# Load all persona resumes
resume_dir = Path("/app/data/synthetic")
for persona_name in ["nurse", "teacher", "consultant", "engineer", "designer", "accountant", "sales_manager", "electrician", "hr_manager", "operations_manager", "technical_writer"]:
    resume_file = resume_dir / f"{persona_name}_resume.txt"
    if resume_file.exists():
        resume_text = resume_file.read_text()
        personas_with_resumes[persona_name] = resume_text
        print(f"[OK] Loaded {persona_name} resume ({len(resume_text)} chars)")

print(f"\n[*] Running 33 searches ({len(personas_with_resumes)} personas x 3 variants each)...")
print("=" * 80)

# Test searches for each persona
test_queries = {
    "nurse": [
        ("Nursing informaticist with healthcare IT and EHR experience", "Remote", True),
        ("Healthcare data analyst with clinical background", "Washington DC", True),
        ("Clinical IT specialist with nursing experience", None, False),
    ],
    "teacher": [
        ("Teacher seeking learning analytics role", "Remote", True),
        ("Educator with curriculum design experience", "San Francisco", True),
        ("Instructional designer with education background", None, False),
    ],
    "consultant": [
        ("Management consultant with MBA seeking data science", "Remote", True),
        ("Strategy consultant with analytics experience", "New York", True),
        ("Consultant with quantitative analysis background", None, False),
    ],
    "engineer": [
        ("Civil engineer with GIS experience seeking geospatial analytics", "Remote", True),
        ("Infrastructure engineer with data skills", "Washington DC", True),
        ("Engineer with water resources background", None, False),
    ],
    "designer": [
        ("Product designer seeking analytics role", "Remote", True),
        ("UX designer with analytics experience", "San Francisco", True),
        ("Designer with product engagement analysis skills", None, False),
    ],
    "accountant": [
        ("CPA seeking finance analytics role", "Remote", True),
        ("Accountant with financial planning experience", "New York", True),
        ("CPA with audit background", None, False),
    ],
    "sales_manager": [
        ("Sales leader seeking revenue leadership role", "Remote", True),
        ("Sales manager with enterprise experience", "San Francisco", True),
        ("Sales professional with business development", None, False),
    ],
    "electrician": [
        ("Electrician seeking supervisor role", "Remote", True),
        ("Journeyman electrician with facilities experience", "Denver", True),
        ("Licensed electrician with commercial experience", None, False),
    ],
    "hr_manager": [
        ("HR manager seeking talent leadership role", "Remote", True),
        ("HR professional with compensation experience", "New York", True),
        ("HR specialist with employee relations background", None, False),
    ],
    "operations_manager": [
        ("Operations manager seeking supply chain leadership", "Remote", True),
        ("Operations professional with logistics experience", "Columbus", True),
        ("Manager with warehouse background", None, False),
    ],
    "technical_writer": [
        ("Technical writer seeking content strategy role", "Remote", True),
        ("Documentation specialist with API experience", "San Francisco", True),
        ("Writer with instructional design background", None, False),
    ],
}

metrics = []
search_num = 0
total_searches = 33

for persona_name, queries in test_queries.items():
    persona_display = persona_name.replace("_", " ").title()
    print(f"\n[PERSONA] {persona_display}")

    if persona_name not in personas_with_resumes:
        print(f"  [WARN] Resume not found for {persona_name}")
        continue

    resume_text = personas_with_resumes[persona_name]

    for idx, (role_desc, geo, use_resume) in enumerate(queries, 1):
        search_num += 1
        start_time = time.time()

        # Create search request
        req = SearchRequest(
            role_description=role_desc,
            geo_preference=geo,
            resume_text=resume_text if use_resume else None,
            extra_context=None,
        )

        variant_name = f"variant_{idx}"
        print(f"  [{search_num:2d}/33] {variant_name:20s} ... ", end="", flush=True)

        try:
            # Run search
            result = run_search_crew(req)
            elapsed = time.time() - start_time

            jobs = len(result.get("top_jobs", []))
            recs = len(result.get("resume_recs", []))
            spots = len(result.get("blind_spots", []))
            validation = result.get("agent_validation", {})
            fallback = any(not v for v in validation.values())

            print(f"[OK] {elapsed:.2f}s | Jobs: {jobs:2d} | Recs: {recs} | Spots: {spots}{' [FALLBACK]' if fallback else ''}")

            metrics.append({
                "persona": persona_name,
                "variant": variant_name,
                "status": "success",
                "time_sec": f"{elapsed:.2f}",
                "jobs": jobs,
                "recs": recs,
                "spots": spots,
                "fallback": fallback,
            })

        except Exception as e:
            elapsed = time.time() - start_time
            error = str(e)[:50]
            print(f"[FAIL] {error}")

            metrics.append({
                "persona": persona_name,
                "variant": variant_name,
                "status": "failed",
                "time_sec": f"{elapsed:.2f}",
                "jobs": 0,
                "recs": 0,
                "spots": 0,
                "fallback": False,
            })

# Print summary
print("\n" + "=" * 80)
print("PHASE 2 SUMMARY")
print("=" * 80)

successful = sum(1 for m in metrics if m["status"] == "success")
failed = sum(1 for m in metrics if m["status"] == "failed")

print(f"\nTotal Searches: {len(metrics)}")
print(f"Successful: {successful}")
print(f"Failed: {failed}")
if len(metrics) > 0:
    print(f"Success Rate: {(successful/len(metrics)*100):.1f}%")

print("\n[COMPLETE] Phase 2 Testing Complete!")
print("=" * 80)

PYTHON_SCRIPT

echo ""
echo "Phase 2 execution finished!"
