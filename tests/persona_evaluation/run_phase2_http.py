#!/usr/bin/env python
"""
Phase 2: Initial Testing via Flask API endpoints.

This script:
1. Loads all 11 personas
2. Ingests synthetic jobs via /ingest endpoint
3. Runs all 33 searches via /search endpoint
4. Collects metrics for each search
5. Generates baseline report
"""

import sys
import time
import json
import requests
from pathlib import Path
from collections import defaultdict
import csv

# Flask app endpoint
FLASK_URL = "http://localhost:5000"


def load_personas_from_file():
    """Load personas from personas.py"""
    personas_file = Path(__file__).parent / "personas.py"

    # Extract persona definitions from file
    personas_data = {
        "Nurse": {
            "variants": [
                ("informatics_with_resume", "Nursing informaticist with healthcare IT and EHR experience transitioning to data analytics", "Remote", True),
                ("data_analyst_with_resume", "Healthcare data analyst with clinical background looking to leverage patient outcome analysis skills", "Washington DC", True),
                ("clinical_specialist_no_resume", "Clinical IT specialist with 8 years nursing experience and basic data skills", None, False),
            ]
        },
        "Teacher": {
            "variants": [
                ("learning_analytics_with_resume", "High school mathematics teacher seeking transition to learning analytics and educational data", "Remote", True),
                ("ed_tech_with_resume", "Curriculum designer with data analysis experience looking for educational technology role", "San Francisco", True),
                ("instructional_designer_no_resume", "Instructional designer with 10 years education experience and Google Classroom proficiency", None, False),
            ]
        },
        "Consultant": {
            "variants": [
                ("data_scientist_with_resume", "Management consultant with 6 years BCG experience and MBA seeking senior data scientist role", "Remote", True),
                ("analytics_leader_with_resume", "Strategy consultant with financial modeling and Tableau experience transitioning to analytics leadership", "New York", True),
                ("quantitative_analyst_no_resume", "Quantitative analyst with MBA and 6 years consulting experience", None, False),
            ]
        },
        "Civil Engineer": {
            "variants": [
                ("geospatial_with_resume", "Civil engineer with 9 years infrastructure experience and GIS/ArcGIS skills seeking geospatial data analytics role", "Remote", True),
                ("infrastructure_analytics_with_resume", "Infrastructure engineer with AutoCAD and project management experience looking for data analytics in transportation", "Washington DC", True),
                ("water_resources_no_resume", "PE-licensed civil engineer with water infrastructure background and ArcGIS experience", None, False),
            ]
        },
        "Digital Designer": {
            "variants": [
                ("product_analytics_with_resume", "Product designer with 5 years UX experience and user research skills seeking product analytics role", "Remote", True),
                ("design_analytics_with_resume", "UX designer with Figma and Google Analytics experience transitioning to design analytics or research data", "San Francisco", True),
                ("growth_analyst_no_resume", "Designer with 5 years product experience and user engagement analysis skills", None, False),
            ]
        },
        "Accountant": {
            "variants": [
                ("financial_analyst_with_resume", "CPA with 9 years accounting and financial planning seeking transition to finance analytics role", "Remote", True),
                ("controller_with_resume", "Senior accountant with strong financial analysis and budgeting expertise looking for controller or finance leadership role", "New York", True),
                ("audit_analyst_no_resume", "CPA with audit and financial reporting background interested in internal audit or compliance roles", None, False),
            ]
        },
        "Sales Manager": {
            "variants": [
                ("vp_sales_with_resume", "Sales director with 11 years leading teams generating 50M+ revenue seeking VP Sales or revenue leadership role", "Remote", True),
                ("account_executive_with_resume", "Senior sales manager with enterprise account management and Salesforce expertise looking for account executive or sales management role", "San Francisco", True),
                ("business_development_no_resume", "Sales leader with business development and partnership building background interested in BD manager roles", None, False),
            ]
        },
        "Electrician": {
            "variants": [
                ("supervisor_with_resume", "Journeyman electrician with 12 years commercial and industrial experience seeking electrical supervisor or project management role", "Remote", True),
                ("facilities_with_resume", "Electrician with troubleshooting expertise and apprentice training experience looking for facilities or building management role", "Denver", True),
                ("master_electrician_no_resume", "Licensed electrician with commercial and industrial systems knowledge interested in master electrician or engineering technician roles", None, False),
            ]
        },
        "HR Manager": {
            "variants": [
                ("talent_director_with_resume", "HR manager with 10 years leading talent acquisition and employee engagement seeking HR director or talent leadership role", "Remote", True),
                ("compensation_analyst_with_resume", "HR professional with compensation analysis and benefits management experience looking for comp analyst or benefits role", "New York", True),
                ("employee_relations_no_resume", "HR specialist with employee relations and engagement background interested in employee relations or organizational development roles", None, False),
            ]
        },
        "Operations Manager": {
            "variants": [
                ("supply_chain_director_with_resume", "Operations manager with 10 years supply chain and process optimization seeking supply chain director or VP operations role", "Remote", True),
                ("logistics_manager_with_resume", "Operations professional with lean six sigma and cost reduction expertise looking for logistics manager or continuous improvement role", "Columbus", True),
                ("warehouse_manager_no_resume", "Operations manager with inventory and process management background interested in warehouse or distribution center management roles", None, False),
            ]
        },
        "Technical Writer": {
            "variants": [
                ("content_strategist_with_resume", "Technical writer with 8 years documentation experience seeking content strategy or information architecture role", "Remote", True),
                ("api_documentation_with_resume", "Documentation specialist with API and developer portal experience looking for technical writing or developer relations role", "San Francisco", True),
                ("instructional_design_no_resume", "Technical writer with training materials and user guide background interested in instructional design or content creation roles", None, False),
            ]
        },
    }

    return personas_data


def ingest_synthetic_jobs():
    """Ingest synthetic jobs via /ingest endpoint"""
    jobs_csv = Path(__file__).parent.parent.parent / "data" / "synthetic" / "synthetic_jobs.csv"

    print(f"\n[*] Ingesting synthetic jobs...")

    try:
        with open(jobs_csv, "r") as f:
            files = {"file": f}
            response = requests.post(
                f"{FLASK_URL}/ingest",
                files=files,
                timeout=60
            )

        if response.status_code == 200:
            result = response.json()
            job_count = result.get("count", 0)
            print(f"[OK] Successfully ingested {job_count} jobs")
            return job_count
        else:
            print(f"[WARN] Ingest returned status {response.status_code}")
            return 0
    except Exception as e:
        print(f"[WARN] Error ingesting jobs: {e}")
        return 0


def run_search(role_description, geo_preference=None, resume_text=None):
    """Run a search via /search endpoint"""
    try:
        data = {
            "role_description": role_description,
        }
        if geo_preference:
            data["geo_preference"] = geo_preference

        files = {}
        if resume_text:
            # Create in-memory file
            files = {"resume_file": ("resume.txt", resume_text)}

        response = requests.post(
            f"{FLASK_URL}/search",
            data=data,
            files=files,
            timeout=120
        )

        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"HTTP {response.status_code}"

    except Exception as e:
        return None, str(e)


def main():
    """Execute Phase 2 tests via Flask API"""
    print("\n" + "=" * 80)
    print("PHASE 2: INITIAL TESTING (via Flask API)")
    print("Job-Search AI Agent Persona Evaluation Suite")
    print("=" * 80)

    # Load personas
    print("\n[*] Loading personas...")
    personas_data = load_personas_from_file()
    print(f"[OK] Loaded {len(personas_data)} personas")

    # Ingest jobs
    job_count = ingest_synthetic_jobs()

    # Run searches
    print(f"\n[*] Running {sum(len(p['variants']) for p in personas_data.values())} searches...")
    print("=" * 80)

    metrics = []
    search_num = 0
    total_searches = sum(len(p['variants']) for p in personas_data.values())

    for persona_name, persona_info in personas_data.items():
        print(f"\n[PERSONA] {persona_name}")

        for variant_name, role_desc, geo, use_resume in persona_info['variants']:
            search_num += 1
            start_time = time.time()

            # Load resume if needed
            resume_text = None
            if use_resume:
                resume_file = Path(__file__).parent.parent.parent / "data" / "synthetic" / f"{persona_name.lower().replace(' ', '_')}_resume.txt"
                if resume_file.exists():
                    resume_text = resume_file.read_text()

            print(f"  [{search_num:2d}/{total_searches}] {variant_name:30s} ... ", end="", flush=True)

            # Run search
            result, error = run_search(role_desc, geo, resume_text)
            elapsed = time.time() - start_time

            if result:
                jobs = len(result.get("top_jobs", []))
                recs = len(result.get("resume_recs", []))
                spots = len(result.get("blind_spots", []))

                print(f"[OK] {elapsed:.2f}s | Jobs: {jobs} | Recs: {recs} | Spots: {spots}")

                metrics.append({
                    "persona": persona_name,
                    "variant": variant_name,
                    "status": "success",
                    "execution_time_sec": elapsed,
                    "jobs_returned": jobs,
                    "recommendations_returned": recs,
                    "blind_spots_returned": spots,
                    "error": None,
                })
            else:
                print(f"[FAIL] {error}")

                metrics.append({
                    "persona": persona_name,
                    "variant": variant_name,
                    "status": "failed",
                    "execution_time_sec": elapsed,
                    "jobs_returned": 0,
                    "recommendations_returned": 0,
                    "blind_spots_returned": 0,
                    "error": error,
                })

    # Generate report
    print("\n" + "=" * 80)
    print("PHASE 2 RESULTS")
    print("=" * 80)

    # Save to CSV
    reports_dir = Path(__file__).parent.parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    csv_path = reports_dir / "persona_results_phase2.csv"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
        writer.writeheader()
        writer.writerows(metrics)

    print(f"[OK] Results saved to {csv_path}")

    # Summary stats
    successful = sum(1 for m in metrics if m["status"] == "success")
    failed = sum(1 for m in metrics if m["status"] == "failed")
    avg_time = sum(m["execution_time_sec"] for m in metrics) / len(metrics)
    avg_jobs = sum(m["jobs_returned"] for m in metrics) / len(metrics)
    avg_recs = sum(m["recommendations_returned"] for m in metrics) / len(metrics)
    avg_spots = sum(m["blind_spots_returned"] for m in metrics) / len(metrics)

    print(f"\nTotal Searches: {len(metrics)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(successful/len(metrics)*100):.1f}%")
    print(f"\nAverage Execution Time: {avg_time:.2f}s")
    print(f"Average Jobs Returned: {avg_jobs:.1f}")
    print(f"Average Recommendations: {avg_recs:.1f}")
    print(f"Average Blind Spots: {avg_spots:.1f}")

    # Results by persona
    print(f"\nRESULTS BY PERSONA")
    print("=" * 80)

    persona_summary = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})
    for m in metrics:
        persona_summary[m["persona"]]["total"] += 1
        if m["status"] == "success":
            persona_summary[m["persona"]]["success"] += 1
        else:
            persona_summary[m["persona"]]["failed"] += 1

    for persona in sorted(persona_summary.keys()):
        stats = persona_summary[persona]
        rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"{persona:20s} | {stats['success']}/{stats['total']} success ({rate:5.1f}%)")

    print("\n[COMPLETE] Phase 2 Complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
