"""
Semantic role -> O*NET-SOC matcher. Naive substring matching mis-maps titles
(Nurse -> Health Informatics, Data Scientist -> InfoSec); embed the 1016 O*NET
occupation titles with the pipeline's bge model and take nearest-cosine instead.

This is the critical enabler for authoritative skill-gap blind spots: a wrong
occupation -> wrong requirements. Reuses the existing embedder (no new dep).

    python scripts/onet_occupation_match.py
"""
import zipfile, csv
import numpy as np
from app.retrieval.embeddings import embed_texts

Z = "data/skills/raw/db_30_3_text.zip"


def _rows(fn):
    data = zipfile.ZipFile(Z).read("db_30_3_text/" + fn).decode("utf-8", "replace").splitlines()
    return list(csv.DictReader(data, delimiter="\t"))


_occ = [(r["O*NET-SOC Code"], r["Title"]) for r in _rows("Occupation Data.txt")]
_codes = [c for c, _ in _occ]
_titles = [t for _, t in _occ]
_emb = np.array(embed_texts(_titles))  # normalized -> cosine == dot


def match(query, k=1):
    qv = np.array(embed_texts([query])[0])
    sims = _emb @ qv
    idx = sims.argsort()[::-1][:k]
    return [(_codes[i], _titles[i], round(float(sims[i]), 3)) for i in idx]


if __name__ == "__main__":
    # persona target roles spanning tech + non-tech; expected SOC in comments
    probes = [
        ("Registered Nurse", "29-1141.00"),
        ("Data Scientist", "15-2051.00"),
        ("Electrician", "47-2111.00"),
        ("Financial Analyst", "13-2051.00"),
        ("Talent Acquisition Manager", "13-1071.00"),
        ("Clinical Informatics Specialist", "15-1211.01"),
        ("Supply Chain Manager", "11-3071.0x"),
        ("Technical Writer", "27-3042.00"),
    ]
    for q, want in probes:
        top = match(q, 2)
        hit = "OK " if top[0][0].startswith(want.rstrip("x")[:6]) else "??"
        print(f"{hit} {q:32} -> {top[0][0]} {top[0][1]:42} ({top[0][2]})  | 2nd: {top[1][1]}")
