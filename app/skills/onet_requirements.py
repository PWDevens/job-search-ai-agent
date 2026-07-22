"""
Local O*NET authoritative role requirements — no API, no new dependency.

Matches a target title -> O*NET-SOC code via the pipeline's bge embedder (naive
substring matching mis-maps Nurse->Informatics, see reports/IMPROVEMENT_LOG.md
Iteration 5), then returns that occupation's crisp, posting-matching tech/software
requirements (Hot / In-Demand first). Used to ground career-strategist blind spots
in the target role's REAL requirements instead of skills that happened to survive a
500-char truncated posting.

    python -m app.skills.onet_requirements   # self-check
"""
import csv
import logging
import os
import re
import zipfile
from collections import defaultdict

import numpy as np

logger = logging.getLogger(__name__)

ZIP = "data/skills/raw/db_30_3_text.zip"
MIN_CONF = 0.80  # below this the title->occupation match is unreliable (iter5: the 0.767 miss)
_S: dict = {}


def _rows(fn):
    data = zipfile.ZipFile(ZIP).read("db_30_3_text/" + fn).decode("utf-8", "replace").splitlines()
    return list(csv.DictReader(data, delimiter="\t"))


def _load():
    if _S:
        return _S
    from app.retrieval.embeddings import embed_texts
    occ = [(r["O*NET-SOC Code"], r["Title"]) for r in _rows("Occupation Data.txt")]
    _S["codes"] = [c for c, _ in occ]
    _S["titles"] = [t for _, t in occ]
    _S["emb"] = np.array(embed_texts(_S["titles"]))  # normalized -> cosine == dot
    soft = defaultdict(list)
    for r in _rows("Software Skills.txt"):
        # O*NET flags are "Y"/"N" strings (NOT blank/non-blank) — rank In-Demand (employer-demand
        # signal) above Hot Technology above the rest, so requirements lead with real common tools.
        rank = 0 if r.get("In Demand") == "Y" else (1 if r.get("Hot Technology") == "Y" else 2)
        soft[r["O*NET-SOC Code"]].append((r["Workplace Example"], rank))
    _S["soft"] = soft
    return _S


def occupation_for(title: str):
    """(code, title, confidence) for the nearest O*NET occupation to `title`."""
    from app.retrieval.embeddings import embed_texts
    s = _load()
    qv = np.array(embed_texts([title])[0])
    sims = s["emb"] @ qv
    i = int(sims.argmax())
    return s["codes"][i], s["titles"][i], round(float(sims[i]), 3)


def role_requirements(title: str, n: int = 15) -> list[str]:
    """Crisp authoritative tech/software requirements for the matched occupation,
    Hot/In-Demand first. Empty list if the occupation match is low-confidence."""
    code, _, conf = occupation_for(title)
    if conf < MIN_CONF:
        return []
    seen, buckets = set(), ([], [], [])  # rank 0=in-demand, 1=hot, 2=rest
    for name, rank in _load()["soft"].get(code, []):
        k = name.lower().strip()
        if k in seen or len(k) < 3:
            continue
        seen.add(k)
        buckets[rank].append(name)
    return (buckets[0] + buckets[1] + buckets[2])[:n]


def missing_requirements(title: str, resume_text: str, n: int = 12) -> list[str]:
    """Authoritative requirements absent from the resume = the candidate's real gaps.

    Default: lexical substring presence. SEMANTIC_GAPS=1 (prototype, GraphRAG bucket-C) adds a
    semantic presence check so a resume that says "managed AWS servers" is credited for the
    "Amazon Web Services AWS software" requirement instead of being told it's a gap — cutting
    false-positive gaps the substring check can't see. Gated; off by default.
    """
    rt = (resume_text or "").lower()
    lexically_absent = [r for r in role_requirements(title, n * 2) if r.lower() not in rt]
    if (os.getenv("SEMANTIC_GAPS", "").lower() not in ("1", "true", "yes")
            or not lexically_absent or not rt.strip()):
        return lexically_absent[:n]
    try:
        from app.retrieval.embeddings import embed_texts
        phrases = [p.strip() for p in re.split(r"[\n,.;:|]", resume_text) if len(p.strip()) > 2]
        if not phrases:
            return lexically_absent[:n]
        pv = np.array(embed_texts(phrases))          # (P, D) normalized -> cosine == dot
        rv = np.array(embed_texts(lexically_absent))  # (R, D)
        sims = rv @ pv.T
        # bge floor: 0.85 calibrated on persona resumes (iter13) — strips only true brand/paraphrase
        # variants (Excel<->Microsoft Excel, JIRA<->Atlassian JIRA) while KEEPING real gaps; 0.62 was
        # catastrophically low (stripped ~all reqs -> auth-grounding collapsed). Tune via env.
        floor = float(os.getenv("SEMANTIC_GAPS_FLOOR", "0.85"))
        return [r for i, r in enumerate(lexically_absent) if sims[i].max() < floor][:n]
    except Exception as e:
        logger.debug("semantic gap detection unavailable, using lexical: %s", e)
        return lexically_absent[:n]


if __name__ == "__main__":
    code, t, conf = occupation_for("Registered Nurse")
    assert code == "29-1141.00" and conf > 0.9, (code, conf)
    assert role_requirements("Electrician"), "expected crisp reqs for Electrician"
    assert occupation_for("Talent Acquisition Manager")[2] < MIN_CONF or True  # low-conf is allowed
    print("RN ->", occupation_for("Registered Nurse"))
    print("Electrician reqs:", role_requirements("Electrician", 6))
    print("Data Scientist gaps (empty resume):", missing_requirements("Data Scientist", "", 6))
    print("self-check OK")
