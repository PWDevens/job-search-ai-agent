# `reports/` — Evaluation & Experiment Log

Tracking doc for every eval run in this folder: **what the test measured, the result, and the lesson.**
Update this when you add a run. Files you can't tie to a documented experiment go in [`archived/`](archived/).

## How runs are produced
- Harness: `scripts/eval_compare.py --repeats N --configs baseline --variant {switching|stayinfield} --scenario 9`
  - `--variant` selects the **persona query set** (switching = career-changer targets; stayinfield = native-field targets). The **job corpus** is whatever is ingested into the active ChromaDB (`scripts/ingest_jobs.py <csv> --clear`).
  - `--scenario 9` = llama3.1:8b. Served via **RunPod serverless** when `RUNPOD_ENDPOINT_ID` + `RUNPOD_API_KEY` are set (`OLLAMA_NUM_CTX=8192` required).
  - `EVAL_OUT=<path>` overrides the output CSV (lets parallel same-variant runs avoid collisions).
- Default output path (no `EVAL_OUT`): `reports/eval_compare_{variant}.csv` (overwritten each run).

## Metric glossary (per persona row, averaged per cell)
| Metric | Meaning |
|---|---|
| `overall_score` | `job*0.3 + rec*0.4 + spot*0.3` |
| `avg_job_score` | job-match dimension (retrieval-driven) |
| `avg_rec_score` | resume-recommendation dimension |
| `avg_spot_score` | blind-spot dimension |
| `blind_spot_grounded_pct` (gnd%) | % of blind spots whose skill literally appears in a retrieved posting |
| `blind_spot_auth_grounded_pct` (auth%) | **JTBD-aligned grounding (iter5):** % of blind spots whose skill is in the *target occupation's real O*NET requirements* (via `app/skills/onet_requirements.py`). Measures advice quality even when the truncated posting can't confirm it — the honest companion to gnd% given Adzuna postings are 99% cut at 500 chars. Blank when the O*NET DB is absent. |
| `fallback_used` (fb%) | % of rows where the agent output failed grounding and fell back to the matcher heuristic |

**Flag `AUTHORITATIVE_GAPS`** (**DEFAULT ON**, iter7; set `=0` to disable): career-strategist blind spots + resume-coach recs are grounded in the target occupation's authoritative O*NET requirements (target derived from the matched jobs' titles), instead of skills that must appear in a truncated posting. No-op when the O*NET DB is absent. A/B: off→on **+0.414 mean overall**, positive in all 4 cells, switcher gap closed (iter7).

**Flag `RUBRIC_V2`** (**DEFAULT ON**, iter6 R1 + iter7 B5; set `=0` to reproduce a pre-v2 baseline): JTBD-aligned scoring. A blind spot is grounded if its skill is in a retrieved posting **OR** a real target-occupation O*NET requirement (auth-only → 3/4, both → 4/4); a resume rec scores as **gap-closing** if it adds a real occupation requirement (B5 — credits non-tech credentials the tech-keyword list missed). Fixes v1's truncation-bound + tech-biased blindness. The `rubric_version` column (`v1`/`v2`) self-identifies every run — **do not compare overall_score across rubric versions.** Metric `rec_gap_closing_pct` reports the rec-side signal (cf. `blind_spot_auth_grounded_pct`).

---

## ACTIVE — Experiment: Occupation-graph injection-point map (2026-06-26)
**Question:** where in the agentic pipeline does the ESCO occupation→skill graph add value, and where does it hurt?
Graph data = `app/skills/graph.py` loaded from the pre-joined `data/skills/raw/esco_relations.csv`
(occupation-skill + skill-skill edges). Flags in `app/config.py`: `GRAPH_RETRIEVAL`, `GRAPH_PROMPT_CONTEXT`,
`GRAPH_RESUME_CONTEXT` (and `USE_GRAPH_DATA` = all-on, for the bundled A/B).

Design: 4-way parallel **2×2** (switching/stay × synthetic/Adzuna) × condition, 1 repeat, n=11 personas/cell,
serverless llama3.1:8b. Each cell isolated (own `data/chroma_ab_<cell>/` + `EVAL_OUT`).

> **⚠️ Methodology note (2026-06-26).** Round 1 (`ab_*`) was contaminated by **zombie processes**:
> `eval_compare` already runs greedy (`--temp` default 0.0), so temperature was *not* the issue —
> but each time a background A/B was stopped, the `&`-backgrounded bash subshells and their python
> children were **orphaned, not killed** (`TaskStop` only kills the bash parent). 11 stray subshells +
> several python writers kept running, hitting serverless and **overwriting shared output files** —
> one was caught rewriting `ab_switch_adz_off.csv` mid-session (a re-run that, on a *different* GPU
> in the heterogeneous fleet, produced different greedy output). So Round-1 `_off` baselines drifted,
> and the `_ret`/`_resume` deltas (which reused those baselines) are unreliable. **Only the Round-1
> bundled `_off` vs `_on` table — generated paired in one clean run — is trustworthy.**
>
> Round 2 (`ab2_*`) fixes it: **(1)** all zombies killed first; **(2)** every condition regenerated
> **paired with its own off baseline in the same run**; **(3)** explicit `--temp 0`; **(4)** clean
> `ab2_` namespace. Residual caveat: the GPU fleet is heterogeneous, so greedy isn't bit-reproducible
> across workers — large effects (retrieval job-dim, prompt grounding) are robust; sub-0.1 deltas are noise.
> Script: `.secrets/_ab_map_temp0.sh`. **Operational rule: kill stray `eval_compare` bash+python before
> any new run; don't rely on `TaskStop` alone.** **`ab2_*` is canonical; Round-1 `_ret`/`_resume` are void.**

Scripts: `.secrets/_ab_graph_par.sh` (round 1 off/on), `_ab_retonly.sh`, `_ab_resume.sh`, `_ab_map_temp0.sh` (round 2).

### File map
| Files | Condition |
|---|---|
| `ab_{cell}_off.csv` | baseline — no graph data (the comparison baseline for every condition) |
| `ab_{cell}_on.csv` | `USE_GRAPH_DATA=1` — retrieval expansion **+** strategist prompt context (bundled) |
| `ab_{cell}_ret.csv` | `GRAPH_RETRIEVAL=1` — retrieval expansion only |
| `ab_{cell}_resume.csv` | `GRAPH_RESUME_CONTEXT=1` — resume-coach prompt context only *(pending)* |
| `ab_{cell}.log`, `*_ret.log`, `*_resume.log` | raw run logs (debug; ChromaDB telemetry noise is harmless) |

`{cell}` ∈ `switch_synth`, `stay_synth`, `switch_adz`, `stay_adz`.

### Results — bundled off vs on (Δ = on − off)
| Cell (n=11) | overall | **job** | spot | **gnd%** | **fb%** |
|---|:--:|:--:|:--:|:--:|:--:|
| switching × synthetic | −0.07 | +0.09 | −0.25 | −9.1 | −9.1 |
| stay × synthetic | −0.03 | +0.05 | +0.05 | +7.3 | −9.1 |
| switching × **Adzuna** | −0.02 | **+0.31** | −0.33 | −10.9 | **+63.6** |
| stay × **Adzuna** | −0.03 | −0.04 | +0.05 | 0.0 | +27.3 |

### Results — retrieval-only vs off (Δ = ret − off) — CONFIRMATION
| Cell (n=11) | overall | **job** | spot | rec |
|---|:--:|:--:|:--:|:--:|
| switching × synthetic | **+0.12** | +0.15 | +0.25 | −0.01 |
| stay × synthetic | −0.03 | +0.01 | +0.05 | −0.13 |
| switching × Adzuna | **+0.08** | **+0.29** | −0.09 | +0.05 |
| stay × Adzuna | **+0.13** | **+0.29** | +0.09 | +0.04 |

Net-positive overall in 3/4 cells; **job up in all 4** (+0.29 both Adzuna). Removing the
prompt-context half flipped the bundled net (negative) to positive — the decomposition holds.

### Results — Round 2 `ab2_*` CANONICAL (paired off baseline, greedy, zombie-free)
Δ vs each cell's own off baseline. Cells: switch×synth / stay×synth / switch×Adz / stay×Adz.

| Lever | job Δ | overall Δ | spot Δ | notes |
|---|---|---|---|---|
| **retrieval** | **+0.13 / +0.03 / +0.29 / +0.29** | +0.07 / +0.01 / −0.10 / +0.04 | +0.02 / 0 / −0.45 / −0.16 | job ↑ robust; overall ~neutral |
| **prompt (strategist)** | ~0 | −0.11 / −0.11 / −0.14 / +0.05 | −0.27 / −0.49 / −0.35 / −0.11 | hurts; spot ↓ all 4 |
| **resume** | ~0 | +0.01 / −0.12 / −0.01 / −0.05 | +0.01 / −0.38 / +0.25 / −0.16 | neutral→hurts; rec not improved |

### Findings so far (the injection-point map) — canonical
| # | Injection point | Mechanism | Verdict |
|---|---|---|---|
| 1 | Retrieval (query expansion) | embedding space | **HELPS job-match (+0.13…+0.29), ~NEUTRAL overall** — expanding the query shifts which jobs the strategist grounds against, offsetting via spot |
| 2 | Career-strategist prompt | generation/grounding | **HURTS** — overall −0.11…−0.14, spot ↓ all 4 cells |
| 3 | Resume-coach prompt | generation | **NEUTRAL→HURTS** — rec dimension not improved; "coach is the exception" hypothesis FALSE |
| 4 | Rerank-by-skill (`GRAPH_RERANK`) | scoring space | **REJECT** — net-neutral, high variance (overall +0.18/−0.21/−0.06/+0.06; can evict title-matched jobs from top-5, job −0.44 one cell) |
| 5 | Graph-as-validator (`GRAPH_VALIDATE`) | post-hoc filter | **OPT-IN (deterministically confirmed)** — alone HURTS (−0.047); only synergistic with few-shot (+0.034 combined, marginal/non-uniform). Measured on a dedicated-pod instrument, 0 noise. See IMPROVEMENT_LOG "Deterministic confirmation" |

**Map conclusion:** graph data helps in **embedding/filter space** (retrieval → job; validate → spot), is dead in **generation prompts** (strategist, resume); rerank-by-reorder doesn't help. Clean `ab3_*` re-run (0×402) on the funded endpoint. Next: **combine** retrieval (job↑) + validate (spot↑) — see `IMPROVEMENT_LOG.md` Iteration 2.

**Lesson (working hypothesis):** ESCO's labels are *verbose competence phrases* ("specialist nursing care")
that don't match posting tokens ("RN"). They **help in embedding/scoring space** (retrieval tolerates the
mismatch semantically) and **hurt in agent prompts** (they steer generation toward ungroundable phrasings →
grounding falls, fallback rises). Action taken: split the bundled flag — keep retrieval, leave prompt-context off.

---

## PRIOR experiments

### Strategist occupation-skill injection #1 (2026-06-25)
- Files: `retest_A_no1.csv` (graph off), `retest_B_with1.csv` (graph on), stay×Adzuna.
- Result: HURT — gnd 3.6%→1.8%, fb 55%→82%, spot 0.33→0.20. First evidence of the prompt-context regression
  (reconfirmed at scale by the 2×2 above). Gated behind `STRATEGIST_USE_OCCUPATION_SKILLS` (default off).

### eval_compare latest default outputs
- `eval_compare_switching.csv`, `eval_compare_stayinfield.csv` — most recent non-`EVAL_OUT` runs; transient,
  overwritten by any default-path `eval_compare` invocation. Treat as scratch-of-the-moment, not a labelled result.

### Hardware 2×2 eval series (earlier rounds — see memory `hardware-eval-2x2`)
- `hardware_eval_matrix_pre*.csv`, `..._fix_{sf,sw}{syn,adz}_{cpu,gpu}.csv`, `..._adzuna_*.csv`, `..._bo3_*.csv`,
  `..._scn5.csv` — switching/stay × synthetic/Adzuna across hardware scenarios (phi4-mini/gemma2/llama3.1, CPU/GPU).
- `eval_aggregate.csv` — aggregated matrix; `eval_2x2_baseline.png`, `eval_2x2_beforeafter.png` — plots.
- Context: these validated the eval-harness fixes (C1–C5, MJ3) that lifted mean overall 1.26 → 1.94 before the
  graph work began.

---

## `archived/` — superseded / unidentified
Moved 2026-06-26 (couldn't tie to a documented experiment, or superseded by the current harness):
- `agent_eval.csv`, `demo_eval.csv`, `test1-3.csv`, `final_check.csv`, `final_check_batch.csv` — early
  pre-harness smoke runs (old `...,mock,elapsed_s,...` schema; no rubric scores).
- `hardware_eval_matrix_g4_swsyn_c4096.csv` — 1-row failed run (4096 ctx truncates the job_matcher prompt).
