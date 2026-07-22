# Job-Search AI Agent

> **A fully local, open-source job-search assistant powered by ChromaDB and local LLMs (qwen3:4b on most machines, gemma3:12b on a GPU, via Ollama). It auto-detects your computer's hardware and picks the best model for it — no setup choices required. No cloud APIs. No data leaving your machine.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg)](docker-compose.yml)
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-orange.svg)](https://ollama.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5+-purple.svg)](https://trychroma.com)
[![Tests](https://img.shields.io/badge/tests-129%20passing-brightgreen.svg)](tests/)

---

## What It Does

Upload your resume and a jobs spreadsheet, describe the role you're targeting, and the app runs a **3-agent AI pipeline** that returns:

| Output | Count | Description |
|--------|-------|-------------|
| Top Job Matches | 25 | Semantically ranked by cosine similarity to your profile |
| Resume Recommendations | 10 | Specific, ATS-grounded improvements with citations |
| Career Strategist Recommendations | 5 | Blindspots to your search and skills that are in demand, absent from your resume, and guidance on free ways to close each gap |

Results are displayed in a clean web UI, appended to a **job pipeline Excel workbook**, and emailed to you weekly on a Mon–Fri schedule.

---

## New here? Start with this (non-technical guide)

**You do not need to understand any of the code below.** Follow these steps exactly and you'll have it running.

### What you need first
1. A computer (Windows, Mac, or Linux).
2. **Docker Desktop** — this is a free program that runs the app for you. [Download it here](https://www.docker.com/products/docker-desktop/), install it, and **open it once** so it's running (you'll see a little whale icon in your taskbar/menu bar).

### Get it running — copy/paste, one line at a time
Open a terminal (Windows: search "PowerShell" · Mac: search "Terminal"), then paste each line and press Enter:

```bash
git clone https://github.com/PWDevens/job-search-ai-agent.git
cd job-search-ai-agent
cp .env.example .env
docker compose up -d
```

The first time, this takes **5–15 minutes** (it's downloading the app and the AI brain). That's normal. Go get a coffee. ☕

### Tell it which AI brain to download (one time)
Paste this and wait — it grabs the AI model that matches your computer:

```bash
docker compose exec ollama ollama pull qwen3:4b
```

> **You don't pick the model — the app does.** When it runs, it checks whether you have a graphics card (GPU) and automatically chooses the smartest model your machine can handle. See [How the app picks your AI model](#-how-the-app-picks-your-ai-model) for the details. If you have an NVIDIA GPU with ≥10 GB VRAM, also run one extra download: `docker compose exec ollama ollama pull gemma3:12b`

### Load some example data so you can try it immediately
```bash
docker compose exec app python scripts/ingest_jobs.py data/demo/demo_jobs.csv
docker compose exec app python scripts/ingest_resume.py data/demo/demo_resume.txt
```

### Open it
Go to **[http://localhost:5000](http://localhost:5000)** in your web browser. Type a job title, upload your resume (PDF or Word), and click search. Done!

### When you're finished
Type this to shut it down cleanly (your data is saved):
```bash
docker compose down
```
Next time, just run `docker compose up -d` again — no re-downloading.

**Stuck?** Jump to [Troubleshooting](#-troubleshooting-docker-startup) — every common problem has a copy/paste fix.

---

## Project Status

**v1 shipped.** The framework-free 3-agent pipeline, hardware-tiered model selection, ATS full-text
sourcing, and O*NET grounding are all live on `main` and validated by a persona evaluation harness
(see *Why these models?* below and `reports/IMPROVEMENT_LOG.md` for the full iteration history).

- **129 automated tests passing** (`pytest tests/`)
- **8/8 security controls** (input validation, rate limiting, session isolation, etc. — see *Security Features*)
- **Evidence-driven**, not vibes: every major design choice (base model, full-text sourcing, O*NET grounding) was settled by A/B testing against a 14-persona eval, including documented negative results

v2 work (bring-your-own-jobs upload mode, apply-priority scoring) is tracked in `.pipeline/v2_specs.md`.

**Quick Links:**
- [Testing & Debugging Guide](docs/development/testing-guide.md)
- [Improvement Roadmap](docs/development/improvements.md)
- [Deployment Checklist](docs/deployment/01-checklist.md)
- [SLM Fine-Tuning Guide](docs/SLM_FINETUNING_GUIDE.md)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Flask Web UI                         │
│   Role description · Geo preference · Resume · Jobs upload  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Orchestrator  │  ← 3 framework-free agents, sequential
                    │  (pipeline.py) │     + grounding checks + reranker passes
                    └───────┬────────┘
           ┌────────────────┼────────────────┐
           ▼                ▼                ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
   │ JobMatcher   │ │ ResumeCoach  │ │ CareerStrategist  │
   │ Agent        │ │ Agent        │ │ Agent             │
   └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘
          │                │                   │
          ▼                ▼                   ▼
   ┌─────────────────────────────────────────────────────┐
   │              Retrieval + Reranking                   │
   │  matcher (vector search) · rerank (cross-encoder)   │
   │  grounding checks · ATS knowledge (RAG)             │
   └──────────────┬──────────────┬──────────────────────┘
                  │              │
         ┌────────▼────┐  ┌──────▼──────────────┐
         │  ChromaDB   │  │  Ollama LLM         │
         │  (embedded  │  │  (model auto-picked │
         │   vector    │  │   by hardware tier) │
         │   store)    │  │                     │
         └─────────────┘  └─────────────────────┘
                  │
         ┌────────▼────────┐     ┌──────────────┐
         │  jobs           │     │  ATS RAG      │
         │  resume_chunks  │     │  knowledge    │
         │  ats_knowledge  │     │  base (built- │
         └─────────────────┘     │  in articles) │
                                 └───────────────┘
```

**Key design principles:**
- **Zero external APIs** — everything runs in Docker on your laptop
- **ChromaDB** (embedded, on-disk) stores job embeddings, resume chunks, and ATS knowledge articles
- **Local embeddings** via Sentence Transformers (`BAAI/bge-small-en-v1.5`)
- **Framework-free agents** — plain Python orchestration (`app/pipeline/pipeline.py`), no heavy agent framework, with agent-skill prompts in markdown (`app/agents/agent_skills/`)
- **Auto hardware detection** picks the best Ollama model for your CPU/GPU
- **Multi-pass reranker** (1–3 passes) sorts results by relevance
- **Agent validation** prevents hallucination by grounding outputs in actual job data
- **APScheduler** drives weekly Mon–Fri 8 AM pipelines with SMTP email summaries
- **Docker Compose** bundles ChromaDB + Ollama + Flask in a single command
- **Security hardened** with input validation, rate limiting, and session isolation

---

## Quick Start (Docker — Recommended)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
- 8 GB RAM recommended (6 GB minimum with qwen3:4b)
- 6 GB free disk space (for Docker images + model files)

### 1 — Clone and configure
```bash
git clone https://github.com/PWDevens/job-search-ai-agent.git
cd job-search-ai-agent
cp .env.example .env
# Edit .env if you want email summaries (add SMTP_USER / SMTP_PASS)
# Everything else works out of the box
```

### 2 — Start the stack
```bash
docker compose up --build -d
```

This starts ChromaDB, Ollama, and Flask. 
- **First build:** ~5-10 minutes (includes Python dependencies)
- **Startup:** Services become healthy within 2-3 minutes
- **Model download:** First time only, ~5-15 minutes depending on internet

### 3 — Wait for services to be healthy
```bash
# Wait 30 seconds for initial startup
Start-Sleep -Seconds 30

# Check status
docker compose ps

# Expected: All three services show "Up" or "healthy"
```

If Ollama shows "unhealthy", it's still initializing. Wait another 30 seconds.

### 4 — Download the LLM (one-time, automatic on first run)

The first time you start Docker, the system will automatically download the LLM model:

```bash
docker compose exec ollama ollama pull qwen3:4b
```

> **Which model?** The app auto-detects your hardware and picks for you — see [How the app picks your AI model](#-how-the-app-picks-your-ai-model). On most machines, `qwen3:4b` (above) is all you need. With a ≥10 GB NVIDIA GPU, pull `gemma3:12b` instead: `docker compose exec ollama ollama pull gemma3:12b`.

**Alternative:** If you already have Ollama models, add to `.env`:
```bash
OLLAMA_DATA_PATH=C:/path/to/your/ollama-data
```

### 5 — Load demo data
```bash
docker compose exec app python scripts/ingest_jobs.py data/demo/demo_jobs.csv
docker compose exec app python scripts/ingest_resume.py data/demo/demo_resume.txt
```

### 6 — Open the app
```
http://localhost:5000
```

### 7 — Verify everything works
```bash
curl http://localhost:5000/health
# Expected: {"status":"ok","service":"job-search-ai","chroma_db":"healthy"}
```

---

## Troubleshooting Docker Startup

**If Ollama is stuck "unhealthy":**
```bash
# Check Ollama logs
docker compose logs ollama --tail 20

# If no models are loaded, download one:
docker compose exec ollama ollama pull qwen3:4b
```

**If Flask app won't start:**
```bash
# Check Flask logs
docker compose logs app --tail 20

# Restart all services
docker compose restart
```

**To completely reset:**
```bash
docker compose down -v
docker volume prune -f
docker compose up -d
```

---

## Local Development (No Docker)

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/download) installed locally

### Setup
```bash
git clone https://github.com/PWDevens/job-search-ai-agent.git
cd job-search-ai-agent

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set OLLAMA_BASE_URL=http://localhost:11434
```

> **No ChromaDB server needed.** The app uses ChromaDB in *embedded* mode — it reads/writes a folder on disk (`data/chroma/`) automatically. Nothing to start.

### Start Ollama and pull models
```bash
# Install Ollama: https://ollama.com/download
ollama serve                          # starts Ollama server (background)
ollama pull qwen3:4b                 # ~3 GB; the app auto-selects this on CPU/iGPU
# Embeddings run locally via Sentence Transformers — no embedding model to pull.
```

### Run the Flask app
```bash
# Ingest demo data
python scripts/ingest_jobs.py data/demo/demo_jobs.csv
python scripts/ingest_resume.py data/demo/demo_resume.txt

# Start app (with scheduler)
ENABLE_SCHEDULER=true python run.py

# Or without scheduler (dev mode)
FLASK_DEBUG=true python run.py
```

---

## Supported Input Formats

### Jobs file (CSV or XLSX)
Required columns: `title`, `company`, `description`
Optional columns: `location`, `url`, `salary`, `date_posted`, `source`

```csv
title,company,location,description,salary,url,date_posted
Senior Data Engineer,Acme Corp,Washington DC,"Build pipelines with Python and Spark",130000,https://...,2026-05-20
```

### Resume
- **PDF** (text-based, not scanned) — recommended
- **TXT** — plain text
- **DOCX** — Word document

---

## Configuration

All settings live in `.env`. Key options:

| Variable | Default | Description |
|----------|---------|-------------|
| `HARDWARE_TIER` | _(auto-detected)_ | Force a tier: `cpu` · `gpu_avg` · `gpu_modern`. Leave unset to auto-detect. |
| `AGENT_MODEL` | _(from tier)_ | Exact Ollama model to use. Overrides tier selection. |
| `OLLAMA_NUM_CTX` | `8192` | LLM context window. Must be ≥ 8192 — the job-matcher prompt is ~5,200 tokens, and the agents fail silently if it's truncated. Only lower on RAM-constrained CPUs (may degrade quality). |
| `RERANK_PASSES` | `2` | Reranker iterations: `1` (fast) · `2` (balanced) · `3` (best quality) |
| `RERANK_MODEL` | `ms-marco-MiniLM-L-12-v2` | Reranker model; set `none` to disable reranking |
| `TOP_JOBS` | `25` | Number of job matches to return |
| `TOP_RESUME_RECS` | `10` | Number of resume recommendations |
| `TOP_BLIND_SPOTS` | `5` | Number of blind spots to identify |
| `UPLOAD_RETENTION_HOURS` | `24` | Auto-cleanup interval for upload files |
| `SCHEDULER_CRON` | `0 8 * * 1-5` | Cron schedule (default: Mon–Fri 8 AM) |
| `SCHEDULER_TZ` | `America/New_York` | Timezone for scheduled runs |
| `EMAIL_TO` | `p.w.devens@gmail.com` | Weekly summary recipient |
| `SECRET_KEY` | (random) | Flask session key (auto-generated if not set) |

---

## How the app picks your AI model

**You don't choose a model — the app detects your hardware on startup and picks the best one automatically.** It runs `nvidia-smi` once to see if you have an NVIDIA graphics card (GPU) and how much memory it has, then selects:

| Your computer | Tier | Model it uses | What to download |
|---------------|------|---------------|------------------|
| No GPU / iGPU / Apple Silicon (most laptops) | `cpu` | **qwen3:4b** | `ollama pull qwen3:4b` |
| NVIDIA GPU < 10 GB VRAM | `gpu_avg` | **qwen3:4b** | `ollama pull qwen3:4b` |
| NVIDIA GPU ≥ 10 GB VRAM | `gpu_modern` | **gemma3:12b** | `ollama pull gemma3:12b` |

`qwen3:4b` is a small (~3 GB) reasoning model that runs fast on almost any machine; `gemma3:12b` (~8 GB) is reserved for real GPUs with headroom.

**Want to override it?** Set these in your `.env` file (most people never need to):

```bash
HARDWARE_TIER=gpu_avg        # force a tier: cpu | gpu_avg | gpu_modern
AGENT_MODEL=gemma3:12b       # or name an exact Ollama model (wins over tier)
```

> **Non-technical translation:** Leave it alone and it just works. If you have a graphics card, the assistant runs faster — automatically.

### Why these models?

In June 2026 we ran a **13-model bake-off** on the full job-search pipeline — same corpus, same test users, varying only the model — measuring answer *quality* (not just speed) across both career-switch and stay-in-field users. The headline: **the base model is the single biggest quality lever**, worth ~**+0.76–0.79 overall** versus the previous default (`llama3.1:8b`, which ranked near the bottom).

| Model | Origin | Quality | Notes |
|-------|--------|---------|-------|
| **qwen3:4b** | Alibaba | **best** | Best overall *and* smallest (4B); fast everywhere → the default |
| **gemma3:12b** | Google (US) | ~tied for #1 | The pick for real GPUs |
| gpt-oss:20b | OpenAI (US) | strong but uneven | Great on switchers, regressed on stay-in-field |
| llama3.1:8b (previous) | Meta | near bottom | The model v1 replaced |

Surprises worth knowing: **scaling backfired** (qwen3 4B > 8B > 14B > 30B-MoE — the *small* reasoning model won), and a model that looked great on one user type regressed on the other (which is why both are tested). All models need a context window ≥ 8,192 tokens — the app sets `OLLAMA_NUM_CTX=8192` automatically, because the job-matcher prompt (~5,200 tokens) is silently truncated and breaks at the old 4,096 default.

> **License note:** `qwen3` is Apache 2.0; `gemma3` is under [Google's Gemma Terms of Use](https://ai.google.dev/gemma/terms) (permissive, with an acceptable-use policy). Check each model's card before redistributing.

---

## Reranking — how results get sorted by quality

After the AI suggests jobs and advice, the app runs a **local reranker** (a small scoring model) one to three times to push the most relevant results to the top. This is controlled by one setting:

```bash
RERANK_PASSES=2     # 1 = fast, 2 = balanced (default), 3 = highest quality
```

- **Pass 1** — sorts the raw job matches.
- **Pass 2** — re-sorts the shortlist using your job target *and* your resume together.
- **Pass 3** (optional) — re-sorts your resume tips by how well they fit your actual resume.

More passes = slightly slower but more accurate. The default of `2` is the sweet spot.

> _Advanced/developer note:_ to test all three hardware tiers on a cloud box (without owning each GPU), the `staging` branch ships `docker-compose.staging.yml`. Force any tier with `HARDWARE_TIER`:
> ```bash
> HARDWARE_TIER=gpu_modern docker compose -f docker-compose.yml -f docker-compose.staging.yml up
> ```
> A quick no-Ollama smoke test of all tiers: `python scripts/test_hardware_profiles.py`

---

## Running Tests

```bash
# Install test deps (included in requirements.txt)
pip install pytest pytest-cov

# Run all tests (no live services required — external calls are mocked)
pytest tests/ -v --cov=app --cov-report=html

# Run specific test files
pytest tests/test_config_and_base.py -v   # hardware tier + model selection + config
pytest tests/test_merge_fix.py -v          # job merge logic
pytest tests/test_run_agent.py -v          # end-to-end mock pipeline

# Try the whole pipeline end-to-end with no Ollama or GPU:
python run_agent.py --role "Data Engineer" --resume data/demo/demo_resume.txt --mock
```

**Test notes:**
- Tests mock all external services (safe to run in CI).
- On Windows, some `tmp_path`-based tests may error under certain pytest-asyncio versions — this is an environment/plugin issue, not the app.

### GitHub Actions CI (`.github/workflows/test.yml`)
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=app
```

---

## Email Setup (Gmail App Password)

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** (required)
3. Search for **App passwords** → create one for "Mail"
4. Copy the 16-character password into `.env`:
   ```
   SMTP_USER=your.email@gmail.com
   SMTP_PASS=abcd efgh ijkl mnop
   ```
5. Email summaries will be sent every weekday at 8 AM ET (configurable).

---

## SLM Quality & RAG Strategy

This app uses three layers to compensate for small model limitations:

1. **ATS Knowledge RAG** (built-in): 11 curated articles on ATS parsers, resume formatting, AI screening, skills-based hiring, and more — injected into every agent's context via ChromaDB.
2. **Grounded job data**: All factual claims (job titles, companies, salaries) come from ChromaDB query results, not model memory — eliminating hallucination for structured facts. Agent outputs are validated to ensure grounding.
3. **Fine-tuning option**: See [`docs/SLM_FINETUNING_GUIDE.md`](docs/SLM_FINETUNING_GUIDE.md) for a complete QLoRA fine-tuning walkthrough for Phi-4-mini.

---

## Project Structure

```
job-search-ai-agent/
├── README.md                    # This file
├── .pipeline/                   # Session handoffs, specs, iteration history (dev-facing)
├── docs/                        # Guides (deployment, testing, fine-tuning)
│   ├── SLM_FINETUNING_GUIDE.md
│   ├── deployment/              # Checklist, report, status, verification
│   └── development/             # testing-guide.md, improvements.md
│
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # All settings (env-driven)
│   ├── routes.py                # Flask routes (5 endpoints)
│   ├── validation.py            # Input validation + rate limiting
│   ├── scheduler.py             # APScheduler weekly pipeline
│   ├── hardware.py              # Hardware-tier detection → model selection
│   ├── agents/
│   │   ├── base.py              # chat() + load_skill() + context helpers
│   │   ├── agent_job_matcher.py        # Job-matching agent
│   │   ├── agent_resume_coach.py        # Resume-advice agent
│   │   ├── agent_career_strategist.py   # Blind-spot / strategy agent
│   │   ├── grounding.py         # Citation grounding checks
│   │   ├── models.py            # Pydantic output schemas
│   │   ├── rag_knowledge.py     # ATS knowledge base (11 articles)
│   │   └── skills/              # Agent prompts as markdown (.md)
│   ├── retrieval/
│   │   ├── client.py            # ChromaDB embedded client
│   │   ├── embeddings.py        # Local Sentence Transformers embedding
│   │   └── rerank.py            # FlashRank cross-encoder reranker
│   ├── email/
│   │   └── sender.py            # SMTP email (HTML + XLSX)
│   ├── pipeline/
│   │   ├── pipeline.py          # Orchestrator (3 agents + reranker passes)
│   │   ├── ingest.py            # Job/resume ingestion
│   │   ├── matcher.py           # Semantic search (optimized)
│   │   ├── geolocation.py       # Location normalization
│   │   ├── audit.py             # SQLite audit logging
│   │   ├── excel_writer.py      # Output XLSX generation
│   │   └── normalizer.py        # CSV header normalization
│   ├── templates/
│   │   ├── index.html           # Search form
│   │   └── results.html         # Results (jobs/resume/blind spots)
│   └── static/css/style.css     # Styling
│
├── scripts/
│   ├── ingest_jobs.py           # CLI: ingest jobs CSV/XLSX
│   ├── ingest_resume.py         # CLI: ingest resume PDF/TXT
│   └── pull_models.sh           # Download Ollama models
│
├── tests/                        # 129 tests
│   ├── conftest.py              # Shared fixtures
│   ├── test_ingest.py           # Ingestion tests (27 cases)
│   ├── test_matcher.py          # Matching tests (18 cases)
│   ├── test_config_and_base.py # Hardware tier + config + base tests
│   ├── test_merge_fix.py        # Job merge logic tests
│   ├── test_run_agent.py        # End-to-end mock pipeline tests
│   ├── test_audit.py            # Audit logging tests (16+ cases)
│   ├── test_email.py            # Email tests (20+ cases)
│   ├── test_excel_writer.py     # Excel writer tests (10 cases)
│   └── test_pipeline_integration.py  # End-to-end tests (12 cases)
│
├── data/
│   ├── demo/
│   │   ├── demo_jobs.csv        # 25 real DC-area AI/data jobs
│   │   └── demo_resume.txt      # Sample resume for testing
│   ├── uploads/                 # User uploads (per-session)
│   └── audit.db                 # SQLite audit trail (created at runtime)
│
├── docs/
│   └── SLM_FINETUNING_GUIDE.md  # Phi-4-mini QLoRA walkthrough
│
├── docker-compose.yml           # Service orchestration
├── Dockerfile                   # Multi-stage build
├── requirements.txt             # Python dependencies
├── .env.example                 # Configuration template
├── .gitignore                   # Exclude .env, logs, uploads
├── LICENSE                      # MIT License
└── run.py                       # Application entry point
```

---

## Security Features

All implemented and verified:

- **Input validation**: Role, geo preference, file size (16MB limit)
- **SQL injection protection**: Dangerous pattern detection
- **Rate limiting**: 10 searches/minute per session (DoS prevention)
- **Session isolation**: UUID-based upload directories
- **Secret management**: Random SECRET_KEY generation
- **Data privacy**: Resume content never logged (MD5 hash only)
- **Error handling**: No stack traces to users
- **Audit trail**: Full SQLite logging of all searches
- **Service health**: ChromaDB timeout (10s) + retry with backoff

---

## Troubleshooting

**For detailed troubleshooting:** See [the Testing & Debugging guide](docs/development/testing-guide.md)

### "ChromaDB connection refused"
```bash
# Check ChromaDB is running
docker compose ps
curl http://localhost:8000/api/v1/heartbeat

# Restart if needed
docker compose restart chromadb
```

### "Ollama model not found"
```bash
# Pull the model
docker compose exec ollama ollama pull qwen3:4b
# Or for local dev:
ollama pull qwen3:4b
```

### "No jobs found" after search
```bash
# Make sure you've ingested jobs first
python scripts/ingest_jobs.py data/demo/demo_jobs.csv
# Check collection count
python -c "
from app.retrieval.client import get_or_create_collection
print('Jobs in DB:', get_or_create_collection('jobs').count())
"
```

### "PDF extraction failed"
The app supports PDF, TXT, and DOCX. For scanned PDFs without OCR, convert to searchable PDF first or use TXT instead. See [the Testing & Debugging guide](docs/development/testing-guide.md) for detailed PDF debugging.

### "Agent validation failed" (using fallback results)
This is normal — when agent outputs don't match actual job data, the app falls back to matcher results. See [the Improvements roadmap](docs/development/improvements.md) for how to improve validation in the future.

### Slow performance on CPU
- On CPU the app already uses the lightweight `qwen3:4b` automatically — this is expected to take ~10–20s per search.
- Speed it up: set `RERANK_PASSES=1` in `.env` (fewer reranker passes), and/or reduce `TOP_JOBS=10` to cut search time.
- For real speed, run on a machine with an NVIDIA GPU — with ≥10 GB VRAM the app detects it and switches to `gemma3:12b` automatically.

### Email not sending
- Verify `SMTP_USER` and `SMTP_PASS` are set in `.env`
- For Gmail: use an App Password (not your main password), requires 2FA enabled
- Test SMTP config: `python -c "from app.email.sender import _send; print('SMTP module loaded')"`

### "Too many searches" (rate limited)
- This is intentional (10/minute per session to prevent abuse)
- Wait 1 minute and try again
- Can be configured in `app/routes.py`: `_check_rate_limit(max_per_minute=10)`

---

## Performance

| Operation | Baseline | After Optimization | Speedup |
|-----------|----------|---|---|
| Skill extraction (500 jobs) | 2-5s | 200-500ms | **10-25x** |
| Resume chunking | ~2s | ~1s | 2x |
| Full search (end-to-end) | ~15s | ~10s | 1.5x |

Key optimizations:
- Compiled regex for skill matching (O(k) instead of O(n*m))
- Semantic resume chunking (respects section boundaries)
- Intelligent geolocation filtering (lazy evaluation)
- ChromaDB connection pooling with timeout

---

## Contributing

This is an open-source tool built for job seekers. Contributions welcome:

- **More knowledge base articles** in `app/agents/rag_knowledge.py`
- **New data sources** (LinkedIn scraper, Indeed RSS, USAJobs API)
- **Better demo datasets** covering different industries/locations
- **UI improvements** (dark/light theme, saved searches, comparison view)
- **Tests** for the agents layer (requires mock LLM integration)
- **Performance optimizations** (vector search, caching, etc.)

See [the Improvements roadmap](docs/development/improvements.md) for a prioritized roadmap.

Please open an issue before submitting large PRs.

---

## License

MIT License — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

## Built With

| Tool | Purpose | License |
|------|---------|---------|
| [ChromaDB](https://trychroma.com) | Local vector database (embedded) | Apache 2.0 |
| [Ollama](https://ollama.com) | Local LLM server | MIT |
| [qwen3:4b](https://ollama.com/library/qwen3) (CPU/small GPU) / [gemma3:12b](https://ollama.com/library/gemma3) (GPU ≥10 GB) | Hardware-tiered SLMs | Apache 2.0 / Gemma Terms |
| [FlashRank](https://github.com/PrithivirajDamodaran/FlashRank) | Local cross-encoder reranker | Apache 2.0 |
| [Sentence Transformers](https://sbert.net) | Local CPU embeddings | Apache 2.0 |
| [Flask](https://flask.palletsprojects.com) | Web framework | BSD |
| [APScheduler](https://apscheduler.readthedocs.io) | Weekly scheduler | MIT |
| [Bootstrap 5](https://getbootstrap.com) | UI framework | MIT |

---

## Documentation

**Quick Links:**
- [Testing & Debugging](docs/development/testing-guide.md) — How to test locally
- [Improvements Roadmap](docs/development/improvements.md) — Future features
- [Deployment Checklist](docs/deployment/01-checklist.md) — Pre-deployment verification
- [SLM Fine-Tuning Guide](docs/SLM_FINETUNING_GUIDE.md) — QLoRA walkthrough

---

*Built by [Patrick Devens](https://github.com/PWDevens) · Washington, DC · 2026*  
*Free tool for job seekers competing in a tough market. Star ⭐ if this helped you.*

**Status:** ✅ v1 shipped · **Tests:** 129 passing
