"""Pull full-text jobs from the ATS board registry -> standard CSV -> (optional) ingest.

The production un-truncation source (iter15: full text +0.414 overall vs truncated). Reports
source-coverage = fraction of pulled jobs with a parseable requirements section (the signal that
made full text win). Free, no auth.

    python scripts/pull_ats.py                          # registry -> data/adzuna/ats_full.csv
    python scripts/pull_ats.py --ingest --geo Remote    # also ingest into CHROMA_DB_PATH
    python scripts/pull_ats.py --boards greenhouse:stripe,ashby:ramp
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.pipeline.ats_sources import fetch_boards
from app.pipeline.sections import requirements_text

FIELDS = ["title", "company", "location", "description", "salary", "url", "date_posted", "source"]
REGISTRY = "data/ats_boards.json"


def _dedup(jobs):
    seen, out = set(), []
    for j in jobs:
        k = (j["title"].lower(), j["company"].lower(), j["description"][:500])
        if k not in seen:
            seen.add(k)
            out.append(j)
    return out


def source_coverage(jobs) -> float:
    """Fraction of jobs with a parseable requirements section (full-text health metric)."""
    if not jobs:
        return 0.0
    return round(100.0 * sum(1 for j in jobs if requirements_text(j["description"])) / len(jobs), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", help="comma list ats:token (overrides registry)")
    ap.add_argument("--registry", default=REGISTRY)
    ap.add_argument("--out", default="data/adzuna/ats_full.csv")
    ap.add_argument("--max-per-board", type=int, default=200)
    ap.add_argument("--ingest", action="store_true", help="ingest the CSV after pulling")
    ap.add_argument("--geo", default=None)
    args = ap.parse_args()

    if args.boards:
        boards = [tuple(b.split(":", 1)) for b in args.boards.split(",") if ":" in b]
    else:
        boards = [(b["ats"], b["token"]) for b in json.load(open(args.registry))]

    jobs = _dedup(fetch_boards(boards, max_per_board=args.max_per_board))
    cov = source_coverage(jobs)
    lens = sorted(len(j["description"]) for j in jobs) or [0]
    print(f"pulled {len(jobs)} full-text jobs from {len(boards)} boards | "
          f"requirements-coverage {cov}% | desc median {lens[len(lens)//2]} chars")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(jobs)
    print(f"wrote {args.out}")

    if args.ingest:
        from app.pipeline.ingest import ingest_jobs
        n = ingest_jobs(args.out, geo_filter=args.geo)
        print(f"ingested {n} jobs into ChromaDB")


if __name__ == "__main__":
    main()
