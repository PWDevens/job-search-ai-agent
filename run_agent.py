"""
Run agents against a persona or ad-hoc role; score + append CSV.

Usage examples:
    python run_agent.py --role "data analyst" --resume data/synthetic/nurse_resume.txt
    python run_agent.py --persona nurse
    python run_agent.py --persona all
    python run_agent.py --persona nurse --agent job_matcher
    python run_agent.py --mock
"""
import argparse, csv, json, sys, time
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from app.agents.models import (JobMatchList, JobMatch, ResumeRecList, ResumeRec,
                               CareerStrategy, BlindSpot, StrategyRec)
from app.pipeline.pipeline import run, SearchRequest
from tests.persona_evaluation.personas import ALL_PERSONAS, get_persona_by_name
from tests.persona_evaluation.evaluation_scoring import ResultEvaluator

# ── constants ─────────────────────────────────────────────────────────────────
VALID_AGENTS = ("job_matcher", "resume_coach", "career_strategist", "all")
DEFAULT_OUT = ROOT / "reports" / "agent_eval.csv"
CSV_FIELDS = [
    "timestamp", "persona", "role_description", "geo_preference", "agent", "mock",
    "elapsed_s", "jobs_returned", "recs_returned", "blind_spots_returned",
    "avg_job_score", "avg_rec_score", "avg_spot_score", "overall_score",
    "quality_label", "agent_validation",
]

# ── load synthetic jobs once ──────────────────────────────────────────────────
def _load_jobs():
    rows = []
    with open(ROOT / "data/synthetic/synthetic_jobs.csv") as f:
        for r in csv.DictReader(f):
            rows.append({
                "title": r["title"], "company": r["company"],
                "location": r["location"], "salary": r.get("salary", ""),
                "description": r["description"], "url": r.get("url", ""),
                "score": 0.85,
            })
    return rows

ALL_JOBS = _load_jobs()
_last_retrieved: list = []  # ponytail: global to share retrieved jobs with _mock_chat

# ── mock helpers ──────────────────────────────────────────────────────────────
def _mock_find_top_jobs(role_description, geo_preference=None, resume_text=None, n=20):
    global _last_retrieved
    kw = role_description.lower()
    scored = [(j, sum(1 for w in kw.split() if w in (j["description"] + j["title"]).lower())) for j in ALL_JOBS]
    scored.sort(key=lambda x: -x[1])
    _last_retrieved = [j for j, _ in scored[:n]]
    return _last_retrieved

def _mock_chat(system, user, schema):
    jobs = _last_retrieved[:5] or ALL_JOBS[:5]
    if schema is JobMatchList:
        return JobMatchList(matches=[
            JobMatch(rank=i+1, title=j["title"], company=j["company"],
                     location=j["location"], salary=j.get("salary"),
                     url=j.get("url"), why_it_fits=f"Strong match for requested role at {j['company']}")
            for i, j in enumerate(jobs)
        ])
    if schema is ResumeRecList:
        return ResumeRecList(recommendations=[
            ResumeRec(priority="HIGH", title=f"Add {skill}",
                      current_state="Not listed", fix=f"Add {skill} to Technical Skills",
                      why=f"Required at {jobs[0]['company']} — {jobs[0]['title']}",
                      impact="ATS filter improvement")
            for skill in ["Python", "SQL", "Tableau", "Excel", "Cloud platforms"]
        ])
    if schema is CareerStrategy:
        return CareerStrategy(
            blind_spots=[
                BlindSpot(skill=s, why=f"Appears in top matches at {jobs[0]['company']}",
                          remediation=f"Complete {s} fundamentals course",
                          time_to_proficiency="4-6 weeks", priority="HIGH")
                for s in ["Python", "SQL", "Data Visualization", "Cloud (AWS/GCP)", "Machine Learning"]
            ],
            strategy=[
                StrategyRec(title="Target high-match roles first",
                            evidence=f"{jobs[0]['title']} at {jobs[0]['company']} aligns with background",
                            action="Apply within 48 hours to top 3 matches")
            ]
        )
    raise ValueError(f"Unknown schema: {schema}")

# ── ad-hoc persona stub ───────────────────────────────────────────────────────
@dataclass
class _AdHocPersona:
    target_job_titles: list  # ponytail: minimal stand-in so ResultEvaluator runs without a persona

# ── mock context manager ──────────────────────────────────────────────────────
@contextmanager
def mock_patches():
    with ExitStack() as stack:
        stack.enter_context(patch("app.pipeline.pipeline.find_top_jobs", side_effect=_mock_find_top_jobs))
        stack.enter_context(patch("app.pipeline.pipeline.find_resume_recommendations", side_effect=_mock_find_top_jobs))
        stack.enter_context(patch("app.pipeline.pipeline.find_blind_spots", return_value=["Python","SQL","Cloud","Tableau","ML"]))
        stack.enter_context(patch("app.agents.agent_job_matcher.chat", side_effect=_mock_chat))
        stack.enter_context(patch("app.agents.agent_resume_coach.chat", side_effect=_mock_chat))
        stack.enter_context(patch("app.agents.agent_career_strategist.chat", side_effect=_mock_chat))
        stack.enter_context(patch("app.agents.agent_career_strategist.query_ats_knowledge", return_value="Use keywords from job description."))
        yield

# ── core functions ────────────────────────────────────────────────────────────
def _read_resume(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        print(f"WARN: resume not found: {path}; continuing with no resume", file=sys.stderr)
        return None
    return p.read_text(errors="replace")

def run_once(*, role_description, geo_preference, resume_text, persona, agent, mock, dump_json=False) -> dict:
    """Run one agent execution + scoring. Returns one CSV-row dict."""
    req = SearchRequest(role_description=role_description, geo_preference=geo_preference, resume_text=resume_text)
    t0 = time.monotonic()

    if mock:
        with mock_patches():
            result = run(req)
    else:
        result = run(req)  # live Ollama; let connection errors propagate

    elapsed = round(time.monotonic() - t0, 2)
    d = result.as_dict()

    if dump_json:
        print(json.dumps(d, indent=2, default=str))

    scoring_persona = persona if persona is not None else _AdHocPersona(target_job_titles=[])
    scores = ResultEvaluator.evaluate_search_result(d, scoring_persona)

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "persona": persona.name if persona else "",
        "role_description": role_description,
        "geo_preference": geo_preference or "",
        "agent": agent,
        "mock": "mock" if mock else "live",
        "elapsed_s": elapsed,
        "jobs_returned": len(d.get("top_jobs", [])),
        "recs_returned": len(d.get("resume_recs", [])),
        "blind_spots_returned": len(d.get("blind_spots", [])),
        "avg_job_score": round(scores["avg_job_score"], 2),
        "avg_rec_score": round(scores["avg_rec_score"], 2),
        "avg_spot_score": round(scores["avg_spot_score"], 2),
        "overall_score": round(scores["overall_score"], 2),
        "quality_label": scores["quality_label"],
        "agent_validation": json.dumps(result.agent_validation),
    }

def append_csv(out_path: Path, row: dict) -> None:
    """Append one row. Rewrite header if absent/empty/mismatched."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header_ok = False
    if out_path.exists() and out_path.stat().st_size > 0:
        with open(out_path, newline="") as f:
            first = f.readline().strip()
        header_ok = first == ",".join(CSV_FIELDS)
    mode = "a" if header_ok else "w"   # ponytail: legacy/empty/mismatched header -> rewrite fresh
    with open(out_path, mode, newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if mode == "w":
            w.writeheader()
        w.writerow(row)

def print_summary(row: dict) -> None:
    who = row["persona"] or row["role_description"]
    print(f"{who} | agent={row['agent']} mock={row['mock']} | {row['elapsed_s']}s")
    print(f"  jobs={row['jobs_returned']} recs={row['recs_returned']} blind_spots={row['blind_spots_returned']}")
    print(f"  job={row['avg_job_score']} rec={row['avg_rec_score']} spot={row['avg_spot_score']} -> overall={row['overall_score']} ({row['quality_label']})")
    print(f"  validation={row['agent_validation']}")

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Run agents against a persona or ad-hoc role; score + append CSV.")
    ap.add_argument("--role")
    ap.add_argument("--resume")
    ap.add_argument("--persona")                 # name (case-insensitive) or literal "all"
    ap.add_argument("--agent", default="all")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--json", dest="json_out", action="store_true")
    args = ap.parse_args()

    # Validate agent
    if args.agent not in VALID_AGENTS:
        print(f"Invalid --agent. Valid: {VALID_AGENTS}", file=sys.stderr)
        sys.exit(1)

    # Build runs list
    runs = []
    if args.persona:
        if args.persona == "all":
            for p in ALL_PERSONAS:
                runs.append({
                    "persona": p,
                    "role_description": p.search_variants[0].role_description,
                    "geo_preference": p.search_variants[0].geo_preference,
                    "resume_text": _read_resume(p.resume_path),
                })
        else:
            try:
                p = get_persona_by_name(args.persona)
            except ValueError as e:
                print(str(e), file=sys.stderr)
                sys.exit(1)
            runs.append({
                "persona": p,
                "role_description": p.search_variants[0].role_description,
                "geo_preference": p.search_variants[0].geo_preference,
                "resume_text": _read_resume(p.resume_path),
            })
    elif args.role:
        runs.append({
            "persona": None,
            "role_description": args.role,
            "geo_preference": None,
            "resume_text": _read_resume(args.resume),
        })
    else:
        print("Provide --role or --persona. See --help.", file=sys.stderr)
        sys.exit(1)

    # Attach agent and mock to each run
    out = Path(args.out)
    for kw in runs:
        kw["agent"] = args.agent
        kw["mock"] = args.mock
        kw["dump_json"] = args.json_out

    # Execute
    if len(runs) == 1:
        # Single run: propagate errors
        kw = runs[0]
        row = run_once(**kw)
        append_csv(out, row)
        print_summary(row)
    else:
        # Batch: catch per-item and continue
        for kw in runs:
            name = kw["persona"].name
            try:
                row = run_once(**kw)
                append_csv(out, row)
                print_summary(row)
            except Exception as e:
                print(f"{name} ... ERROR: {e}", file=sys.stderr)

    print(f"\nResults -> {out}")

if __name__ == "__main__":
    main()
