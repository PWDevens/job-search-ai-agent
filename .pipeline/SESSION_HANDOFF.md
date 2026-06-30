# Session Handoff — Job-Search AI Agent (as of 2026-06-30)

Cold-start context for a new Claude Code session. Read this first, then `reports/IMPROVEMENT_LOG.md`
(full iteration history) and the `.pipeline/*.md` specs. Branch: **`fix/eval-harness-and-personas`**
(35+ commits ahead of where this work started; all committed + pushed to origin, backlog clear).

---

## 1. What this is
A **fully local, open-source** job-search assistant (Flask web app, `python run.py` → localhost:5000).
Upload a resume + target role; a **framework-free 3-agent pipeline on Ollama** returns ranked jobs,
resume recommendations, and career blind spots — grounded in **real job-posting requirements + US O*NET**
occupation data. No cloud APIs, no data leaves the machine. MIT licensed.

**North-star JTBD:** "prioritize what to apply to + improve my chances of getting hired, frictionlessly."
The eval is a proxy; the JTBD is the goal.

**Agents** (`app/agents/`): `agent_job_matcher`, `agent_resume_coach`, `agent_career_strategist`.
Each returns Pydantic JSON-schema-validated output (grammar-constrained via Ollama `format=json`).

## 2. Architecture (current)
```
Resume + role ─► retrieval (ChromaDB + bge-small embeddings + bge-reranker-v2-m3)
              ─► full-text job postings ─► sections.py parser ─► requirements_text
              ─► job_matcher ─► resume_coach ─► career_strategist
              ─► O*NET authoritative requirements (AUTHORITATIVE_GAPS) ground blind-spots/recs
```
- **Full-text sourcing**: `app/pipeline/ats_sources.py` pulls complete descriptions from **Greenhouse/
  Lever/Ashby** public APIs (free, no bot-wall). `scripts/pull_ats.py` (registry `data/ats_boards.json`,
  48 boards) → CSV → `scripts/ingest_jobs.py` → ChromaDB. Adzuna is truncated (500 chars) + 403-walled.
- **Grounding**: `app/skills/onet_requirements.py` (title→O*NET-SOC via bge, MIN_CONF 0.80) injects the
  target occupation's real requirements. `AUTHORITATIVE_GAPS=1` (default on) — proven the biggest early win.
- **Intent**: stay-in-field vs career-switch mode (`app/agents/intent.py`); **Effort dial**
  (quick/balanced/thorough/max) in `app/config.py` EFFORT_BUNDLES.
- **Section parser** `app/pipeline/sections.py`: extracts requirements block; header set expanded for
  ATS phrasings ("Who You Are"/"What You'll Bring") → requirements-coverage 22.9%→58.1%.

## 3. THE VALIDATED FINDINGS (most important — don't relitigate)
What moves the eval, proven by deterministic pod A/Bs (see IMPROVEMENT_LOG iterations 11-16):

**WINS (shipped/default):**
- **Base model = the DOMINANT lever (+0.76-0.79 overall).** iter16 13-model bake-off. Current default
  `llama3.1:8b` ranked NEAR BOTTOM. Winners (generalize across switch+stay): **qwen3:4b** (best+smallest,
  CN, 4B/8GB) and **gemma3:12b** (US/Google, ~tied, 16-24GB). Scaling BACKFIRES (qwen3 4b>8b>14b>30b-MoE).
  gpt-oss:20b (US) strong on switch but FADES on stay. NOW WIRED INTO `app/hardware.py`.
- **Full posting text +0.414 overall, 14/14 personas** (iter15). Un-truncation via ATS APIs. The
  requirements section is what grounds good advice. Built the ATS sourcing pipeline on this.
- **AUTHORITATIVE_GAPS** (O*NET grounding) — big early win (off→on +0.49). Default on.
- **Evidence-depth** (AGG_REQS=5, aggregate O*NET reqs across top-5 occupations) +0.052, free. Default.

**DEAD ENDS (tested, retired/shelved — DO NOT re-try without new info):**
- **ESCO occupation-graph** — retired iter11 (+0.026 noise; labels don't match posting tokens).
- **best-of-N sampling** — dead even re-aimed (iter12).
- **verification pass** — situational (helps switch, flat stay).
- **semantic gap-detection** (SEMANTIC_GAPS) — fixed a bug but net marginal; gated off.
- **Causeways / O*NET-Related occupation pivots** — flat both cells (iter14); module exists, gated off.
- **embeddings/reranker tuning** — assessed as "little juice"; SHELVED unless a retrieval need surfaces.
- General pattern: **grounding/evidence/model move the needle; taxonomy/graph/sampling/retrieval do not.**

## 4. v1 MVP status — SHIPPED
v1 is a good stopping point. GitHub-facing details: **`.pipeline/v1.md`**. README refreshed to new models
(`README.md`, `README_Simplified.md`). Everything committed + pushed.

## 5. Models (current, `app/hardware.py`)
| Tier | Model | Origin |
|---|---|---|
| cpu (no NVIDIA / iGPU / Apple) | `qwen3:4b` | Alibaba |
| gpu_avg (<10GB VRAM) | `qwen3:4b` | Alibaba |
| gpu_modern (≥10GB VRAM) | `gemma3:12b` | Google (US) |
Override: `AGENT_MODEL=<model>`. US-only: `AGENT_MODEL=gemma3:12b` everywhere. Requires `OLLAMA_NUM_CTX≥8192`.
CAVEAT: eval measures QUALITY not speed; gemma3:12b is slow on CPU/iGPU laptops. `detect_tier` only probes
nvidia-smi (Macs fall to cpu→qwen3:4b, fine). Re-confirm tok/s on real target hardware before relying in prod.

## 6. Eval / test harness
- **Personas**: `tests/persona_evaluation/personas.py` (14 occupations, ALL_PERSONAS; switch + stay variants).
- **Scoring**: `tests/persona_evaluation/evaluation_scoring.py` — overall = job*0.3 + rec*0.4 + spot*0.3;
  rubric_v2 (blind spot grounded if in posting OR O*NET req). Metrics incl. blind_spot_auth_grounded_pct,
  rec_gap_closing_pct, pivot_coverage_pct.
- **Runner**: `scripts/eval_compare.py --configs baseline --scenario 9 --variant switching|stayinfield
  --temp 0 [--model X]`. `--model` overrides the LLM. `EVAL_PERSIST_RAW=1` banks raw outputs to
  `<EVAL_OUT>.raw.jsonl` for **$0 offline re-scoring** (`scripts/rescore_raw.py`) — essential given
  session interruptions.
- **Model bake-off framework**: `scripts/model_bakeoff.sh` — holds corpus/personas/variant constant,
  varies only --model, pull→preflight→eval(raw)→rm (disk-bounded). Reusable for future model tests.
- Unit tests: `python -m pytest -q` (140 passing). pytest.ini disables asyncio plugin.

## 7. Pod / RunPod playbook (deterministic eval)
Local CPU is too slow + serverless too noisy for sub-0.1 effect sizes. Use a **dedicated single-GPU pod**:
- Create via MCP `mcp__runpod__create-pod` OR REST (`curl https://rest.runpod.io/v1/pods` with
  `Authorization: Bearer $RUN_POD_API_KEY` from `.secrets/runpod.env`). Image `ollama/ollama:latest`,
  env `OLLAMA_HOST=0.0.0.0 OLLAMA_MODELS=/workspace/models OLLAMA_KEEP_ALIVE=-1`, **volumeInGb≥40 + a
  volume mount** (model on ephemeral container disk gets wiped on restart → 404 → silent matcher fallback!).
- Pull model + **preflight `/api/chat`** before running (a 404 means silent fallback → invalid data).
- Run eval with `unset RUNPOD_ENDPOINT_ID; OLLAMA_BASE_URL=https://<podId>-11434.proxy.runpod.net`,
  `--temp 0`, sequential.
- **DELETE the pod immediately after** (bills ~$0.27-0.69/hr continuously). MCP delete returns
  "Unexpected end of JSON input" but succeeds — verify via list-pods. If MCP is down, delete via REST
  (`curl -X DELETE .../v1/pods/<id>`). LESSON: session gaps leave pods billing — always tear down in-session.
- A4000/A5000/A40 all fine for temp-0 determinism; A40 (48GB) needed for 32B models. ~$10 budget runs a lot.

## 8. Key file map
- `app/hardware.py` — tier→model map (just updated).
- `app/config.py` — EFFORT_BUNDLES, AUTHORITATIVE_GAPS, AGG_REQS, RERANK_MODEL=bge-reranker-v2-m3,
  EMBED_MODEL=BAAI/bge-small-en-v1.5.
- `app/pipeline/pipeline.py` — orchestration; `_run_with_grounding` (best_of + select_fn gated off).
- `app/pipeline/ats_sources.py` + `scripts/pull_ats.py` + `data/ats_boards.json` — full-text sourcing.
- `app/pipeline/sections.py` — requirements parser.
- `app/skills/onet_requirements.py` — O*NET grounding (+ SEMANTIC_GAPS path, gated).
- `app/skills/causeways.py` — pivot engine (gated off, shelved).
- `scripts/eval_compare.py`, `scripts/model_bakeoff.sh`, `scripts/rescore_raw.py` — eval tooling.
- `reports/IMPROVEMENT_LOG.md` — FULL history, iterations 1-16.
- `.pipeline/v1.md` (GitHub v1), `.pipeline/v2_specs.md` (v2 plan), `.pipeline/full_text_sourcing_spec.md`,
  `.pipeline/nesta_causeways_spec.md`.

## 9. v2 roadmap (`.pipeline/v2_specs.md`)
1. **USAJobs validation** — 4th adapter in ats_sources.py; cross-domain confirmation the wins generalize
   (federal jobs = validation corpus, not production source; structured → high requirements-coverage).
2. **"Bring your own jobs" upload feature** (the product leap) — second UI tab: user uploads a CSV of
   jobs they care about; tool PRIORITIZES that list + tailors resume/strategy to those targets. Sidesteps
   v1's one weakness (corpus-bound discovery) + maximizes the proven full-text grounding lever. Reuses
   ingest + sections + agents; new = upload tab, "user-jobs mode" (uploaded set IS the candidate pool,
   matcher ranks vs retrieves), URL→full-text fallback, per-job output. Headline output: **apply-priority
   scoring** (fit × gap-effort → apply now/stretch/skip).
3. Follow-ons: gap-closing roadmap (top-3 skills unlocking the most of the list), per-job resume tailoring.
   `.pipeline/v2.md` will be the GitHub v2 writeup once it lands. Front-end: mockup coming from user.

## 10. Immediate open items
- Re-confirm new models' tok/s on real target laptops before fully trusting in production.
- (Optional) `docs/SLM_FINETUNING_GUIDE.md` still Phi-4-mini-specific — refresh if desired.
- v2 starts with USAJobs validation, then the upload feature.

## 11. Memory (auto-loaded each session, `~/.claude/.../memory/`)
Key files: `model-is-dominant-lever.md`, `full-text-is-the-lever.md`, `grounding-rootcause-and-rubric.md`,
`deterministic-eval-via-pod.md`, `taskstop-leaves-zombie-processes.md`, `core-jtbd.md`.

## 12. Constraints
- User tops up RunPod themselves — NEVER enter payment/financial credentials.
- Secrets in `.secrets/` (gitignored): `runpod.env` (RUN_POD_API_KEY), CareerOneStop creds in `.env`.
- Delete pods after each A/B. Commit + push when asked; branch `fix/eval-harness-and-personas`.
