# Job-Search AI Agent — Remediation and Re-Architecture Plan

Author: engineering review (tech-debt + architecture + system-design + design-handoff lenses, ponytail intensity: full)
Date: 2026-06-18
Target hardware: 16 GB RAM, CPU-only, no GPU. Accuracy and quality prioritized over latency.
End goal of this plan: not deployment. The finish line is a set of three agents you can run standalone from the command line, outside the Flask app, so you can test against personas, score with the existing rubric, and tune prompts/skills (and optionally fine-tune an SLM) based on real results.

---

## 0. How to read this document

Section 1 is the diagnosis: what is actually wrong, with file-level evidence. Section 2 is the recommended stack with the rejected alternatives named. Sections 3-7 are the must-haves. Sections 8-11 are the nice-to-haves. Section 12 is the phased sequence and the definition of done. Section 13 is the honest list of what this plan deliberately does NOT do, and when to revisit.

A guiding rule throughout (the ponytail lens): question whether each piece needs to exist before improving it. The single biggest finding in this review is that a large, expensive component currently produces output that is thrown away. The fix is mostly deletion.

---

## 1. Diagnosis — what is actually wrong

### 1.1 The headline problem: the agents barely do anything

`app/agents/crew.py` (438 lines) builds three CrewAI agents, gives them tools, runs them sequentially through a local LLM, and then **discards most of their output**:

- Top jobs: `result.top_jobs = find_top_jobs(...)` is called directly. The JobMatcher agent's LLM output is never used for the actual job list — the matcher (plain vector search) is ground truth.
- Resume recs and blind spots: the agent text is run through `_validate_agent_output`, a brittle keyword heuristic (it checks whether the text contains substrings like "python", "sql", "ats"). On failure — which STATUS.md reports as the common case — it falls back to `find_resume_recommendations` / `find_blind_spots`, which are again just the matcher.

So the LLM is paying full inference cost (three sequential agents, `max_iter=3`, verbose) to produce text that is frequently validated away and replaced by deterministic vector-search output. The CrewAI layer is, in its current form, close to decorative. That is the core waste.

This is not an argument that the agents have no value — the reference outputs in `.claude/agentic-outputs/` show what good agent output looks like, and it is genuinely valuable. It is an argument that the current wiring spends a framework's worth of complexity to get matcher output with extra steps.

### 1.2 The stack is mid-migration and internally contradictory

A ChromaDB-to-Weaviate migration was started and left half-done (git: `eb77f13 migrate: Replace ChromaDB with Weaviate for reliability`):

- `app/chroma/client.py` is named "chroma" but talks to **Weaviate** over raw HTTP and hand-built GraphQL strings (it interpolates the full embedding vector into a GraphQL query string — fragile and slow).
- `requirements.txt` still pins `chromadb==0.5.20` and never lists `weaviate` at all.
- `app/chroma/client.py` imports `tenacity`, which is **not in requirements.txt**.
- `app/config.py` carries both worlds: `WEAVIATE_HOST/PORT` and `CHROMA_JOBS_COLLECTION/CHROMA_RESUME_COLLECTION`.
- `README.md` badges and prose say ChromaDB; `docker-compose.yml` runs a `semitechnologies/weaviate:latest` server.

The net effect: nobody reading the repo can tell what the vector store is, and the running system depends on a separate server container for what is fundamentally a single-user, local, on-disk index.

### 1.3 Two embedding backends, two LLM wrappers, redundant fallbacks

- `app/chroma/embeddings.py` supports both Ollama embeddings and sentence-transformers, with per-call fallback from one to the other.
- `app/agents/llm_provider.py` supports an 8-model map plus a CrewAI-LLM path and a LiteLLM path and a mock.
- The matcher itself has internal fallbacks; the crew has another fallback layer on top.

Each fallback is individually reasonable, but stacked they make behavior hard to predict and hard to test. The "which code path actually ran" question is the root of the STATUS.md debugging spiral (stale-container confusion, 33/33 test failures).

### 1.4 Documentation and packaging debt

- README links five root docs that do not exist: `INDEX.md`, `DEPLOYMENT_CHECKLIST.md`, `TESTING_GUIDE.md`, `IMPROVEMENTS.md`, `COMPLETION_SUMMARY.md`.
- README badge claims `License: MIT` but there is no `LICENSE` file.
- README claims "PRODUCTION-READY", "Zero critical bugs", "104+ tests passing" while STATUS.md simultaneously reports the entire Phase 2 suite (33/33) failing on a tool-validation error. The two top-level documents contradict each other.
- README has ~59 emoji; STATUS.md and the UI carry more. (You asked for these removed — see Section 9.)
- `.pytest_cache/` is committed.

### 1.5 No reranker

`find_top_jobs` returns raw vector-similarity order. On a small SLM with a small embedder, bi-encoder similarity alone is the weakest link in retrieval quality. There is no cross-encoder/reranker stage. This is the single highest-quality-per-dollar addition available (Section 8).

### 1.6 What is actually good (keep it)

- `app/pipeline/matcher.py` is the real engine and is sound: compiled-regex skill extraction, clean result formatting, geo filtering. Keep it; it becomes a retrieval primitive the agents call.
- `app/pipeline/` ingest / normalizer / excel_writer / audit / geolocation are coherent, single-purpose modules. Keep them.
- `app/agents/rag_knowledge.py` (curated ATS knowledge base) is a genuinely good idea and aligns with the SLM strategy guide. Keep the content; repoint it at the consolidated vector store.
- `.claude/agentic-outputs/QUALITY_BENCHMARKS.md` plus the three reference outputs are an excellent, concrete quality bar. They are the foundation for the skill files and the test loop.

---

## 2. Recommended tech stack for 16 GB CPU

Decision principle: one component per job, in-process where possible, no servers you do not need, smallest model that clears the quality bar. Each row names what it replaces and why the alternatives lost.

| Layer | Recommended | Replaces / removes | Why on 16 GB CPU |
|---|---|---|---|
| Vector store | **ChromaDB (embedded, persistent, on-disk)** | Weaviate server + GraphQL client + docker service | In-process, zero server, single-user. The repo was originally built for this and the module is even named for it. Removes a whole container and the hand-built GraphQL. |
| Embeddings | **`BAAI/bge-small-en-v1.5`** via sentence-transformers (single backend) | dual Ollama+ST backends | 384-dim, ~130 MB, strong retrieval/size ratio on CPU. Drop the Ollama embedding path entirely — one backend, predictable. (Keep `all-MiniLM-L6-v2` as a drop-in if you want even lighter.) |
| Reranker | **FlashRank** with `ms-marco-MiniLM-L-12-v2` (ONNX, ~34 MB) | nothing (new) | Pure-CPU, no torch needed at inference, millisecond-scale on 25-50 candidates. Biggest accuracy win per MB. See Section 8 for the `bge-reranker-v2-m3` upgrade path. |
| SLM | **Qwen2.5-3B-Instruct (Q4_K_M)** via Ollama, default | Llama-3 8B default | 3B Q4 is the comfort zone for 16 GB CPU; strong instruction-following and reliable JSON. Phi-3.5-mini-instruct and Llama-3.2-3B as alternates kept behind one env var. Drop 7-8B as default (too slow on CPU for a 3-agent chain). |
| Structured output | **Ollama JSON mode + Pydantic models** | regex parsing + `_validate_agent_output` keyword heuristic | The model returns schema-valid JSON; Pydantic validates shape; a grounding check validates content against retrieved IDs. Deletes the brittle regex/keyword guesser entirely. |
| Agent orchestration | **Framework-free: thin structured LLM calls, one module per agent** | CrewAI + the crew.py orchestration + tools.py BaseTool wrappers | Per your decision and the 1.1 finding: the framework's value isn't being realized. Direct `chat(messages, schema)` calls are lazier, faster, fully testable, and remove `crewai`, `litellm`, and the tool-validation class of bugs that stalled Phase 2. |
| Web layer | **Keep Flask** (unchanged) | — | It works and is not the problem. Out of scope for this plan except the CLI entry point in Section 7. |

Rejected frameworks, briefly, so the choice is on record:

- **CrewAI** — the current dependency. Its multi-agent/role abstractions are exactly the part you are not benefiting from; its tool-schema validation is what broke Phase 2. Removing it deletes the most bug-prone surface.
- **PydanticAI** — the closest "keep a framework" option and a fine choice if you later want typed agents with tool-calling. Recommendation: skip for now (YAGNI); you can adopt it later without changing the skill files or the retrieval layer, because both are framework-agnostic.
- **LangGraph / AutoGen / "openclaw/hermes"-style** — heavier graphs/runtimes aimed at branching multi-agent control flow you do not have (your flow is a fixed sequence: match -> coach + strategist). Not worth the weight on CPU.

Net dependency change: remove `crewai`, `litellm`, the Weaviate server. Add `flashrank`, `chromadb` (already pinned), `tenacity` (or drop it with Weaviate). Fewer moving parts, fewer servers, smaller image.

---

## 3. Must-have: break the agents into separate scripts with referenced skills

### 3.1 Target layout

```
app/
  agents/
    base.py            # shared: load skill .md, chat(messages, schema)->pydantic, grounding check
    agent_job_matcher.py     # retrieves + reranks + explains matches
    agent_ resume_coach.py    # resume recommendations grounded in matched jobs
    agent_career_strategist.py  # blind spots + strategy, RAG-enhanced
    pipeline.py        # thin orchestrator: match -> (coach || strategist) -> assemble result
    skills/
      job_matcher.md
      resume_coach.md
      career_strategist.md
      _grounding.md    # shared rules every agent imports (anti-hallucination, citation format)
    rag_knowledge.py   # kept; repointed at ChromaDB
  retrieval/           # renamed from app/chroma/ (no more lying name)
    client.py          # ChromaDB embedded client
    embeddings.py      # single backend (bge-small)
    rerank.py          # FlashRank wrapper (new)
  pipeline/            # unchanged engines: matcher, ingest, normalizer, excel_writer, audit, geolocation
```

### 3.2 The skill-per-agent mechanism (what "reference of skills" means here)

Each agent module loads its skill markdown at construction and uses it as the system prompt. A skill file is plain markdown with light YAML frontmatter (the same shape as `ponytail.md`, which you supplied as the model). The agent code stays tiny; the behavior, quality bar, few-shot examples, and output contract live in the editable `.md` file. That is the whole point: you tune the `.md`, not the Python, between test runs.

Sketch (this is the contract the draft skills are written against; not asking you to build it yet):

```python
# app/agents/base.py  — ponytail: ~40 lines, no framework
from pathlib import Path
import httpx
from pydantic import BaseModel

SKILLS = Path(__file__).parent / "skills"

def load_skill(name: str) -> str:
    text = (SKILLS / f"{name}.md").read_text(encoding="utf-8")
    shared = (SKILLS / "_grounding.md").read_text(encoding="utf-8")
    return f"{text}\n\n---\n{shared}"  # ponytail: string concat, not a template engine

def chat(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    r = httpx.post(f"{OLLAMA}/api/chat", json={
        "model": MODEL, "stream": False, "format": schema.model_json_schema(),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }, timeout=180)
    return schema.model_validate_json(r.json()["message"]["content"])
```

The three agents each become a single small file: assemble the user message from retrieved context, call `chat(skill, user, OutputModel)`, run the grounding check, return typed output. No `BaseTool` subclasses, no `Agent`/`Crew`/`Task` objects, no `max_iter` loops.

### 3.3 Draft skill files

Four draft `.md` files ship with this plan (see `app/agents/skills/`), authored from `QUALITY_BENCHMARKS.md` and the three reference outputs so the rubric and the prompt are the same artifact:

- `job_matcher.md` — output contract + the job-results.md exemplar, 90+ rubric encoded.
- `resume_coach.md` — problem -> before -> after -> impact format, priority tags, the resume.md exemplar.
- `career_strategist.md` — evidence-based root-cause + tactical + market-lane recommendations, the career-search.md exemplar.
- `_grounding.md` — shared anti-hallucination contract: only cite retrieved jobs/IDs, never invent companies/salaries, mark estimates as estimates.

These are drafts to iterate on, not final. They are the thing you will edit most during the test loop.

---

## 4. Must-have: consolidate and streamline `app/`

Keep the engines, delete the duplication, rename the lie.

Delete / remove:
- `app/agents/crew.py` -> replaced by `agents/pipeline.py` (orchestrator) + the three agent modules. Net: ~438 lines of orchestration+validation become ~3 small files plus a ~20-line orchestrator.
- `app/agents/tools.py` -> deleted. The "tools" were just JSON-string wrappers around matcher functions; agents call those functions directly now.
- Weaviate code in `app/chroma/client.py` -> replaced by a real ChromaDB embedded client in `app/retrieval/client.py`. The GraphQL string-building goes away.
- `app/agents/llm_provider.py` -> collapses into `base.chat()` plus a one-line model map. Keep the `mock` path for tests; drop the LiteLLM/CrewAI dual wrappers.
- One embedding backend in `app/retrieval/embeddings.py`; remove the Ollama-embed path.

Keep, unchanged or lightly repointed:
- `app/pipeline/matcher.py` (repoint import `app.chroma.client` -> `app.retrieval.client`; add optional rerank call).
- `app/pipeline/{ingest,normalizer,excel_writer,audit,geolocation}.py`.
- `app/agents/rag_knowledge.py` (repoint to ChromaDB).
- `app/{routes,scheduler,validation,config}.py` (config loses the Weaviate block and one of the two collection-name styles).

Outcome: the `app/` tree drops a whole subsystem (Weaviate client + CrewAI tools + provider zoo) while keeping every capability that actually produces user value.

---

## 5. Must-have: kill the Chroma/Weaviate split, settle on one store

Concrete steps:
1. Rename `app/chroma/` -> `app/retrieval/`. Update imports (`matcher.py`, `rag_knowledge.py`, `scripts/ingest_*.py`).
2. Rewrite `client.py` against the ChromaDB embedded API (`chromadb.PersistentClient(path=...)`, `collection.add`, `collection.query`). Keep the existing function names (`query_collection`, `upsert_documents`, `get_or_create_collection`) so the matcher needs no logic change — only the import path.
3. In `config.py`: delete `WEAVIATE_*`; keep a single `CHROMA_DB_PATH` plus the two collection names. Pick one naming convention (`CHROMA_JOBS_COLLECTION` / `CHROMA_RESUME_COLLECTION`) and delete the other.
4. In `requirements.txt`: keep `chromadb`, remove anything Weaviate, and either add `tenacity` or remove its use (with ChromaDB embedded there is no network call to retry, so `tenacity` can simply go — ponytail).
5. `docker-compose.yml`: delete the `weaviate` service and its volume. (Docker is out of scope for the end goal, but leaving a dead service in the file is exactly the kind of contradiction that caused the Phase 2 confusion.)
6. Re-run `scripts/ingest_jobs.py` / `ingest_resume.py` once to build the on-disk Chroma index.

This is the change that makes the repo legible again. After it, "what is the vector store" has exactly one answer.

---

## 6. Must-have: the structured-output / validation rewrite

Replace `_validate_agent_output` (keyword heuristic) and `_extract_numbered_list` (regex) with:

1. **Schema validation** — each agent declares a Pydantic output model (e.g., `JobMatch`, `ResumeRec`, `BlindSpot`). Ollama JSON mode + `schema.model_validate_json` guarantees shape. No regex parsing of free text.
2. **Grounding validation** — a single shared function checks the cheap, real thing: every job/company the agent cites must exist in the retrieved set (match by ID/title against what retrieval returned). This is a true anti-hallucination check, unlike "does the text contain the word python". On failure, you have two honest options per agent: re-ask once with the violating items named, or surface the matcher-only result and flag it. Recommendation: re-ask once, then flag.

This both fixes the quality problem and removes the most confusing code in `crew.py`.

---

## 7. Must-have: the local, outside-the-app runner (the finish line)

The end goal is running agents standalone to tune on results. Add one CLI entry point, no Flask:

```
run_agent.py  --agent job_matcher|resume_coach|career_strategist|all \
              --resume data/synthetic/engineer_resume.txt \
              --role "Senior Data Engineer" --geo "Remote" \
              --jobs data/synthetic/synthetic_jobs.csv \
              --out reports/run_<ts>.json
```

It loads the agent module(s), runs against a persona, writes structured JSON, and (optionally) scores it with the existing `tests/persona_evaluation/evaluation_scoring.py` rubric. This is the loop:

edit `skills/*.md` -> `run_agent.py --agent X --resume persona` -> read JSON + rubric score -> repeat.

Because the agents are framework-free and import cleanly, this runner is ~50 lines and needs nothing from Flask, Docker, or the scheduler. The existing `tests/persona_evaluation/run_phase2_tests.py` harness can be repointed at it to batch all 11 personas.

On fine-tuning specifically (you mentioned SLM fine-tuning): be deliberate here. On 16 GB CPU you can generate and curate training data and iterate prompts/skills cheaply, but you cannot realistically LoRA-fine-tune even a 3B model on CPU in reasonable time. Recommended order: (1) exhaust prompt + skill + RAG + reranker tuning first — for structured tasks this often closes the gap, per your own SLM guide; (2) if a measurable gap remains, use the curated good/bad outputs from the test loop as a dataset and run the actual LoRA fine-tune off-box (rented GPU hour, or Colab), then pull the GGUF back into Ollama. The local loop produces the dataset; the GPU does the training. This keeps the must-have ("run + tune locally") honest about what "tune" means on CPU.

---

## 8. Nice-to-have: the reranker (strongly recommended)

Add a two-stage retrieve-then-rerank to `find_top_jobs`:

1. Bi-encoder (bge-small) retrieves a wide candidate set (e.g., top 50).
2. FlashRank cross-encoder (`ms-marco-MiniLM-L-12-v2`) rescizes to the final top 25 by query-document relevance.

```python
# app/retrieval/rerank.py — ponytail: ~15 lines
from flashrank import Ranker, RerankRequest
_ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")  # ~34MB, cached once

def rerank(query: str, passages: list[dict], top_n: int) -> list[dict]:
    req = RerankRequest(query=query, passages=[{"id": p["id"], "text": p["document"]} for p in passages])
    ranked = _ranker.rerank(req)
    by_id = {p["id"]: p for p in passages}
    return [by_id[r["id"]] for r in ranked[:top_n]]
```

Why FlashRank over `bge-reranker-v2-m3` as the default on 16 GB CPU: FlashRank's MiniLM model is ~34 MB and runs on ONNX without torch, so it is fast on CPU and adds negligible memory. `bge-reranker-v2-m3` is stronger but ~600 MB and noticeably slower on CPU per query. Keep it as a one-line upgrade behind an env var (`RERANK_MODEL`) for when you want max accuracy and can tolerate the latency — exactly the kind of calibration knob worth leaving in.

Expected effect: this is the highest-leverage accuracy change in the whole plan, because it compensates directly for the small embedder and removes weak matches before they ever reach the LLM agents (which also makes the LLM's job easier and its output more groundable).

---

## 9. Nice-to-have: MCP framework guidance

You do not need MCP for the agents to work — the agents call retrieval functions directly, which is laziest and fastest. MCP earns its place if you want to (a) let an external client (e.g., Claude in this app) drive your retrieval/pipeline, or (b) standardize the agent-to-tool boundary for reuse.

If/when you want it, the lazy path:
- Wrap the small set of capabilities you would actually expose — `search_jobs(query, geo, n)`, `query_ats_knowledge(query)`, `append_to_pipeline(jobs)` — as a single FastMCP server (`pip install fastmcp`, ~30 lines, stdio transport).
- The internal agents keep calling the Python functions directly (no IPC overhead in the hot path); the MCP server is a thin facade over the same functions for external callers.
- Defer auth/transport hardening until something external actually connects. (The `mcp-builder` skill in this environment is the reference if you build it.)

Recommendation: design the retrieval functions now with clean signatures (Section 5 keeps the names stable), and only add the MCP facade when there is a concrete external consumer. YAGNI until then.

---

## 10. Nice-to-have: speed without sacrificing accuracy

Ordered by impact-to-effort on CPU:

1. **Run the two downstream agents concurrently.** ResumeCoach and CareerStrategist both depend only on the matched jobs, not on each other. The current code runs all three sequentially. Run match first, then coach and strategist in parallel (threads are fine — the work is a blocking Ollama call). Roughly cuts the LLM critical path from 3 calls to 2.
2. **Keep the model warm.** First Ollama call pays load time. Issue a tiny warmup call at process start in `run_agent.py` and in the Flask worker. Set Ollama `keep_alive` so the model stays resident between requests.
3. **JSON mode removes retries.** Structured output (Section 6) eliminates the parse-fail-and-retry loop that `max_iter=3` was papering over.
4. **Right-size `num_ctx` and `max_tokens`.** The prompts are bounded (top-25 jobs, capped resume). Set `num_ctx` to fit the real context (e.g., 8192) rather than defaulting high, and cap `max_tokens` per agent to its output size. Smaller context = faster CPU decode.
5. **Cache embeddings.** Job embeddings are computed at ingest and stored in Chroma already; ensure query embeddings for repeated personas/roles are cached (`functools.lru_cache` on the query string). Reranking is cheap enough to not cache.
6. **Reranker lets you shrink the LLM's input.** Because rerank surfaces the best 25 from 50, you can feed the agents tighter, higher-quality context — faster decode and better grounding at once.

None of these trade accuracy for speed; items 1-3 and 6 arguably improve both.

---

## 11. Nice-to-have: remove emojis, and other high-impact easy wins

Emoji removal (you asked): strip from `README.md` (~59), `STATUS.md`, and the UI templates in `app/templates/` and any flash messages in `routes.py`. A one-pass script over `*.md` and `*.html` plus the table headers is enough; do it as part of the docs cleanup so it lands once. (STATUS.md itself notes a prior "Replaced emoji with ASCII" fix for test encoding — finish that job everywhere.)

Other easy wins, each small and high-signal:
- Add a real `LICENSE` file (MIT, to match the badge) or drop the badge.
- Fix or remove the five dead README links; reconcile the README "production-ready / 104 tests passing" claim with STATUS.md's "33/33 failing" — pick one truthful status. Recommendation: replace both with one honest STATUS that this plan supersedes.
- Pin/declare all imports: add `tenacity` or remove it; ensure `flashrank` lands in requirements when added; remove `crewai`/`litellm` when the agents are cut over.
- Remove `.pytest_cache/` from version control; confirm `.gitignore` covers it, `.venv/`, `logs/`, `data/*.db`, `data/uploads/`.
- Delete the dead `weaviate` docker service and volume (Section 5.5).
- Collapse the contradictory model list in `llm_provider.py` to the three you will actually use (Qwen2.5-3B default, Phi-3.5-mini, Llama-3.2-3B) plus `mock`.

---

## 12. Phased sequence and definition of done

Each phase is independently shippable and leaves the repo working. Stop after any phase if results are good enough — that is the point of the ordering.

Phase A — Make it legible (no behavior change, lowest risk)
- Rename `app/chroma/` -> `app/retrieval/`, swap Weaviate client for ChromaDB embedded, fix config + requirements + docker, re-ingest. Strip emojis, fix docs/LICENSE/links, drop `.pytest_cache`.
- Done when: `pytest` runs, ingest builds a Chroma index, one search returns jobs, and the repo no longer mentions Weaviate.

Phase B — Replace the agent layer (the core change)
- Add `agents/base.py`, the three agent modules, the four skill files, Pydantic output models, the grounding check. Add `agents/pipeline.py`. Delete `crew.py`, `tools.py`, fold `llm_provider.py` into `base.py`. Repoint `routes.py` at `pipeline.run(...)`.
- Done when: a search runs end-to-end through the new agents with structured output and no CrewAI import remains.

Phase C — Add the reranker
- Add `retrieval/rerank.py`, wire retrieve-then-rerank into `matcher.find_top_jobs`, env-gate the model choice.
- Done when: top-25 are reranked and a before/after on one persona shows the reranked set is at least as relevant.

Phase D — The local test/tune loop (the finish line)
- Add `run_agent.py`; repoint the persona harness at it; wire the rubric scorer to emit per-agent scores to CSV.
- Done when: you can run any agent against any persona from the CLI, get JSON + a rubric score, edit a skill `.md`, and re-run — outside the Flask app, no Docker.

Phase E (optional) — Speed pass, then optional off-box fine-tune
- Parallelize coach+strategist, warm the model, tune `num_ctx`. Only if a measurable quality gap survives Phases B-D, curate the dataset and fine-tune off-box.

Suggested order respects dependencies: A unblocks everything; B depends on A; C and D depend on B; D is the goal; E is polish.

---

## 13. What this plan deliberately does NOT do (and when to revisit)

- **No new agent framework.** Skipped CrewAI/PydanticAI/LangGraph because the flow is a fixed match -> coach+strategist sequence. Add PydanticAI when you genuinely need typed tool-calling or branching control flow; the skills and retrieval layer won't need to change.
- **No MCP server yet.** Skipped until an external consumer exists. The function signatures are kept clean so the facade is a later afternoon, not a rewrite.
- **No CPU fine-tuning.** Skipped because it is not realistic on 16 GB CPU. Revisit off-box once the local loop has produced a curated dataset and prompt/skill/rerank tuning has plateaued.
- **No `bge-reranker-v2-m3` as default.** Left as a one-env-var upgrade for when accuracy matters more than CPU latency.
- **No Flask/UI redesign.** Out of scope; it works. The only UI touch is emoji removal.

The shortest path to your stated goal — three tunable agents you run locally on results — is: settle the vector store (A), replace the discarded-output agent layer with thin grounded calls (B), add the reranker that does the heavy lifting on a small stack (C), and put a CLI in front of it (D). Everything else is optional and named above.
