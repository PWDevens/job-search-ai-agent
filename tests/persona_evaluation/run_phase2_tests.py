#!/usr/bin/env python
"""
Phase 2: Initial Testing — Run all persona searches and collect baseline metrics.

This script:
1. Loads all 11 personas
2. Ingests synthetic jobs into Weaviate
3. Runs all 33 searches (11 personas × 3 variants)
4. Collects metrics for each search
5. Generates baseline report
"""

import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.crew import SearchRequest, run_search_crew
from app.pipeline.ingest import ingest_jobs
from tests.persona_evaluation.personas import ALL_PERSONAS, load_resume
from tests.persona_evaluation.metrics_collector import MetricsCollector


def load_personas_and_resumes():
    """Load all personas and their resume text"""
    personas_with_resumes = []
    for persona in ALL_PERSONAS:
        resume_text = load_resume(Path(persona.resume_path).name)
        personas_with_resumes.append((persona, resume_text))
        print(f"✓ Loaded {persona.name} resume ({len(resume_text)} chars)")
    return personas_with_resumes


def ingest_synthetic_jobs():
    """Ingest all synthetic jobs into Weaviate"""
    jobs_csv = PROJECT_ROOT / "data" / "synthetic" / "synthetic_jobs.csv"

    if not jobs_csv.exists():
        print(f"❌ Synthetic jobs file not found: {jobs_csv}")
        return 0

    print(f"\n📥 Ingesting synthetic jobs from {jobs_csv}...")
    try:
        job_count = ingest_jobs(str(jobs_csv))
        print(f"✓ Successfully ingested {job_count} jobs into Weaviate")
        return job_count
    except Exception as e:
        print(f"❌ Error ingesting jobs: {e}")
        return 0


def run_all_searches(personas_with_resumes):
    """Run all 33 searches and collect metrics"""
    collector = MetricsCollector()
    search_count = 0
    failed_count = 0

    print(f"\n🔍 Running {len(personas_with_resumes) * 3} searches across {len(personas_with_resumes)} personas...")
    print("=" * 80)

    for persona, resume_text in personas_with_resumes:
        print(f"\n📋 Persona: {persona.name} ({persona.role})")

        for variant in persona.search_variants:
            search_count += 1
            start_time = time.time()

            # Prepare search request
            req = SearchRequest(
                role_description=variant.role_description,
                geo_preference=variant.geo_preference,
                resume_text=resume_text if variant.use_resume else None,
                extra_context=None,
            )

            print(f"  [{search_count:2d}/33] {variant.name:30s} ... ", end="", flush=True)

            try:
                # Run search
                result = run_search_crew(req)
                execution_time = time.time() - start_time

                # Convert dataclass to dict if needed
                result_dict = result.as_dict() if hasattr(result, "as_dict") else result

                # Record metrics
                collector.record_search(
                    persona=persona.name,
                    search_variant=variant.name,
                    search_query=variant.role_description[:60],
                    geo_preference=variant.geo_preference,
                    used_resume=variant.use_resume,
                    execution_time_sec=execution_time,
                    result=result_dict,
                    error_message=None,
                )

                # Print status
                fallback_indicator = " [FALLBACK]" if result_dict.get("agent_validation", {}).get("resume_coach") == False else ""
                jobs = len(result_dict.get("top_jobs", []))
                recs = len(result_dict.get("resume_recs", []))
                spots = len(result_dict.get("blind_spots", []))

                print(f"OK {execution_time:.2f}s | Jobs: {jobs} | Recs: {recs} | Spots: {spots}{fallback_indicator}")

            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = str(e)[:100]
                failed_count += 1

                # Record failed search
                collector.record_search(
                    persona=persona.name,
                    search_variant=variant.name,
                    search_query=variant.role_description[:60],
                    geo_preference=variant.geo_preference,
                    used_resume=variant.use_resume,
                    execution_time_sec=execution_time,
                    result={"top_jobs": [], "resume_recs": [], "blind_spots": []},
                    error_message=error_msg,
                )

                print(f"❌ FAILED: {error_msg}")

    return collector, search_count, failed_count


def main():
    """Main Phase 2 test execution"""
    print("\n" + "=" * 80)
    print("PHASE 2: INITIAL TESTING")
    print("Job-Search AI Agent Persona Evaluation Suite")
    print("=" * 80)

    # Step 1: Load personas and resumes
    print("\n📚 Loading personas and resumes...")
    personas_with_resumes = load_personas_and_resumes()
    print(f"✓ Loaded {len(personas_with_resumes)} personas")

    # Step 2: Ingest synthetic jobs
    job_count = ingest_synthetic_jobs()
    if job_count == 0:
        print("⚠️  No jobs ingested - proceeding with search (may find limited results)")

    # Step 3: Run all searches
    collector, total_searches, failed_searches = run_all_searches(personas_with_resumes)

    # Step 4: Generate reports
    print("\n" + "=" * 80)
    print("📊 GENERATING REPORTS")
    print("=" * 80)

    csv_path = collector.export_csv()
    print(f"✓ Exported metrics to {csv_path}")

    # Print summary
    collector.print_summary()

    # Print results by persona
    print("\n📈 RESULTS BY PERSONA")
    print("=" * 80)

    from collections import defaultdict
    persona_stats = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0, "avg_time": 0, "times": []})

    for metric in collector.metrics:
        stats = persona_stats[metric.persona]
        stats["total"] += 1
        if metric.error_message:
            stats["failed"] += 1
        else:
            stats["success"] += 1
        stats["times"].append(metric.execution_time_sec)

    for persona_name in sorted(persona_stats.keys()):
        stats = persona_stats[persona_name]
        avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
        success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"{persona_name:20s} | {stats['success']:2d}/{stats['total']:2d} success ({success_rate:5.1f}%) | {avg_time:5.2f}s avg")

    print("\n✅ Phase 2 Complete!")
    print(f"   Total Searches: {total_searches}")
    print(f"   Successful: {total_searches - failed_searches}")
    print(f"   Failed: {failed_searches}")
    print(f"   Metrics saved to: {csv_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
