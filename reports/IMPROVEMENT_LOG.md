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

---

## Iteration 2 — Combine retrieval + validate
**Status:** in progress.

**Discover.** The completed levers run (clean, 0×402) closed the injection-point map:
graph data helps in embedding/filter space — **retrieval expansion → job ↑** (+0.13…+0.29),
**graph-as-validator → spot ↑** (+0.16/+0.15/−0.05/+0.11, +0.05 mean overall) — and dies in
generation prompts. Crucially, retrieval-alone's overall gain was *eaten by a spot drop*
(changing retrieved jobs perturbs strategist grounding); validate independently *lifts* spot.

**Hypothesis H2.** Enabling **`GRAPH_RETRIEVAL` + `GRAPH_VALIDATE` together** nets a real overall
gain across the 2×2: retrieval raises job, validate raises spot and offsets retrieval's spot
coupling. Falsifiable: if combined overall Δ vs off is ≤ ~0 or below validate-alone, the levers
interfere rather than compose.

**Method.** Serverless 2×2, **paired off vs retrieval+validate** in one run (greedy, `--temp 0`,
`ab4_` namespace), 8 evals (economical — 2 conditions not 4). Zombie-swept first. Decision: adopt
both as defaults if combined overall Δ ≥ +0.05 mean AND positive in ≥3/4 cells; else keep validate
only (its standalone tentative-adopt) and flag interference.

**Result.** Paired off vs retrieval+validate (clean, 0 persistent 402; transient 402s recovered by retry):

| cell | off | combo | Δ |
|---|---|---|---|
| switch_synth | 2.01 | 2.13 | +0.12 |
| stay_synth | 1.87 | 2.04 | +0.17 |
| switch_adz | 1.62 | 1.50 | −0.12 |
| stay_adz | 1.66 | 1.69 | +0.03 |
| **mean** | | | **+0.05** |

**Decision.** H2 partially supported: combo is +0.05 / 3-of-4 — but **equal to validate-alone**, not additive. Retrieval's job-gain doesn't survive into the composite (spot coupling + variance; switch×Adz −0.12). **Adopt `GRAPH_VALIDATE` as default** (commit pending) — the loop's one validated win (+0.05 mean overall, consistent across two runs, lifts spot, no-op without the graph). **Keep `GRAPH_RETRIEVAL` opt-in** — it genuinely improves job-match retrieval quality (a real product good) but is neutral on `overall`, so not defaulted. ⚑ Flag: +0.05 sits near the GPU-noise floor; firm up with repeats when budget allows.

**Outcome:** landed +0.05 mean overall (validate default-on). Loop now **budget-gated** — see below.

---

## Iteration 3 — Field-diverse few-shot exemplars
**Status:** in progress. **Serverless budget from here: ≤$25, then CPU.** (Idle burn check: `workersMin=0` already → no always-on billing; `gpuCount=4`/worker is dashboard-locked, can't reduce via API; only lever is run size. ~$4–6 per 8-eval 2×2 → ~4 runs affordable.)

**Discover.** Composite drag = spot (lowest dim) + 45–73% Adzuna fallback (agents' output discarded → heuristic scored). `PROMPT_FEWSHOT` exemplars exist but were **tech-biased** (AWS/K8s/ML) — a generalization hazard for non-tech stay-in-field personas. Rewrote them **field-diverse** (tech + healthcare + trades + finance), modelling grounded-output *structure* (cite the postings, name the gap, remediation, timeline), generic employers only — not persona answers.

**Hypothesis H3.** Enabling field-diverse few-shot (on top of the validate default) teaches the agents to ground/cite better → **lower fallback** and higher rec/spot quality, **generalizing** across both switching (tech) and stay-in-field (non-tech) cells. Falsifiable: if overall Δ ≤ ~0, or if it helps switching but hurts stay-in-field (bias not fixed), reject.

**Method.** Serverless 2×2, paired **off (validate default) vs few-shot** (`PROMPT_FEWSHOT=1`), greedy, `ab5_` namespace, 8 evals (~$5; run 1 of ≤$25). Decision: adopt if overall Δ ≥ +0.05 mean AND not negative on any stay-in-field cell (generalization guard).

**Result.** Paired off (validate default) vs few-shot, clean (0×402):

| cell | off | few-shot | Δ |
|---|---|---|---|
| switch × synth | 2.00 | 1.98 | −0.02 |
| stay × synth* | 1.95 | 2.10 | **+0.16** |
| switch × Adz | 1.57 | 1.58 | +0.01 |
| stay × Adz* | 1.66 | 1.76 | **+0.10** |
| **mean** | 1.795 | **1.856** | **+0.061** |

(* = non-tech stay-in-field, generalization guard.)

**Decision: ADOPT — `PROMPT_FEWSHOT` default ON.** +0.061 mean overall; **generalization guard passed** — the non-tech cells are the *biggest* gainers (+0.16/+0.10), confirming the field-diverse rewrite removed the tech bias; no cell regressed (switch×synth −0.02 = noise). Cost: few-shot tokens add ~small per-call context (acceptable for the gain). Cumulative loop gain so far ≈ **+0.11 overall** (validate +0.05 → few-shot +0.061 on top). Spend: ~$5 (run 1 of ≤$25); ~$20 left.

**Outcome:** second win banked. Feed back → Iteration 4 targets the structural fallback drag (45–73% on Adzuna → LLM output discarded for heuristic).

---

## Iteration 4 — fallback is a non-lever (discovery) → confirm stack + retest retrieval
**Discover finding (free, code+log read).** `_run_with_grounding` **never discards agent output** —
it keeps the best result and scores it; grounding-ratio<0.5 only sets a validation flag. Only true
agent **exceptions** swap in the heuristic. Measured in the clean iter-3 set: **1 real exception vs
77 grounding re-asks across 288 agent runs** → "fallback_used" (45–73%) is ~entirely a grounding-quality
flag, NOT output-discard. **⇒ reducing fallback would not move `overall`** (output already scored).
Fallback-gate iteration abandoned before spend. (Flag: `fallback_used` is a misleading metric name —
it's "≥1 agent had imperfect grounding," not "heuristic used.")

**Hypothesis H4.** (a) The chained cumulative gain (validate +0.05 → few-shot +0.061, measured on
different noisy baselines) holds up when measured **original-baseline vs shipped-stack in one clean run**;
(b) retrieval, neutral on the *old* baseline, may now compose on the improved stack (few-shot/validate
stabilize spot, so retrieval's job-gain could survive into overall).

**Method.** One serverless 2×2, 3 paired conditions per cell — `base0` (`GRAPH_VALIDATE=0 PROMPT_FEWSHOT=0`),
`shipped` (current defaults), `shipped+ret` (`GRAPH_RETRIEVAL=1`) — greedy, `ab6_` namespace, 12 evals
(~$7 of remaining ~$20). Decision: confirm cumulative Δ (base0→shipped); adopt retrieval if shipped+ret
≥ shipped by +0.05 mean AND no stay-in-field regression.

**Result.** One clean run, 3 paired conditions/cell (0×402):

| cell | base0 | shipped | +ret |
|---|---|---|---|
| switch × synth | 2.21 | 1.84 (**−0.38**) | 1.91 |
| stay × synth* | 1.90 | 2.04 (+0.13) | 1.98 |
| switch × Adz | 1.62 | 1.64 (+0.02) | 1.74 |
| stay × Adz* | 1.73 | 1.70 (−0.03) | 1.71 |
| **mean** | **1.867** | **1.803 (−0.063)** | 1.836 (+0.032 vs shipped) |

**Decision — the critical finding: I've been measuring noise.** `switch×synth base0=2.21` exceeds *every*
prior reading of that cell (2.00–2.14) — a lucky GPU draw. Each condition is a **separate `eval_compare`
process** hitting **different workers in a heterogeneous GPU fleet**, and greedy decoding isn't
bit-reproducible across GPU types → **every paired delta carries ~±0.2/cell noise**, which **swamps the
~+0.05 lever effects.** The iter-2/3 "+0.05/+0.061" were within that noise; this fresh base0-vs-shipped
(also noisy, one −0.38 outlier) can neither confirm nor refute them. Even serverless `repeats=3` can't
resolve a +0.05 effect against ±0.2 SD within the remaining budget; no local GPU + Ollama-not-serving
rules out a fast deterministic CPU run.

**⇒ Per the mandate (no overfitting, test against goal): REVERTED `GRAPH_VALIDATE` and `PROMPT_FEWSHOT`
to opt-in defaults.** Not honest to ship them as defaults on within-noise evidence when a clean test
came out slightly negative. Code, infra, and the improved field-diverse examples are kept — enable via
env (`GRAPH_VALIDATE=1`, `PROMPT_FEWSHOT=1`) once deterministic measurement is available.

---

## 🏁 Loop conclusion (2026-06-26)
**Stop trigger:** diminishing returns — lever effect sizes (~+0.05) fell **below the measurement noise
floor** (~±0.2/cell on the heterogeneous GPU serverless fleet at repeats=1), and that floor can't be
lowered within the budget/compute available (no local GPU; repeats too costly). ~$13 of the ≤$25 unspent.

**Confirmed, durable findings (large effects / free / robust):**
- Occupation-graph injection map: graph data helps in **embedding/filter space** (retrieval→job +0.13…+0.29;
  validate→spot), **dies in generation prompts** (strategist, resume). (README map.)
- **US embedding swap = parity** (Arctic/Nomic ≈ bge-small on free field-relevance@5); bge kept (lighter). US-swap is a provenance-only call, flagged.
- **`fallback_used` is a non-lever** — agent output is always scored (1 real exception vs 77 grounding re-asks/288 runs); the metric name is misleading.
- **Methodology:** the eval cannot resolve sub-~0.2 effects at repeats=1 on a heterogeneous fleet. Validate/few-shot are mechanism-sound and mildly-positive in most paired cells but **unconfirmable** at this precision.

**To resume with real measurement (recommended next):** pin a **single GPU type** on the endpoint (homogeneous
→ greedy reproducible) OR run deterministic **local CPU** evals (needs Ollama + llama3.1:8b pulled locally),
then re-test validate / few-shot / retrieval with `repeats≥3`. New durable tooling left behind:
`scripts/screen_retrieval.py` (free local retrieval screen) + this journal.

---

## ✅ Deterministic confirmation — DEFINITIVE (2026-06-26, dedicated pod)
The noise floor WAS beaten. After three dead ends — heterogeneous serverless (noisy), single-GPU
serverless (Low-stock A4000 → allocation scarcity; fresh-endpoint cold-start churn even on High-stock
4090), and local CPU (phi4-mini too slow on 5k-token prompts) — the working instrument was a
**dedicated single-GPU pod**: `ollama/ollama` image on 1× RTX 4090, `OLLAMA_HOST=0.0.0.0`, port 11434,
`ollama pull llama3.1:8b` via the proxy, eval pointed at `OLLAMA_BASE_URL=https://<pod>-11434.proxy.runpod.net`.
A pod **pulls once and stays up** (no worker cycling) and is **one fixed GPU** (greedy bit-reproducible —
verified: two identical calls → identical output). Run: sequential, **0 fallbacks across all 88+88 personas**.

**Per-lever attribution (Δ overall vs off, deterministic, scenario 9 / llama3.1:8b):**
| cell | off | Δ validate | Δ few-shot | Δ both |
|---|---|---|---|---|
| switch×synth | 2.205 | −0.242 | −0.177 | −0.086 |
| stay×synth | 2.200 | +0.045 | −0.085 | +0.127 |
| switch×Adz | 1.600 | −0.011 | +0.104 | +0.043 |
| stay×Adz | 1.671 | +0.022 | +0.010 | +0.051 |
| **MEAN** | | **−0.047** | **−0.037** | **+0.034** |

**The finding (only visible with clean data): a synergistic interaction.** Each lever ALONE *hurts*
(validate −0.047, few-shot −0.037); only TOGETHER do they help (+0.034) — few-shot's grounding structure +
validate's relevance-filtering combine to yield grounded *and* on-target blind spots. Switching-synthetic
still regresses even combined (−0.086).

**Definitive verdict — `GRAPH_VALIDATE` + `PROMPT_FEWSHOT` stay OPT-IN:** you cannot adopt either alone
(each degrades overall), and the combined gain (+0.034) is marginal and non-uniform. The earlier
conservative revert is now backed by clean per-lever proof, not a guess. **Reusable recipe:** the pod
method above is the deterministic eval instrument for any future sub-0.1-effect A/B (deleted after use to
stop billing; ~$0.69/hr, ~$4 total for the two pod runs). Total improvement-loop spend ≈ **$18–20**.
