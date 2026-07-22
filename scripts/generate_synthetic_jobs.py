"""
O*NET-grounded synthetic job-posting generator (iter6).

Composes realistic, full-length, LABELED postings from O*NET (occupation description,
core tasks, software tools, knowledge, job-zone education/experience) so the synthetic
corpus matches JTBD/real-posting structure (research: 700-2000 chars, ~8 quals, 5-10
responsibility bullets) instead of the old 162-char curated blurbs that gamed grounding.

Improvements (iter6, research-driven):
  - In-Demand tools first, then Hot Technology, then rest (closest free proxy for the
    employer-demand frequency signal that Lightcast has but O*NET lacks).
  - Singularized titles ("an Electrician", not "a Electricians").
  - Crisp education/experience by Job Zone (not O*NET's verbose explanatory sentences).
  - Ground-truth `requirements` column per posting for precise gap scoring.

    python scripts/generate_synthetic_jobs.py --sample   # print 2 sample postings
    python scripts/generate_synthetic_jobs.py            # write both corpora
"""
import csv, zipfile, sys
from collections import defaultdict
from pathlib import Path
from app.skills.onet_requirements import occupation_for

ROOT = Path(__file__).resolve().parent.parent
ZIP = str(ROOT / "data/skills/raw/db_30_3_text.zip")

# Job Zone -> crisp (education, experience). Replaces O*NET's verbose explanatory text.
ZONE_REQ = {
    "1": ("High school diploma or equivalent", "little to no prior experience"),
    "2": ("High school diploma; some vocational training or certification", "some prior experience"),
    "3": ("Associate's degree or vocational training plus apprenticeship", "1-2 years of relevant experience"),
    "4": ("Bachelor's degree", "2-4 years of relevant experience"),
    "5": ("Graduate or professional degree", "5+ years of relevant experience"),
}
COMPANIES = ["Northbridge Health", "Capital One", "Turner Construction", "Meridian Logistics",
             "Brightpath Solutions", "Summit Financial", "Cedar Ridge Care", "Vantage Retail",
             "Onyx Technologies", "Harborview Systems", "Pinnacle Services", "Greenfield Manufacturing"]
LOCATIONS = ["Columbus, OH", "Austin, TX", "Charlotte, NC", "Denver, CO", "McLean, VA",
             "Phoenix, AZ", "Atlanta, GA", "Nashville, TN", "Remote", "Chicago, IL"]
SAL_BY_ZONE = {"1": "32,000-45,000", "2": "40,000-62,000", "3": "55,000-82,000",
               "4": "78,000-118,000", "5": "110,000-160,000"}


def _rows(fn):
    data = zipfile.ZipFile(ZIP).read("db_30_3_text/" + fn).decode("utf-8", "replace").splitlines()
    return list(csv.DictReader(data, delimiter="\t"))


OCC = {r["O*NET-SOC Code"]: (r["Title"], r["Description"]) for r in _rows("Occupation Data.txt")}
CORE = defaultdict(list)
for r in _rows("Task Statements.txt"):
    if r.get("Task Type") == "Core":
        CORE[r["O*NET-SOC Code"]].append(r["Task"])
SOFT = defaultdict(list)  # code -> [(name, in_demand, hot)]
for r in _rows("Software Skills.txt"):
    SOFT[r["O*NET-SOC Code"]].append(
        (r["Workplace Example"], r.get("In Demand") == "Y", r.get("Hot Technology") == "Y"))
KNOW = defaultdict(list)
for r in _rows("Knowledge.txt"):
    if r.get("Scale ID") == "IM":
        KNOW[r["O*NET-SOC Code"]].append((r["Element Name"], float(r["Data Value"])))
ZONE = {r["O*NET-SOC Code"]: r["Job Zone"] for r in _rows("Job Zones.txt")}


def _singular(title):
    # O*NET titles are plural ("Electricians"); make a clean singular for a posting.
    t = title.split(",")[0]  # drop ", All Other" etc.
    if t.endswith("ies"):
        return t[:-3] + "y"
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _article(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def _dedup(seq):
    seen, out = set(), []
    for x in seq:
        k = x.lower().strip()
        if k and k not in seen:
            seen.add(k); out.append(x)
    return out


def _tools(code, n):
    """In-Demand first, then Hot, then the rest — the employer-demand proxy."""
    items = SOFT.get(code, [])
    ranked = ([n_ for n_, d, h in items if d] + [n_ for n_, d, h in items if h and not d]
              + [n_ for n_, d, h in items if not d and not h])
    return _dedup(ranked)[:n]


def compose(code, company, location, salary, source="LinkedIn", seniority=""):
    raw_title, desc = OCC[code]
    title = f"{seniority} {_singular(raw_title)}".strip()
    tasks = CORE.get(code, [])[:6]
    req_tools = _tools(code, 5)
    pref_tools = [t for t in _tools(code, 9) if t not in req_tools][:4]
    # Domain knowledge areas (O*NET) = the realistic skill language real postings carry beyond software
    # (e.g. "Economics and Accounting", "Building and Construction", "Medicine and Dentistry").
    know = [k for k, _ in sorted(KNOW.get(code, []), key=lambda x: -x[1])][:5]
    edu, exp = ZONE_REQ.get(ZONE.get(code, "4"), ("Bachelor's degree", "2-4 years of relevant experience"))

    body = [f"{company} is hiring {_article(title)} {title} in {location}. {desc}", "", "Responsibilities:"]
    body += [f"- {t}" for t in tasks]
    body += ["", "Required qualifications:", f"- {edu}; {exp}"]
    if req_tools:
        body.append("- Proficiency with " + ", ".join(req_tools))
    if know:
        body += ["", "Core knowledge areas:"] + [f"- {k}" for k in know]
    if pref_tools:
        body += ["", "Preferred qualifications:", "- Experience with " + ", ".join(pref_tools)]
    # ground-truth label = distinctive tools + domain knowledge (the realistic, gap-worthy requirements)
    requirements = _dedup(req_tools + know)
    return {
        "title": title, "company": company, "location": location, "salary": salary,
        "description": "\n".join(body), "requirements": "; ".join(requirements),
        "url": f"https://example.com/jobs/{code}", "date_posted": "2026-06-01", "source": source,
    }


def build_corpus(titles, out_path, n_per=2):
    """Map each target title -> O*NET occupation, generate n_per varied postings per unique
    occupation, write CSV. Returns (n_postings, n_occupations)."""
    codes = {}
    for t in _dedup(titles):
        code, occ_t, conf = occupation_for(t)
        codes.setdefault(code, occ_t)  # dedup by occupation
    cols = ["title", "company", "location", "salary", "description", "requirements", "url", "date_posted", "source"]
    rows, i = [], 0
    for code in codes:
        zone = ZONE.get(code, "4")
        for j in range(n_per):
            company = COMPANIES[i % len(COMPANIES)]
            location = LOCATIONS[(i + j) % len(LOCATIONS)]
            rows.append(compose(code, company, location, SAL_BY_ZONE.get(zone, "78,000-118,000")))
            i += 1
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return len(rows), len(codes)


if __name__ == "__main__":
    if "--sample" in sys.argv:
        for q, comp, loc, sal in [("Home Health Aide", "Cedar Ridge Care", "Phoenix, AZ", "32,000-45,000"),
                                  ("Software Developer", "Onyx Technologies", "Austin, TX", "95,000-140,000")]:
            code, t, conf = occupation_for(q)
            print(f"\n{'='*70}\nQUERY: {q} -> {code} {t} (conf {conf})\n{'='*70}")
            print(compose(code, comp, loc, sal)["description"])
        sys.exit(0)

    from tests.persona_evaluation.personas import ALL_PERSONAS
    sw = _dedup([t for p in ALL_PERSONAS for t in (p.target_job_titles or [])])
    st = _dedup([t for p in ALL_PERSONAS for t in (p.stay_in_field_titles or [])])
    n1, o1 = build_corpus(sw, str(ROOT / "data/synthetic/synthetic_jobs.csv"))
    n2, o2 = build_corpus(st, str(ROOT / "data/synthetic/synthetic_jobs_stayinfield.csv"))
    print(f"switching corpus: {n1} postings / {o1} occupations")
    print(f"stay-in-field corpus: {n2} postings / {o2} occupations")
