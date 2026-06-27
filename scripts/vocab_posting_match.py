"""
Free, local validation (improvement loop): does a skills VOCABULARY's terms actually
appear in real job-posting text? This is the root-cause test for the skills layer —
ESCO labels are verbose competence phrases that DON'T match posting tokens; O*NET's
"Software Skills" workplace examples are crisp tokens extracted from postings.

Metric: % of unique vocab terms that are "groundable" = appear in the Adzuna corpus
(single-word term -> must be a corpus token; multi-word -> phrase substring). Higher =
the agents can actually cite these skills in blind spots / resume recs. No LLM, $0.

Run: python scripts/vocab_posting_match.py
"""
import zipfile, csv, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADZ = [ROOT / "data/adzuna/jobs_pre.csv", ROOT / "data/adzuna/jobs_stayfield.csv"]
ZIP = ROOT / "data/skills/raw/db_30_3_text.zip"
ESCO = ROOT / "data/skills/raw/esco_relations.csv"

# --- build the posting corpus ---
posts = []
for f in ADZ:
    if not f.exists():
        continue
    for r in csv.DictReader(open(f, encoding="utf-8")):
        posts.append(((r.get("title") or "") + " " + (r.get("description") or r.get("document") or "")))
corpus = " ".join(posts).lower()
words = set(re.findall(r"[a-z0-9][a-z0-9+#.]*", corpus))
print(f"corpus: {len(posts)} postings, {len(corpus):,} chars, {len(words):,} unique tokens\n")


def groundable(terms, min_len=3):
    seen, found = [], []
    for t in terms:
        t = (t or "").strip().lower()
        if len(t) < min_len or t in seen:
            continue
        seen.append(t)
        if (" " in t and t in corpus) or (" " not in t and t in words):
            found.append(t)
    return len(seen), found


def onet_col(fn, col):
    rows = zipfile.ZipFile(ZIP).read("db_30_3_text/" + fn).decode("utf-8", "replace").splitlines()
    return [r[col] for r in csv.DictReader(rows, delimiter="\t")]


vocabs = {
    "ESCO skill labels (verbose)":       [r["targetLabel"] for r in csv.DictReader(open(ESCO, encoding="utf-8"))
                                          if r["targetType"] in ("skill/competence", "knowledge")],
    "O*NET Essential Skills (abstract)": onet_col("Essential Skills.txt", "Element Name"),
    "O*NET Knowledge (abstract)":        onet_col("Knowledge.txt", "Element Name"),
    "O*NET Software Skills (crisp)":     onet_col("Software Skills.txt", "Workplace Example"),
}

import statistics
post_lens = [len(p) for p in posts]
print(f"avg posting length: {statistics.mean(post_lens):.0f} chars (~{statistics.mean(post_lens)//6:.0f} words)\n")

# Product-relevant metric: per-posting grounding. For the terms that DO appear in the
# corpus, how many distinct ones land in a typical posting, and what fraction of postings
# get >=1? (Independent of vocab size — fair across vocabs.)
post_tokens = [set(re.findall(r"[a-z0-9][a-z0-9+#.]*", p.lower())) for p in posts]
post_lower = [p.lower() for p in posts]

print(f"{'vocabulary':36} {'found':>6} {'cov/post':>9} {'mean#/post':>11} {'med':>4}")
print("-" * 70)
for name, terms in vocabs.items():
    _, found = groundable(terms)
    single = [t for t in found if " " not in t]
    multi = [t for t in found if " " in t]
    dens, cov = [], 0
    for tok, low in zip(post_tokens, post_lower):
        c = sum(1 for t in single if t in tok) + sum(1 for t in multi if t in low)
        dens.append(c)
        cov += (c > 0)
    mean_d = statistics.mean(dens)
    med_d = statistics.median(dens)
    print(f"{name:36} {len(found):>6} {100*cov/len(posts):>7.0f}% {mean_d:>11.2f} {med_d:>4.0f}")
    print(f"    e.g.: {', '.join(found[:8])}")
