"""Switcher-pivot engine: adjacent occupations a candidate can realistically move into.

First cut of the Causeways concept (see .pipeline/nesta_causeways_spec.md) built on O*NET's own
**Related Occupations** table (US-native, tiered + index-ranked) — which sidesteps the ESCO->SOC
crosswalk the spec flagged as the main risk. Nesta's displacement-risk / feasibility-scoring layer
is the documented upgrade on top of this.

Gated by CAUSEWAYS=1 for A/B; surfaced to the career_strategist in switch mode only.
"""
import zipfile
from collections import defaultdict

from app.skills.onet_requirements import ZIP, occupation_for

# Adjacency is advisory (suggest related roles), so it uses a looser confidence gate than
# requirement injection (0.80): correct matches for verbose titles land 0.776-0.799 (Management
# Consultant->Management Analysts 0.776, Electrician->Electricians 0.784); 0.75 keeps those while
# still rejecting genuine mismatches (CPA->Bookkeeping Clerks 0.672). See iter14 calibration.
ADJ_MIN_CONF = 0.75

_A: dict = {}


def _load():
    if _A:
        return _A
    z = zipfile.ZipFile(ZIP)
    rel = defaultdict(list)  # soc -> [(related_soc, index)]
    for line in z.read("db_30_3_text/Related Occupations.txt").decode("utf-8", "replace").splitlines()[1:]:
        p = line.split("\t")
        if len(p) >= 4:
            rel[p[0]].append((p[1], int(p[3]) if p[3].strip().isdigit() else 999))
    titles = {}  # soc -> title
    for line in z.read("db_30_3_text/Occupation Data.txt").decode("utf-8", "replace").splitlines()[1:]:
        p = line.split("\t")
        if len(p) >= 2:
            titles[p[0]] = p[1]
    _A["rel"] = rel
    _A["titles"] = titles
    return _A


def adjacent_occupations(title: str, k: int = 3) -> list[dict]:
    """Top-k occupations adjacent to `title` by O*NET relatedness (lower index = closer).

    Returns [{soc, title}], or [] when the title->occupation match is too weak to trust.
    """
    code, _, conf = occupation_for(title)
    if not code or conf < ADJ_MIN_CONF:
        return []
    a = _load()
    ranked = sorted(a["rel"].get(code, []), key=lambda x: x[1])[:k]
    return [{"soc": s, "title": a["titles"].get(s, s)} for s, _ in ranked]


if __name__ == "__main__":
    nurse = adjacent_occupations("Registered Nurse", 3)
    print("RN adjacent:", nurse)
    assert nurse, "expected related occupations for a high-confidence title"
    assert all("nurs" in o["title"].lower() or "health" in o["title"].lower()
               or "care" in o["title"].lower() for o in nurse[:1]), nurse
    print("self-check OK")
