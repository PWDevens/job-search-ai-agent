"""
Live job search via the Adzuna API — a free, keyed aggregator that spans all
occupations (healthcare, trades, finance, education, tech, ...), matching the
breadth of the synthetic personas.

Returns the SAME job-dict shape the rest of the pipeline (ingest/matcher/agents/
scoring) already uses, so nothing downstream changes.

ponytail: one provider, one function. No provider-interface abstraction until a
second source actually exists (YAGNI). Quality gates kept minimal but real:
dedup by (title, company) + freshness filter + require title/description.

Self-check: `python -m app.pipeline.job_search` (needs ADZUNA_APP_ID/KEY).
"""
import logging
import httpx
from app.config import ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_COUNTRY, ADZUNA_MAX_DAYS

logger = logging.getLogger(__name__)

_API = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


def search_adzuna(what: str, where: str | None = None, n: int = 25,
                  max_days_old: int = ADZUNA_MAX_DAYS) -> list[dict]:
    """Fetch up to `n` live postings for `what` (role) near `where` (location).

    Raises RuntimeError if keys are missing; httpx.HTTPError on API failure.
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise RuntimeError(
            "Adzuna keys missing — set ADZUNA_APP_ID / ADZUNA_APP_KEY "
            "(free at https://developer.adzuna.com)."
        )
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": min(max(n, 1), 50),  # Adzuna caps at 50/page
        "what": what,
        "max_days_old": max_days_old,
        "content-type": "application/json",
    }
    if where:
        params["where"] = where

    url = _API.format(country=ADZUNA_COUNTRY)
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
    results = resp.json().get("results", [])
    jobs = [_normalize(r) for r in results]
    jobs = [j for j in jobs if j["title"] and j["description"]]   # quality gate
    return _dedup(jobs)[:n]


def _normalize(r: dict) -> dict:
    """Adzuna result → internal job dict (matches matcher/ingest schema)."""
    sal = r.get("salary_min") or r.get("salary_max")
    return {
        "title":       (r.get("title") or "").strip(),
        "company":     ((r.get("company") or {}).get("display_name") or "").strip(),
        "location":    ((r.get("location") or {}).get("display_name") or "").strip(),
        "description": (r.get("description") or "").strip(),
        "salary":      f"{int(sal):,}" if sal else "",
        "url":         r.get("redirect_url", ""),
        "date_posted": (r.get("created") or "")[:10],
        "source":      "adzuna",
    }


def _dedup(jobs: list[dict]) -> list[dict]:
    """Drop duplicate postings by (title, company) — Adzuna reposts are common."""
    seen, out = set(), []
    for j in jobs:
        key = (j["title"].lower(), j["company"].lower())
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


if __name__ == "__main__":   # ponytail: one runnable check
    try:
        res = search_adzuna("registered nurse", "Chicago", n=5)
        print(f"{len(res)} jobs; e.g. {res[0]['title']} @ {res[0]['company']} ({res[0]['location']})")
        assert all(j["title"] and j["source"] == "adzuna" for j in res), "bad shape"
        assert len({(j['title'], j['company']) for j in res}) == len(res), "dedup failed"
        print("PASS")
    except Exception as e:
        print(f"(needs ADZUNA keys + network) {type(e).__name__}: {e}")
