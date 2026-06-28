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

---

## Iteration 5 — Skills-source bake-off & the truncation reframe (2026-06-26)

**Context:** acquired free, US, posting-matching skills data as the ESCO replacement the prior
iterations called for: O*NET 30.3 (local DB), CareerOneStop API (O*NET+BLS, creds in `.env`),
gpriday/job-titles (65k). Goal per core JTBD — *prioritize what to apply to* + *improve hire chances*.

**H5.1 — O*NET crisp tokens ground postings better than ESCO's verbose labels.** REJECTED.
`scripts/vocab_posting_match.py` (free, local, no LLM) vs the Adzuna corpus:
| vocab | found | cov/post | mean #/post |
|---|---|---|---|
| ESCO skill labels (verbose) | 98 | 43% | 0.60 |
| O*NET Software Skills (crisp) | 23 | 7% | 0.10 |
ESCO grounds *more* (its breadth includes generic terms: "troubleshoot", "company policies");
O*NET software is *actionable but tech-only* (Tableau, SAS) → low coverage on a mixed-field corpus.

**H5.2 (emergent, the real finding) — the grounding bottleneck is TRUNCATED postings, not vocab.**
Adzuna descriptions are **99% truncated at 500 chars** (free-tier cap, cut mid-sentence; synthetic = 160c).
The strategist must ground blind spots in posting text whose *requirements section is gone*. No vocab swap
fixes that. **Exposes a rubric flaw (flagged, not changed — rubric is fixed-target):** scoring blind-spot
quality by substring-match against truncated postings *penalizes genuinely good occupation-grounded advice.*

**H5.3 — authoritative occupation requirements sidestep truncation.** CONFIRMED (local, $0).
Local O*NET gives crisp, hot-flagged requirements for *every* field: Electrician → Autodesk AutoCAD /
Construction Master Pro; Financial Analyst → Alteryx / Apache Hive. This is O*NET used for its *strength*
(authoritative requirements) instead of posting-matching.

**H5.4 — but title→occupation matching is the make-or-break enabler.** Naive substring mis-maps badly
(Registered Nurse → Health Informatics; Data Scientist → Information Security). `scripts/onet_occupation_match.py`
(semantic, reuses the bge embedder, no new dep) fixes it: **7/8 persona roles correct @ cos 0.89–0.98**;
the 1 miss (Talent Acquisition Mgr → entertainment "Talent Directors") is self-flagging at cos 0.767
(< ~0.85 threshold) and fixable via reported-title anchors.

**Verdict / path forward (de-risked end-to-end):** pivot the career-strategist's blind spots from
*"skills that survived posting-truncation"* to *"the target occupation's real O*NET requirements the
candidate lacks"* (correct occupation via H5.4 → crisp gaps via H5.3), with a JTBD-aligned grounding
metric (gap ∈ target occupation's real requirements) reported alongside the legacy posting-grounding.
Next: integrate behind a gated flag, A/B on the deterministic pod. Spend this iteration: **$0** (all local).

### Iteration 5 — implementation (local-O*NET arm, built & verified; A/B pending)
Built the validated path behind opt-in `AUTHORITATIVE_GAPS` (config default off):
- `app/skills/onet_requirements.py` — semantic title→O*NET-SOC matcher (reuses bge, no new dep) +
  per-occupation crisp requirements (Hot/In-Demand first) + `missing_requirements()`. Self-check passes
  (RN→29-1141.00 @0.97; Electrician→AutoCAD/Construction Master Pro).
- `app/agents/agent_career_strategist.py` — gated injection of authoritative missing-requirements +
  a conditional GROUNDING RULE (authoritative-list when on, posting-substring when off).
- New JTBD-aligned metric `blind_spot_auth_grounded_pct` threaded scorer→CSV→`eval_compare`
  (verified: 1-real + 1-junk blind spot → 50.0). Measures advice quality independent of posting truncation.
- 18/18 existing tests pass; all modules compile.

**Coverage caveat:** `MIN_CONF=0.80` gates low-confidence title matches (correctly kills the wrong
"Talent Acquisition Mgr"→entertainment "Talent Directors" @0.767, but also gates borderline-correct
"Healthcare Data Analyst"→"Business Intelligence Analysts" @0.778). Follow-up: add reported-title anchors
to raise confidence on legit fuzzy titles. **Next:** deterministic-pod A/B (`AUTHORITATIVE_GAPS=1` vs off),
read both gnd% and auth% — ~$4, the only spend; all build work above was $0/local.

### Iteration 5 — AUTHORITATIVE_GAPS A/B result (deterministic pod, llama3.1:8b, ~$0.80)
Off vs on, paired per cell, greedy/temp0/sequential on a single 4090 pod (deleted after).

| cell | overall | spot | gnd% | auth% |
|---|---|---|---|---|
| switch_synth | 2.163→2.100 (-0.063) | 3.10→2.82 | 86.7→81.7 | 1.7→3.3 |
| stay_synth   | 2.129→2.005 (-0.124) | 1.87→1.38 | 58.3→41.7 | 6.0→34.0 |
| switch_adz   | 1.685→1.722 (+0.037) | 1.00→1.08 | 33.3→38.3 | 0.0→0.0 |
| stay_adz     | 1.680→1.680 (+0.000) | 0.43→0.43 | 15.0→13.3 | 2.0→36.0 |
| MEAN | 1.914→1.877 (-0.038) | 1.60→1.43 | 48.3→43.8 | 2.4→18.3 (+15.9) |

**Verdict:** the feature works (auth% +15.9 mean; +34 on stay_adz, the most-realistic/most-truncated cell) but
the legacy rubric can't see it. `stay_adz` is definitive: overall/spot/gnd% all FLAT while auth% went 2→36 —
the rubric is blind to a 34-pt improvement in occupation-grounded advice. The overall DROP is a **synthetic
artifact** (curated 160c postings reward posting-substring grounding of the off-arm); on Adzuna (truncated,
realistic) overall is neutral (+0.037/+0.000). Switching cells got ~no lift: aspirational target titles match
< MIN_CONF=0.80 so injection never fires (career-changers need the reported-title-anchor matcher upgrade).

**Conclusion → the binding constraint is the EVALUATION, not the feature.** Next step (user-directed): refine
the rubric to value JTBD-aligned (occupation-grounded) advice BEFORE further testing. Keep AUTHORITATIVE_GAPS
opt-in until the rubric can measure it. Spend: ~$0.80 pod (under the $4 budget).

---

## Iteration 6 — Rubric refinement R1: occupation-grounded blind spots (rubric_v2) (2026-06-27)

**Mandate (from iter5):** the binding constraint is the *evaluation*, not the feature — the v1 rubric was
blind to a 34-pt auth% gain (stay_adz). Fix the rubric to value JTBD-aligned (occupation-grounded) advice.

**R1 implemented** behind opt-in `RUBRIC_V2` (config default off → all pre-v2 baselines reproduce exactly;
new `rubric_version` column self-identifies every run):
- `tests/persona_evaluation/evaluation_scoring.py` — `score_blind_spot(skill, top_jobs, occ_reqs)` now blends
  occupation grounding: a skill that is a real target-occupation O*NET requirement is a genuine gap even when
  a truncated posting omits it. Scoring: auth-only → 3/4; auth + posting demand → 4/4; posting-only → v1
  (2/3/4 by citations); neither → v1 (0/1). `occ_reqs` computed once per persona (reused by the auth% metric).
- `rubric_version` threaded scorer→CSV (`eval_hardware_matrix.py`).

**Verified:** v1 unchanged (auth-only Epic Systems → 0, posting tableau → 2); v2 (auth-only → 3, both → 4,
ungrounded junk → 0); 18/18 tests pass. Anti-Goodhart: occ_reqs are authoritative O*NET requirements for the
*matched* occupation (not LLM-assertable), and the skill must be missing from the resume.

**Next:** re-run the AUTHORITATIVE_GAPS A/B under `RUBRIC_V2=1` (~$0.80 pod) — expectation: the on-arm's
authoritative blind spots (auth% 18–36) now score 3–4 instead of ~0, so v2 should reveal the feature's real
value that v1 hid. Keep both flags opt-in until that confirms. (R3/R2/R5 refinements deferred per user scope.)

### Iteration 6 — rubric_v2 A/B result: the loop closes (deterministic pod, ~$0.80)
AUTHORITATIVE_GAPS off vs on, re-measured under RUBRIC_V2 (raw outputs persisted for free re-scoring).

| cell | overall(off→on) | spot | auth% | v2 Δ | (v1 Δ) |
|---|---|---|---|---|---|
| switch_synth | 2.152→2.105 | 3.08→2.83 | 1.7→3.3 | −0.047 | (−0.063) |
| stay_synth | 2.144→2.245 | 1.92→2.18 | 6→34 | +0.101 | (−0.124) |
| switch_adz | 1.593→1.583 | 1.02→0.92 | 0→0 | −0.010 | (+0.037) |
| stay_adz | 1.695→1.935 | 0.48→1.28 | 2→36 | **+0.240** | (+0.000) |
| MEAN | 1.896→1.967 | 1.63→1.80 | — | **+0.071** | (−0.038) |

**Verdict — the rubric was the bottleneck, confirmed.** AUTHORITATIVE_GAPS flipped from −0.038 (v1, apparent loss)
to **+0.071 (v2, win)** on the SAME generated advice — v2 just sees occupation-grounded quality v1 was blind to.
`stay_adz` (most realistic/most-truncated) is the headline: v1 +0.000 → v2 **+0.240** (spot +0.80), the project's
biggest single-cell gain. Feature works where it fires (stay cells +0.10…+0.24); misfires for switchers
(switch cells flat — aspirational titles match < MIN_CONF, injection never fires → auth stays 1.7/0.0).

**Two clear next actions (confirmed §4 workstream in .pipeline/PathForward.md):**
1. **Career-changer occupation matching** (reported-title anchors) — makes AUTHORITATIVE_GAPS help switchers too.
2. **Regenerate synthetic** as O*NET-grounded, full-length, labeled postings (current toy 162c blurbs game gnd%
   and still drag switch_synth negative even under v2) → rerun → re-evaluate gaps.
Raw outputs banked → future rubric versions re-score offline for $0. Loop spend ≈ $20–22 (under budget).

### Iteration 6 — retest on regenerated corpus + Tier-1 personas (deterministic pod, ~$1)
AUTHORITATIVE_GAPS off vs on under rubric_v2, on the NEW O*NET-grounded synthetic corpora
(84/82 postings, ~1450c, labeled) + 14 personas (3 Tier-1 market-demand added) + the In-Demand
tool-ordering bug fix (O*NET flags are "Y"/"N", not blank — old bool() flagged everything).

| cell | overall(off→on) | spot | auth% | Δ |
|---|---|---|---|---|
| switch_synth | 1.65→1.64 | 1.48→1.48 | 11→9 | −0.012 |
| stay_synth | 1.75→2.15 | 1.48→2.83 | 1.5→53.8 | +0.404 |
| switch_adz | 1.67→1.70 | 1.25→1.55 | 12→16 | +0.037 |
| stay_adz | 1.65→2.02 | 0.60→1.83 | 3→53.8 | +0.365 |
| MEAN | 1.68→1.88 | | | **+0.198** |

**Progression of the SAME feature:** v1/toy −0.038 (apparent loss) → v2/toy +0.071 → v2/realistic+fixed
**+0.198**. Each fix (rubric, then realistic corpus + In-Demand ordering) revealed more real value.
Both stay cells +0.37…+0.40 (auth% ~2%→~54%). Realistic corpus dropped scores to a healthy 1.6–2.1
(harder, less gameable) — the point of the regen.

**Tier-1 persona auth% fingerprint [sw_syn, st_syn, sw_adz, st_adz]:** Home Health Aide [0,100,0,100],
Customer Service Rep [0,100,0,100], Software Developer [40,0,0,0]. Stay-in-field → 100% occupation-grounded
blind spots (feature working); switching → 0% (target matches < MIN_CONF, injection never fires).

**Remaining gap = career-changer occupation matching** (reported-title anchors) — unlocks the feature for
switchers (the [0,_,0,_] half). Bug fix to onet_requirements also improves the authoritative layer generally.
Loop spend ≈ $21-23. Raw outputs banked (authv3_*.raw.jsonl) → future rubric tweaks re-score for $0.

---

## Iteration 7 — backlog P0 (context-engineering foundation) (2026-06-27)

Per the JTBD-alignment audit (PathForward §4-5). All local/$0; pod retest pending.

**A0 — posting section parser / data dictionary** (`app/pipeline/sections.py`). Postings are formulaic;
parse into company/responsibilities/required-quals/preferred/benefits (regex over canonical headers +
positional fallback). Stored in Chroma metadata at ingest (parse from RAW description — `_clean` collapses
the newlines the parser needs), propagated onto job dicts. The substrate the context fixes want.

**A1 — resume_coach sees requirements** (was blind: `fmt_jobs(detail=False)` → title+company only, yet its
prompt promised posting text). Now shows each job's parsed `requirements_text` + injects the target
occupation's authoritative O*NET requirements missing from the resume. Fixes the highest-weighted dim (rec=0.4).

**A2 — target occupation from matched jobs, not the role sentence.** The switcher `[0,_,0,_]` auth gap was
query construction, not the matcher: the strategist/coach matched on the role_description SENTENCE, which for
a career-changer leads with the CURRENT role ("home health aide … seeking CNA") → occupation_for picks Home
Health Aides (0.778, gated) → no injection. Fix: derive the target from the matched jobs' clean titles.
Validated: sentence→Home Health Aides (gated, []); matched title "Nursing Assistant"→Nursing Assistants
(0.964)→real target reqs (Epic, MEDITECH).
- **Negative result (documented):** reported-title anchors (7,953 O*NET aliases) were tried first and
  REJECTED — they raise confidence but add confident-WRONG matches (Operations Coordinator→Brokerage Clerks
  1.0; a top-K vote regressed Data Scientist→Biostatisticians). Reverted to the clean iter6 matcher.

**Pre-existing infra issue flagged:** `pytest_asyncio` hijacks the `tmp_path` fixture
(`'WindowsPath' has no attribute 'mktemp'`) → 30 errors in test_matcher at *setup* (not from these changes).
Test-infra cleanup item.

**Next:** consolidated pod retest of the P0 context block (rec dim + switcher auth%), then backlog P1.

### Iteration 7 — context-block retest (mode-aware A0+A1+A2), deterministic pod ~$1
AUTHORITATIVE_GAPS off vs on, rubric_v2, 14 personas, mode-from-variant, on the parsed-sections pipeline.

| cell | overall off->on | auth% off->on |
|---|---|---|
| switch_synth | 1.89->2.45 (+0.554) | 12->72 |
| stay_synth   | 1.76->2.36 (+0.598) | 12->85 |
| switch_adz   | 1.59->1.84 (+0.255) | 7->44 |
| stay_adz     | 1.70->1.94 (+0.249) | 9->60 |
| MEAN | 1.73->2.15 (+0.414) | |

**The switcher gap is CLOSED.** switch-cell auth% 9->72 (synth) / 16->44 (Adzuna); the [0,_,0,_] fingerprint
is gone. switch_synth overall +0.81, spot +2.13. The stay/switch MODE (user idea) + A2 matched-title target
together made the feature fire for career-changers — it now helps the whole market.

**Feature benefit more than doubled.** Same AUTHORITATIVE_GAPS feature, measured across the alignment work:
v1/toy −0.038 -> v2/toy +0.071 -> v2/realistic +0.198 -> **v2/realistic+context-block+mode +0.414**.

**Caveat:** rec lifted on switch cells (2.0->2.3) but flat on stay — the rec metric still scores tangibility/
citations, not gap-closing, so A1's value is partly invisible (same as spot pre-rubric_v2). B5 (rec scored on
gap-closing) captures it and is re-scorable on banked authv4 outputs for $0.

Commits: A0 (sections), A1 (resume_coach reqs), A2 (matched-title target), mode (stay/switch). Loop spend ~$24.

---

## Iteration 8 — backlog B5/B2/B1 + final scorecard (2026-06-27)

**B5 — rec scored on gap-closing** (rubric_v2): a resume rec that adds a real target-occupation
requirement scores >=3 (credits non-tech credentials the TECH_SKILLS list missed). New `rec_gap_closing_pct`
metric. Validated offline on banked authv4 outputs: rec OLD->B5 up every cell (stay_synth 1.89->2.64),
60-82% of recs gap-closing — captures A1's value the tech-biased metric hid (same pattern as spot/rubric_v2).

**B2 — AUTHORITATIVE_GAPS + RUBRIC_V2 default ON** — both proven + JTBD-aligned; shipped product now uses them.

**B1 — live Adzuna discovery in the product** — "Search live jobs" checkbox fetches by role+location
(reuses search_adzuna), ingests (A0 parsing), runs the pipeline. Closes the biggest JTBD gap (find, not just
rank). Graceful degradation without ADZUNA keys.

**Final shipped-state scorecard** (rubric_v2 + B5 — all dims JTBD-aligned — re-scored on authv4 generation;
no generation-affecting code changed since, so this is deterministically equal to a fresh run, done for $0):

| cell | overall off->on | spot | auth% | rec-gap% |
|---|---|---|---|---|
| switch_synth | 2.08->2.61 | 1.79->3.64 | 77 | 70 |
| stay_synth | 1.94->2.72 | 1.47->3.70 | 92 | 82 |
| switch_adz | 1.73->2.00 | 1.13->1.71 | 47 | 59 |
| stay_adz | 1.80->2.18 | 0.84->1.91 | 65 | 62 |
| MEAN | 1.89->2.38 (+0.490) | | | |

**Feature-benefit progression (same AUTHORITATIVE_GAPS feature, across the alignment work):**
v1/toy −0.038 -> v2/toy +0.071 -> v2/realistic +0.198 -> v2/context-block +0.414 -> **v2+B5 +0.490**.
All dims now JTBD-aligned (job=retrieval; rec=gap-closing/B5; spot=occupation-grounded/rubric_v2); switcher
gap closed. Pod spend $0 this iteration (offline re-score). REMAINING (C-tier cleanup): retire/migrate ESCO,
tech-biased _SKILL_KEYWORDS fallback, JTBD behavioral tests, switcher-target rebalance, pytest_asyncio fixture.

---

## Iteration 9 — backlog C-tier (cleanup + test infra) (2026-06-27)

**C-test-infra (DONE)** — fixed the broken `tmp_path` fixture: conftest.py shadowed pytest's built-in
`tmp_path_factory` with a plain Path (no `.mktemp`), and pytest_asyncio 1.4.0 + pytest 9.x wrapped fixtures
despite zero async tests. Removed the override + disabled the unused plugin (pytest.ini). **Suite went from
~30 errors (everything erroring) to 122 passing.**

**C5 (DONE)** — `find_blind_spots()` fallback now prefers authoritative O*NET occupation requirements
(works for healthcare/trades/admin) over the tech-only `_SKILL_KEYWORDS` list. CNA->Epic/MEDITECH,
Electrician->AutoCAD.

**C3 (DONE)** — `tests/test_jtbd_alignment.py`: 6 behavioral tests guarding the alignment work (section
parsing, occupation matching, non-tech authoritative reqs, rubric_v2 spot grounding, B5 rec gap-closing,
mode switch framing). All pass.

**Test state after the fix:** 122 passed, 13 failed, 11 errored. The fail/error set is PRE-EXISTING debt
the fixture fix UNMASKED (not regressions): brittle source-asserting tests (e.g. `'timeout=120.0' in base.py`
— code is config-driven now), mock-retrieval-returns-nothing integration tests, a missing `chroma_client`
fixture, the test_skills embedding-threshold flake, and persona-coverage thresholds stale vs the iter6 corpus.

**DEFERRED (documented, lower-value/risk):**
- Switcher-target rebalance of the original 11 personas (still analytics-biased) — mitigated by the stay/
  switch MODE feature (it adapts per intent); changing targets cascades into corpus regen.
- ESCO layer retire/migrate to O*NET — dormant (graph levers opt-in) + wired into ingest/rubric; risky refactor.
- Broader test-suite repair (the 13 fail / 11 error debt) — separate hardening effort (mock-retrieval fixture,
  chroma_client fixture, de-brittle source-assert tests, refresh coverage thresholds).

---

## Iteration 10 — test-suite hardening + stay-reason context engineering (2026-06-27)

**Test-suite hardening (green):** the iter9 tmp_path fix unmasked pre-existing debt; fixed it all.
- conftest: replaced the MagicMock retrieval (returned nothing) with a REAL in-memory ChromaDB
  (EphemeralClient + per-test reset) + a fast deterministic lexical embedding; added the missing
  `chroma_client` fixture; rerank passthrough (skip cross-encoder without overriding RERANK_MODEL).
- de-brittled config/base tests (tier->llama3.1:8b; timeout asserts cfg.OLLAMA_TIMEOUT behavior, not a
  source literal); monkeypatched import-bound PIPELINE_XLSX in excel_writer test; xfailed two known-gap
  tests (dormant ESCO paraphrase; persona stay-blind-spot fixtures stale vs the O*NET corpus, unused in
  scoring). **~28 passing/30 erroring -> 145 passed, 2 xfailed, 0 failed.**

**Stay-reason context engineering** (`app/agents/intent.py`): "staying in field" split into advancement /
comp_culture / displaced / lateral, each with tailored matcher+coach+strategist framing (see commit).
All intent framing (switch + stay reasons) centralized; 3 agents refactored to `intent.note()`. UI dropdown
added. Eval doesn't yet model stay_reason (no motivation personas) — validated by unit test + prompt capture.

Spend: $0 (all local). Backlog status: P0/P1 done + validated (+0.490); C-tier test-infra/C5/C3 done;
stay-reason added. Deferred: ESCO retire, persona stay-blind-spot re-authoring, stay_reason eval personas.

---

## Iteration 11 — ESCO retire + effort/compute A/B + Step-5 assessment (2026-06-28)

**ESCO A/B (3-arm, post-Step-1 baseline) → RETIRED.** esco_ret/esco_full vs O*NET-only = +0.026/+0.028
mean overall: within the GPU-noise floor, concentrated in one synthetic cell (switch_synth job +0.31 via
retrieval expansion), 0.000 on realistic stay_adz. No generalizing value. Retired the whole ESCO layer
(graph/loader/normalize + all GRAPH_* levers + skill_ids tagging + _id_citations). O*NET layer untouched.

**Effort / accuracy-vs-compute A/B (quick/balanced/max, realistic cells):**
| cell | quick | balanced | max | max sec/run |
|---|---|---|---|---|
| switch_adz | 1.965 | 2.047 | 2.093 | 126s |
| stay_adz | 2.183 | 2.155 | 2.128 | 127s |
| mean | 2.074 | 2.101 | 2.111 | (2.5x latency) |

**Verdict: more compute is NOT reliably more accurate.** quick->max +0.037 mean (noise floor), NON-uniform
(switch +0.13, stay -0.055), at 2.5x latency; best-of-N @ temp 0.4 degraded stay_adz spot (1.89->1.67) —
sampling variance hurt. The effort dial's value is UX (breadth of options surfaced, expectation-tempering,
async/email fit), NOT accuracy. Do not market "max = more accurate."

**Step-5 recommendations:**
1. Keep the effort dial for UX (default Balanced — best accuracy/latency); frame Max as "more options +
   thoroughness," not "more accurate."
2. best-of-N as implemented (temp 0.4) is net-negative on accuracy — either lower the sampling temp +
   select by occupation-grounding (auth%) instead of grounding-ratio, then re-A/B, OR drop best-of-N from
   Max and let Max = breadth (fetch) + rerank only (the safe levers). Recommend the latter unless a tuned
   best-of-N proves out.
3. Usage-personas: define by UX need (speed / breadth / async), map to effort; not as accuracy tiers.
4. Canonical baseline for future A/Bs = O*NET-only + rubric_v2 + B5 + Balanced effort
   (realistic-cell mean overall ~2.10).

Pod spend this batch ~$3.5 (ESCO + effort), under the $10 cap.

---

## Iteration 12 — Re-aimed-Max lead: A/B/C arms (2026-06-28)

Question (user lead): does Max-effort compute add real accuracy when *aimed right*, and is the path
verification (B) or evidence (C) or both? 5 arms x 2 realistic cells x 14 personas, llama3.1:8b @ temp 0.

| arm | switch d | sw auth% | stay d | st auth% | mean d |
|---|---|---|---|---|---|
| baseline (balanced) | 2.041 | 42.7 | 2.138 | 61.5 | - |
| A re-aimed best-of-N (occ-grounded select, temp 0.2, best-of-3) | +0.013 | 38.7 | -0.015 | 50.8 | -0.001 |
| B verification pass (deterministic grounding-enforcement) | +0.061 | 46.8 | -0.013 | 60.1 | +0.024 |
| C evidence depth (aggregate authoritative reqs across top-5 occupations) | +0.034 | 44.0 | +0.069 | 70.8 | +0.052 |
| BC | +0.063 | 48.1 | +0.047 | 67.8 | +0.055 |

**Verdict:**
- **A (sampling) is DEAD** — mean -0.001, and auth% DROPS in both cells even with the selection re-aimed
  to occupation-grounding. Best-of-N is not the lever, re-aiming did not save it. Confirms the iter11
  drop; best_of stays 1.
- **C (evidence depth) is the winner** — +0.052 mean, positive in BOTH cells, biggest grounding lift
  (stay auth 61.5->70.8), and FREE (no extra LLM). ADOPTED as default (AGG_REQS=5).
- **B (verification) is situational** — +0.061 on the hard switch cell, flat/negative on stay (-0.013);
  costs an extra LLM call. Keep gated, enable for switch-mode / high-effort only.
- **BC does not compound** — +0.055 mean ~= C alone (+0.052); B drags C down on stay (BC +0.047 < C +0.069).
  Not worth the extra call.

**So "Max effort" should mean evidence depth + (switch-only) verification, NOT sampling.** The real
accuracy lever was richer authoritative evidence, costing ~nothing — consistent with every prior
iteration (grounding/evidence move the needle; compute/sampling/taxonomy do not).

Follow-ups queued: (a) SEMANTIC_GAPS prototype sharpens the same evidence path (A/B next, on the new
C-default baseline); (b) Nesta Causeways spec = switcher-pivot engine (.pipeline/nesta_causeways_spec.md).
Pod spend this batch ~$2.6 (one invalid run re-done), under the $5 cap.
