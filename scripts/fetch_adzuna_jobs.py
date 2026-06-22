"""
Fetch live job postings from Adzuna for every synthetic persona (+ demo) and
write ONE combined, deduped CSV snapshot. The snapshot makes the otherwise-live
Adzuna run reproducible: ingest the same CSV and the eval is repeatable.

Then ingest + run the eval against this market:
    python scripts/ingest_jobs.py data/adzuna/<snapshot>.csv --clear
    OLLAMA_TEMPERATURE=0.0 python scripts/eval_hardware_matrix.py --label adzuna --scenarios 2

Needs ADZUNA_APP_ID / ADZUNA_APP_KEY (free: https://developer.adzuna.com).
"""
import argparse, csv, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.pipeline.job_search import search_adzuna
from tests.persona_evaluation.personas import ALL_PERSONAS

FIELDS = ["title", "company", "location", "description", "salary", "url", "date_posted", "source"]
DEMO = ("Data Engineer", "Washington DC")  # demo persona market


def _query_for(persona):
    """Short role term for the Adzuna 'what' param + the persona's geo.

    Adzuna's 'where' expects a real place — "Remote" (or blank) returns nothing,
    so map those to a nationwide search, which is what "general market demand"
    for the role actually means.
    """
    what = (persona.target_job_titles[0] if getattr(persona, "target_job_titles", None)
            else persona.search_variants[0].role_description)
    where = persona.search_variants[0].geo_preference
    if not where or where.strip().lower() == "remote":
        where = None
    return what, where


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-persona", type=int, default=25, help="postings to fetch per persona")
    ap.add_argument("--out", default=None, help="output CSV (default: data/adzuna/jobs_<ts>.csv)")
    args = ap.parse_args()

    queries = [(p.name, *_query_for(p)) for p in ALL_PERSONAS] + [("demo", *DEMO)]

    all_jobs, seen = [], set()
    for name, what, where in queries:
        try:
            jobs = search_adzuna(what, where, n=args.per_persona)
        except Exception as e:
            print(f"  {name:18s} '{what}' @ {where or '-'}: ERROR {e}", file=sys.stderr)
            continue
        fresh = 0
        for j in jobs:
            key = (j["title"].lower(), j["company"].lower())
            if key not in seen:
                seen.add(key); all_jobs.append(j); fresh += 1
        print(f"  {name:18s} '{what}' @ {where or '-'}: {len(jobs)} fetched, {fresh} new")

    if not all_jobs:
        print("No jobs fetched — check ADZUNA keys / network.", file=sys.stderr); sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else ROOT / "data" / "adzuna" / f"jobs_{ts}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_jobs)
    print(f"\n{len(all_jobs)} unique jobs across {len(queries)} personas -> {out}")
    print(f"Next: python scripts/ingest_jobs.py {out} --clear")


if __name__ == "__main__":
    main()
