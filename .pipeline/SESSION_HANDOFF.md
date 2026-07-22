# Session Handoff — Job-Search AI Agent (as of 2026-07-13)

Cold-start context for a new Claude Code session. Read this first, then `reports/IMPROVEMENT_LOG.md`
(full iteration history) and the `.pipeline/*.md` specs. Branch: **`fix/eval-harness-and-personas`**.

**Since the last handoff (2026-06-30):** this session did NOT touch the eval/model work below (sections
2-7 are unchanged background). It did two new things: (a) shipped the v2 "upload target jobs" front-end
split as a folder-tab UI, and (b) stood up + stress-tested a full Docker deployment. **Nothing from this
session is committed yet** — see §0 for exactly what's sitting in the working tree and what to decide next.

---

## 0. THIS SESSION — start here

### What shipped (uncommitted)
- **Folder-tab mode switch** on the search form (`app/templates/index.html`, `app/static/css/style.css`):
  splits the old single form into **🔎 Have Tool Search** (existing corpus/live-search flow) vs.
  **📤 Upload Target Jobs** (CSV/XLSX upload + format guide, moved in from its old standalone card).
  Pure front-end reorg — same field names, `switchTab()` JS disables the inactive panel's inputs so only
  the active mode submits. No backend/route changes. Verified in-browser: default state, round-trip
  toggling, disabled-input behavior, computed tab colors, no console errors, no mobile overflow at 375px.
  **This directly answers the "front-end mockup" gap that was blocking v2 Phase 2** in the prior
  `.pipeline/v2_specs.md` read — the UI approach is no longer an open question, it's built.
- **Dockerfile fix**: `pip install -r requirements.txt` was pulling full CUDA torch (~3GB of unneeded
  `nvidia-*` wheels) with no GPU passthrough configured. Fixed with a CPU-index install
  (`--index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple`).
- **New `.dockerignore`**: build context was 677MB+ (was baking in the local ChromaDB store, `.venv`,
  logs — all irrelevant since `data/` is volume-mounted at runtime anyway).

Working tree right now:
```
 M Dockerfile
 M app/static/css/style.css
 M app/templates/index.html
?? .dockerignore
```
`.claude/launch.json` also has a `flask-dev` config (Flask dev server preview) — fine to keep/commit if useful,
it's tooling config not app code.

### Docker deployability — tested end-to-end, one real finding
Built and ran `docker compose up` (app + ollama containers), pulled `qwen3:4b` into the container, ran a
real search through the browser against the deployed image. Result:
- Folder-tab UI renders and works correctly from the built image (frontend change is deploy-clean).
- **CPU-only inference in the container cannot finish a single agent call within `OLLAMA_TIMEOUT=300s`.**
  All three agents (job_matcher → resume_coach → career_strategist) timed out in sequence (~5 min each,
  ~15 min total) with no GPU passthrough configured (it's commented out in `docker-compose.yml`).
- The pipeline's fallback logic worked exactly as designed — no crash, `POST /search` still returned 200,
  and the results page rendered with real retrieved job matches (Adzuna/ATS-sourced, real scores) plus
  fallback-labeled resume recs / blind spots ("Using fallback results" shown honestly in the UI, not
  hidden). **Deployability is proven; usable LLM-generated advice in Docker is not, until GPU passthrough
  is enabled.**
- **Action item:** uncomment/wire the GPU `deploy:` block in `docker-compose.yml` before relying on the
  Docker path for real output, or accept CPU-only Docker as "retrieval-only" mode.

### Environment state RIGHT NOW (verify before continuing)
- **Docker Desktop's engine is not currently reachable** (`docker version` gets a client response but the
  daemon connection fails — `dockerDesktopLinuxEngine` pipe not found). The session/environment this ran
  in appears to have reset since the Docker test completed (a background pip-install task from the same
  session also lost its output file and had to be re-verified). **Restart Docker Desktop before resuming
  Docker work**; the fate of the `jobsearch_app_tmp` / `jobsearch_ollama` containers from the test is
  unverified — check `docker ps -a` once the daemon is back.
- The `docker-compose.override.yml` used for testing (just remaps Ollama's host port to avoid clashing
  with the native Ollama already running on 11434) lived in the **scratchpad temp dir, not the repo** —
  it's gone/unreachable now and would need to be recreated if you resume Docker testing.
- **Native (non-Docker) path**: the repo's committed `.venv` is broken — `pyvenv.cfg` points at
  `C:\Users\pwdev\AppData\Local\Programs\Python\Python312`, which no longer exists post-hardware-upgrade
  (see memory `hardware-upgrade-runpod-less-needed.md`). Worked around by installing straight into the
  system/base Python (`miniconda3\python.exe`) instead: `flask`, `python-dotenv`, `werkzeug` first (to
  preview the template), then the full `requirements.txt`. **Confirmed importable this session**: flask
  3.1.3, chromadb 0.5.20, sentence-transformers 5.6.0, flashrank, pandas 3.0.3, pdfplumber 0.11.10, torch
  2.12.1+**cpu** (correctly the CPU build), openpyxl, apscheduler — the native path is ready to run
  end-to-end right now (`python run.py`). **The `.venv` itself is still broken and unused** — worth a
  `python -m venv` rebuild if you want an isolated env instead of installing into base.
- Ollama is running natively on this machine (not in Docker) with `qwen3:4b` pulled — `hardware.py`
  correctly detects this box as `gpu_avg` tier and selects `qwen3:4b`, matching what's available. The
  native path (`python run.py`) should work for a real end-to-end test without the Docker CPU-timeout
  problem, since native Ollama presumably has GPU access Docker's container didn't.

### Next steps (pick up here)
0. **Quick win**: native path is fully ready right now (`python run.py`, deps confirmed importable) —
   worth a real end-to-end search here first since native Ollama likely has GPU access the Docker
   container didn't, so it should avoid the 300s timeout and produce real (non-fallback) LLM output.
1. Restart Docker Desktop, check `docker ps -a` for the leftover test containers, decide keep-running vs.
   tear down (`docker compose down`).
2. Review + commit the working-tree diff (Dockerfile, .dockerignore, index.html, style.css) — nothing
   from this session is committed.
3. Decide on GPU passthrough in `docker-compose.yml` given the CPU-timeout finding.
4. **v2 Phase 2 backend is still open**: the folder-tab UI only reorganizes the front end. `routes.py`
   still ingests uploaded jobs CSVs into the shared ChromaDB corpus and *retrieves* against it — the spec's
   "user-jobs mode" (uploaded set *is* the candidate pool, ranked not retrieved) doesn't exist yet, and
   the apply-priority scoring formula/thresholds (fit × gap-effort → apply now/stretch/skip) are still
   undefined. That's the real remaining work before Phase 2 is done.
5. Phase 1 (USAJobs validation) in `.pipeline/v2_specs.md` is untouched and still the one fully-spec'd,
   ready-to-build unit if you want a smaller/independent next task.

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
(`README.md`, `README_Simplified.md`). Everything through v1 committed + pushed.

## 5. Models (current, `app/hardware.py`)
| Tier | Model | Origin |
|---|---|---|
| cpu (no NVIDIA / iGPU / Apple) | `qwen3:4b` | Alibaba |
| gpu_avg (<10GB VRAM) | `qwen3:4b` | Alibaba |
| gpu_modern (≥10GB VRAM) | `gemma3:12b` | Google (US) |
Override: `AGENT_MODEL=<model>`. US-only: `AGENT_MODEL=gemma3:12b` everywhere. Requires `OLLAMA_NUM_CTX≥8192`.
CAVEAT: eval measures QUALITY not speed; gemma3:12b is slow on CPU/iGPU laptops. `detect_tier` only probes
nvidia-smi (Macs fall to cpu→qwen3:4b, fine). Confirmed this session: this dev machine detects `gpu_avg` →
`qwen3:4b`, and that's the model actually pulled in Ollama — consistent, no action needed here.

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
- `app/hardware.py` — tier→model map.
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
- `app/templates/index.html` + `app/static/css/style.css` — **now has the folder-tab mode switch** (§0).
- `Dockerfile` + `.dockerignore` — **CPU-torch install fix + trimmed build context this session** (§0).
- `docker-compose.yml` — GPU `deploy:` block still commented out; see §0 action item.

## 9. v2 roadmap (`.pipeline/v2_specs.md`)
1. **USAJobs validation** — 4th adapter in ats_sources.py; cross-domain confirmation the wins generalize
   (federal jobs = validation corpus, not production source; structured → high requirements-coverage).
   **Untouched, still fully spec'd and ready to build.**
2. **"Bring your own jobs" upload feature** (the product leap) — **front-end DONE this session** (folder-tab
   mode switch, §0). Still open: **"user-jobs mode"** in the pipeline (uploaded set IS the candidate pool,
   matcher ranks vs retrieves — `routes.py` currently just ingests into the shared corpus), URL→full-text
   fallback, per-job output, and the **apply-priority scoring formula** (fit × gap-effort → apply
   now/stretch/skip — thresholds not yet defined).
3. Follow-ons: gap-closing roadmap (top-3 skills unlocking the most of the list), per-job resume tailoring.
   `.pipeline/v2.md` will be the GitHub v2 writeup once it lands.

## 10. Immediate open items
See **§0 "Next steps"** for this session's concrete pickup list. Older/standing items:
- Re-confirm new models' tok/s on real target laptops before fully trusting in production.
- (Optional) `docs/SLM_FINETUNING_GUIDE.md` still Phi-4-mini-specific — refresh if desired.

## 11. Memory (auto-loaded each session, `~/.claude/.../memory/`)
Key files: `model-is-dominant-lever.md`, `full-text-is-the-lever.md`, `grounding-rootcause-and-rubric.md`,
`deterministic-eval-via-pod.md`, `taskstop-leaves-zombie-processes.md`, `core-jtbd.md`,
`hardware-upgrade-runpod-less-needed.md`, `local-ollama-models-pulled.md`.

## 12. Constraints
- User tops up RunPod themselves — NEVER enter payment/financial credentials.
- Secrets in `.secrets/` (gitignored): `runpod.env` (RUN_POD_API_KEY), CareerOneStop creds in `.env`.
- Delete pods after each A/B. Commit + push when asked; branch `fix/eval-harness-and-personas`.
