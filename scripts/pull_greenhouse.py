"""Phase-0 full-text source: pull full job descriptions from Greenhouse public board APIs.

Free, no auth, no bot-wall, structured. Writes our standard job CSV (title, company, location,
description, salary, url, date_posted, source). Used to test whether full posting text beats the
O*NET fallback (see .pipeline/full_text_sourcing_spec.md).

    python scripts/pull_greenhouse.py --boards stripe,gitlab,databricks --out data/adzuna/greenhouse_full.csv
"""
import argparse
import csv
import html
import re
import sys
import urllib.request

FIELDS = ["title", "company", "location", "description", "salary", "url", "date_posted", "source"]
API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"


def _strip_html(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)         # drop tags
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def pull_board(board: str) -> list[dict]:
    url = API.format(board=board)
    with urllib.request.urlopen(url, timeout=30) as r:
        import json
        data = json.load(r)
    out = []
    for j in data.get("jobs", []):
        desc = _strip_html(j.get("content", ""))
        if len(desc) < 200:               # skip stubs
            continue
        out.append({
            "title": (j.get("title") or "").strip(),
            "company": board.capitalize(),
            "location": ((j.get("location") or {}).get("name") or "").strip(),
            "description": desc,
            "salary": "",
            "url": j.get("absolute_url", ""),
            "date_posted": (j.get("updated_at") or "")[:10],
            "source": f"greenhouse:{board}",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boards", default="stripe,gitlab,databricks")
    ap.add_argument("--out", default="data/adzuna/greenhouse_full.csv")
    ap.add_argument("--max-per-board", type=int, default=200)
    args = ap.parse_args()

    rows = []
    for b in [x.strip() for x in args.boards.split(",") if x.strip()]:
        try:
            jobs = pull_board(b)[: args.max_per_board]
            print(f"{b}: {len(jobs)} jobs (full text)")
            rows.extend(jobs)
        except Exception as e:
            print(f"{b}: FAILED {e}", file=sys.stderr)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    lens = [len(r["description"]) for r in rows]
    print(f"wrote {len(rows)} jobs -> {args.out} | desc len min/med/max = "
          f"{min(lens)}/{sorted(lens)[len(lens)//2]}/{max(lens)}")


if __name__ == "__main__":
    main()
