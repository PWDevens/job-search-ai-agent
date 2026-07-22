"""
Free, LLM-free local screen for retrieval quality — used by the improvement loop to
compare embedding/reranker changes without spending serverless credits.

Primary metric: field-relevance@5 (model-AGNOSTIC) = fraction of the top-5 retrieved
jobs whose description contains a persona target-field token (the rubric's `field_match`,
decoupled from the cosine bucket — see IMPROVEMENT_LOG confound C-1).
Also reports the top-5 cosine distribution (mean / p25 / p50 / p75) so a swapped
embedding's scale shift is visible (for re-calibrating job thresholds if adopted).

Run (per model, isolated chroma so vectors match the query model):
  EMBED_MODEL=BAAI/bge-small-en-v1.5 CHROMA_DB_PATH=data/chroma_screen_bge \
    python scripts/screen_retrieval.py
No LLM, no serverless. CPU only.
"""
import sys, statistics as st
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.config as cfg
from app.retrieval.client import delete_collection
from app.pipeline.ingest import ingest_jobs
from app.pipeline.matcher import find_top_jobs
from scripts.eval_hardware_matrix import build_rows
from tests.persona_evaluation.evaluation_scoring import EvaluationRubric, targets_for

CELLS = [
    ("switch_synth", "data/synthetic/synthetic_jobs.csv",             "switching"),
    ("stay_synth",   "data/synthetic/synthetic_jobs_stayinfield.csv", "stayinfield"),
    ("switch_adz",   "data/adzuna/jobs_pre.csv",                      "switching"),
    ("stay_adz",     "data/adzuna/jobs_stayfield.csv",                "stayinfield"),
]


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0.0


def main():
    print(f"MODEL={cfg.EMBED_MODEL}  RERANK={cfg.RERANK_MODEL}  CHROMA={cfg.CHROMA_DB_PATH}\n")
    grand_fr = []
    for label, corpus, variant in CELLS:
        try:
            delete_collection(cfg.CHROMA_JOBS_COL)
        except Exception:
            pass
        n = ingest_jobs(corpus)
        rows = [r for r in build_rows(False, variant) if getattr(r[0], "target_job_titles", None)]
        fr, cos = [], []
        for persona, _dataset, role, geo, resume, rv in rows:
            jobs = find_top_jobs(role, geo, resume)
            targets, _ = targets_for(persona, rv)
            for j in jobs[:5]:
                s = EvaluationRubric.score_job_match(j, targets)
                fr.append(1 if s.matches_persona_field else 0)
                cos.append(float(j.get("score", 0) or 0))
        fr_mean = st.mean(fr) if fr else 0
        grand_fr.append(fr_mean)
        print(f"{label:13} n_jobs={n:3} personas={len(rows):2}  "
              f"field_rel@5={fr_mean:.3f}  "
              f"cos[mean/p25/p50/p75]={st.mean(cos):.3f}/{pct(cos,.25):.3f}/{pct(cos,.50):.3f}/{pct(cos,.75):.3f}")
    print(f"\nMEAN field_rel@5 across cells = {st.mean(grand_fr):.3f}")


if __name__ == "__main__":
    main()
