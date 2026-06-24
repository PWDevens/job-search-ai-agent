# Project Status — 2026-06-24

## Current Phase: Eval Harness Fix (`fix/eval-harness` branch)

**Active work:** Fixing the evaluation rubric so it validly measures agent quality before the
v2 (finetuned-agent) comparison round. The 2×2 baseline run (192 rows) showed the rubric
currently mis-measures quality — every row scored "Poor", blind-spot grounding was 0%, and
stay-in-field rows fell back to the matcher heuristic almost 100% of the time.

See `.claude/plans/misty-giggling-scott.md` for the full prioritized list (5 critical /
5 major / 5 minor items) and `docs/development/improvements.md` for the summary.

---

## What's Shipped (`main`)

- **Framework-free 3-agent pipeline** — `job_matcher`, `resume_coach`, `career_strategist`,
  orchestrated in plain Python (`app/pipeline/pipeline.py`). No agent framework.
  *(The earlier CrewAI approach was removed; the BaseTool validation issue it had no longer applies.)*
- **ChromaDB embedded** vector store for job embeddings, resume chunks, and ATS knowledge.
- **Live job search** via the Adzuna free API (Action 2), alongside CSV/XLSX upload.
- **Hardware-tiered model selection** (`app/hardware.py`):
  - CPU → `phi4-mini:q4_K_M`
  - Any NVIDIA GPU → `llama3.1:8b`
- **Context window default raised to 8192** (`OLLAMA_NUM_CTX`) — required because the
  job-matcher prompt is ~5,200 tokens and the agents fail silently if it's truncated at 4096.

---

## Recent Eval Results (June 2026 bake-off, GPU, `num_ctx=8192`)

A model bake-off compared candidates on the real pipeline, which requires reliable
structured (JSON) output:

| Model | Overall score | Speed | Verdict |
|-------|---------------|-------|---------|
| gemma2:9b | 2.10 / 4.0 | ~119 s/run | Previous GPU default |
| gemma3:12b | ~2.0 / 4.0 | ~150 s/run | Rejected — slower, no quality gain |
| gemma4 (12B & 26B-MoE) | N/A | — | Rejected — returns empty responses under structured output |
| **llama3.1:8b** | **1.92 / 4.0** | **~67 s/run** | **✅ New GPU default — ~2× faster, quality within noise, fits all GPU tiers** |

> **Note:** the absolute scores are suppressed by the known eval-harness bugs (the 5 critical
> items above), so they are a *relative* hardware signal only. The quality gap between
> `llama3.1:8b` and `gemma2:9b` is within noise; speed and structured-output reliability are
> the deciding factors. See the README's "Why llama3.1:8b for GPU?" section.

---

## Next Steps

1. Land the 5 critical eval-harness fixes (C1–C5).
2. Re-run the 2×2 baseline on the fixed harness — this becomes the **true** pre-finetuning baseline.
3. Address the major coverage/variance items (all 3 search variants per persona, `--repeats N`).
4. Begin the v2 finetuned-agent round and measure before/after against the corrected rubric.

---

*Updated: 2026-06-24 · Status: Eval harness fix in progress on `fix/eval-harness`*
