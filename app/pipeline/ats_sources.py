"""Full-text job sourcing from ATS public board APIs (Greenhouse / Lever / Ashby).

Free, no auth, no bot-wall, structured — the un-truncation source. Phase-0 (iter15) proved full
posting text beats the truncated-Adzuna + O*NET fallback by +0.414 overall, 14/14 personas. Adzuna
truncates 100% at 500 chars and its redirect URL is 403 bot-walled; these ATS APIs return the whole
posting. Normalizes to the standard job dict the ingest pipeline already consumes.
"""
import html
import json
import logging
import re
import urllib.request

logger = logging.getLogger(__name__)
_UA = {"User-Agent": "Mozilla/5.0 (job-search-agent)"}


def _get(url: str):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _strip_html(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()


def _job(title, company, location, desc, url, date, source) -> dict:
    return {"title": (title or "").strip(), "company": company,
            "location": (location or "").strip(), "description": desc, "salary": "",
            "url": url or "", "date_posted": (date or "")[:10], "source": source}


def fetch_greenhouse(token: str) -> list[dict]:
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    return [_job(j.get("title"), token.capitalize(), (j.get("location") or {}).get("name"),
                 _strip_html(j.get("content", "")), j.get("absolute_url"), j.get("updated_at"),
                 f"greenhouse:{token}") for j in d.get("jobs", [])]


def fetch_lever(token: str) -> list[dict]:
    out = []
    for j in _get(f"https://api.lever.co/v0/postings/{token}?mode=json"):
        parts = [j.get("descriptionPlain", "")]
        for lst in j.get("lists", []):           # responsibilities / requirements blocks
            parts += [lst.get("text", ""), _strip_html(lst.get("content", ""))]
        parts.append(j.get("additionalPlain", ""))
        desc = "\n\n".join(p for p in parts if p)
        out.append(_job(j.get("text"), token.capitalize(), (j.get("categories") or {}).get("location"),
                        desc, j.get("hostedUrl"), "", f"lever:{token}"))
    return out


def fetch_ashby(token: str) -> list[dict]:
    d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    return [_job(j.get("title"), token.capitalize(), j.get("location"),
                 j.get("descriptionPlain", ""), j.get("jobUrl"), j.get("publishedAt"),
                 f"ashby:{token}") for j in d.get("jobs", []) if j.get("isListed", True)]


_FETCH = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


def fetch_board(ats: str, token: str, min_chars: int = 200) -> list[dict]:
    """One board -> full-text jobs (skips stubs under min_chars)."""
    jobs = _FETCH[ats.lower()](token)
    return [j for j in jobs if j["title"] and len(j["description"]) >= min_chars]


def fetch_boards(boards: list[tuple[str, str]], max_per_board: int = 200) -> list[dict]:
    """boards: [(ats, token), ...] -> merged full-text jobs; a dead/unknown board is skipped, not fatal."""
    out = []
    for ats, token in boards:
        try:
            jobs = fetch_board(ats, token)[:max_per_board]
            logger.info("ATS %s/%s: %d full-text jobs", ats, token, len(jobs))
            out.extend(jobs)
        except Exception as e:
            logger.warning("ATS %s/%s failed: %s", ats, token, e)
    return out


if __name__ == "__main__":
    for ats, tok in [("greenhouse", "stripe"), ("lever", "leverdemo"), ("ashby", "ramp")]:
        js = fetch_board(ats, tok)
        assert js, f"{ats}/{tok} returned nothing"
        print(f"{ats}/{tok}: {len(js)} jobs, median desc {sorted(len(j['description']) for j in js)[len(js)//2]} chars")
    print("self-check OK")
