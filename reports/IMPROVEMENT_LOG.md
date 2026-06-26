# Improvement Loop — Hypothesis-Driven Development Journal

Autonomous quality-improvement loop against the eval metrics. Every iteration records a
falsifiable **hypothesis**, its **rationale**, the **method**, the **result**, and the
**decision** (adopt / reject / park). Companion to [README.md](README.md) (the injection-point map).

## Mandate & constraints (set 2026-06-26)
- **Goal:** raise `overall = job*0.3 + rec*0.4 + spot*0.3` across the 2×2 (switching/stay × synthetic/Adzuna) **without overfitting** — every change evaluated on all 4 cells, never tuned to individual personas.
- **Stop:** diminishing returns (<~0.05 mean overall gain) **or** $30–45 RunPod spent.
- **Rubric:** FIXED target; I may *flag* flaws but not change scoring to inflate.
- **Latitude:** moderate→broad. Prefer **US-developed models**; model swaps allowed if clearly better, but must be **flagged**. Freeware deps OK if safe/reputable.
- **Compute:** HYBRID — free local CPU screens for iteration; serverless (paid) only to confirm a winner. `gpuCount=4`/worker can't be changed via API (dashboard only) → serverless is ~4× costlier than needed; lean on local screens.

## Current stack (provenance)
| Component | Model | Origin | US? |
|---|---|---|---|
| LLM (agents) | llama3.1:8b | Meta | ✅ |
| Embedding | BAAI/bge-small-en-v1.5 | Beijing Academy of AI | ❌ |
| Reranker | bge-reranker-v2-m3 | Beijing Academy of AI | ❌ |

## ⚠️ Measurement notes / known confounds
- **C-1 (cosine-calibration confound).** `matcher.py:209` sets `job["score"] = 1 - cosine_distance` (raw **embedding** cosine; the cross-encoder reranks order but does NOT overwrite this). The job rubric (`evaluation_scoring.py:309`) buckets that cosine with **bge-calibrated** thresholds (0.74/0.68/0.62). ⇒ **`avg_job_score` is NOT comparable across embedding models** — a different model's cosine scale shifts the buckets independent of real relevance. For any embedding swap, judge with a **model-agnostic** metric (field-relevance@5), and re-baseline `overall` after adopting. Flagged per "fixed rubric" rule; not silently optimized through.

---

## Iteration 1 — US-developed embedding model (retrieval)
**Status:** in progress.

**Discover.** Map so far (canonical `ab2_`): retrieval-expansion helps job (+0.13…+0.29), ~neutral overall; strategist-prompt and resume-prompt levers dead; rerank/validate pending (`b8rncg7dz`). Lowest scores = blind-spot grounding/spot on Adzuna. Biggest rubric weight = rec (0.4). Stack audit shows the **embedding + reranker are Chinese (BAAI)** while the user prefers US models — so a US embedding swap is both an alignment win and targets retrieval (the one lever that demonstrably works).

**Hypothesis H1.** A US-developed embedding model (candidates: Nomic Embed Text v1.5 — Nomic AI, NYC, Apache-2; or Snowflake Arctic-Embed — Snowflake, US, Apache-2) retrieves **at least as field-relevant** a top-5 as BAAI bge-small, on local CPU, generalizing across all 4 cells. If true → adopt (US-aligned, equal-or-better retrieval). If clearly worse → keep bge, flag.

**Method.** Free local screen `scripts/screen_retrieval.py`: per (variant × corpus), ingest jobs with model M (CPU), retrieve top-5 per persona, score **field-relevance@5** (model-agnostic: fraction of top-5 whose description contains a persona target-field token — the rubric's `field_match`, decoupled from the cosine bucket). Compare bge vs US candidates. No LLM, no serverless → $0. Decision rule: adopt if mean field-relevance@5 ≥ bge across cells; confirm the winner's full `overall` on one serverless 2×2 (with job thresholds re-calibrated to its cosine distribution, flagged).

**Result.** Screen working. **Baseline — BAAI/bge-small-en-v1.5** (rerank=bge-reranker-v2-m3, CPU), field-relevance@5:

| cell | n_jobs | field_rel@5 | cos p25/p50/p75 |
|---|---|---|---|
| switch_synth | 107 | 0.719 | 0.61/0.66/0.69 |
| stay_synth | 80 | 0.763 | 0.62/0.68/0.72 |
| switch_adz | 231 | 0.772 | 0.60/0.64/0.67 |
| stay_adz | 198 | 0.912 | 0.66/0.68/0.73 |
| **mean** | | **0.792** | — |

(bge cosines cluster around the rubric thresholds 0.62/0.68/0.74 → calibration is bge-specific, as expected.) US candidates must match/beat **0.792** mean to justify a swap. All models screened with the SAME no-prefix treatment bge gets (fair drop-in).

**Full comparison (mean field-relevance@5, local CPU, $0):**
| model | origin | params | mean field_rel@5 | cos p50 range | verdict |
|---|---|---|---|---|---|
| BAAI/bge-small-en-v1.5 | China | 33M | **0.792** | 0.64–0.69 | incumbent |
| Snowflake/arctic-embed-m-v1.5 | **US** | 109M | 0.786 | 0.47–0.61 | tie; needs recalibration (low cos) |
| nomic-ai/nomic-embed-text-v1.5 | **US** | 137M | 0.783 | 0.63–0.71 | tie; cos ~bge-compatible |

**Decision: KEEP bge-small (defer the US swap).** Rationale: (1) **no eval gain** — all US candidates tie-or-slightly-below on the confound-free metric; (2) bge-small is **4× lighter** (33M) → best honors the *hard* "non-compute-heavy / local-CPU" constraint; (3) a parity swap costs threshold recalibration + re-ingest churn for $0 metric movement. **⚑ FLAG for user:** this trades against your US-provenance preference. If US-provenance is a *hard* requirement, **Nomic** is the cleanest swap (cosine scale ≈ bge, least recalibration) at retrieval parity + heavier compute — say the word and I'll wire it. **Parked:** prefer US models for any future component where they're ≥ incumbent. (Not pursued: per-model query-prefix tuning — possible small upside, low priority vs budget.)

**Outcome:** iteration produced no eval improvement (valid negative). Embedding is not the lever. Feed back → Iteration 2 targets rec/spot headroom. Screen tool + baseline retained for all future retrieval experiments.
