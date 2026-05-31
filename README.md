# 🤖 Job-Search AI

> **A fully local, open-source job-search assistant powered by ChromaDB, CrewAI, and local LLMs (Phi-4-mini / Llama-3 / Mistral via Ollama). No cloud APIs. No data leaving your machine.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg)](docker-compose.yml)
[![CrewAI](https://img.shields.io/badge/CrewAI-0.80+-orange.svg)](https://crewai.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5+-purple.svg)](https://trychroma.com)

---

## ✨ What It Does

Upload your resume and a jobs spreadsheet, describe the role you're targeting, and the app runs a **3-agent AI pipeline** that returns:

| Output | Count | Description |
|--------|-------|-------------|
| 🏆 Top Job Matches | 25 | Semantically ranked by cosine similarity to your profile |
| 📝 Resume Recommendations | 10 | Specific, ATS-grounded improvements with citations |
| 🔦 Blind Spots | 5 | Skills in demand that are absent from your resume + free ways to close each gap |

Results are displayed in a clean web UI, appended to a **job pipeline Excel workbook**, and emailed to you weekly on a Mon–Fri schedule.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Flask Web UI                         │
│   Role description · Geo preference · Resume · Jobs upload  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  CrewAI Crew   │  ← 3 agents, sequential
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
   │                   Local Tools                        │
   │  JobSearchTool · ResumeMatchTool · BlindSpotTool    │
   │  ATSKnowledgeTool (RAG) · PipelineWriterTool        │
   └──────────────┬──────────────┬──────────────────────┘
                  │              │
         ┌────────▼────┐  ┌──────▼────────┐
         │  ChromaDB   │  │  Ollama LLM   │
         │  (vector    │  │  (Phi-4-mini  │
         │   store)    │  │  / Llama-3)   │
         └─────────────┘  └───────────────┘
                  │
         ┌────────▼────────┐     ┌──────────────┐
         │  jobs           │     │  ATS RAG      │
         │  resume_chunks  │     │  knowledge    │
         │  ats_knowledge  │     │  base (built- │
         └─────────────────┘     │  in articles) │
                                 └───────────────┘
```

**Key design principles:**
- 🔒 **Zero external APIs** — everything runs in Docker on your laptop
- 📦 **ChromaDB** stores job embeddings, resume chunks, and ATS knowledge articles
- 🧠 **Local embeddings** via Ollama `nomic-embed-text` or Sentence Transformers fallback
- 🤖 **CrewAI** orchestrates agents with proper context passing and tool use
- 📧 **APScheduler** drives weekly Mon–Fri 8 AM pipelines with SMTP email summaries
- 🐳 **Docker Compose** bundles ChromaDB + Ollama + Flask in a single command

---

## 🚀 Quick Start (Docker — Recommended)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
- 8 GB RAM recommended (6 GB minimum with Phi-4-mini)
- 6 GB free disk space (for Docker images + model files)

### 1 — Clone and configure
```bash
git clone https://github.com/pwdevens/job-search-ai.git
cd job-search-ai
cp .env.example .env
# Edit .env if you want email summaries (add SMTP_USER / SMTP_PASS)
# Everything else works out of the box
```

### 2 — Start the stack
```bash
docker compose up --build -d
```
This starts ChromaDB, Ollama, and the Flask app. First build takes ~3–5 minutes.

### 3 — Download the LLM (one-time setup)
```bash
bash scripts/pull_models.sh            # downloads phi4-mini + nomic-embed-text
# OR for better quality (needs 8 GB RAM):
bash scripts/pull_models.sh llama3
```
> **Model sizes:** `phi4-mini` = ~2.5 GB · `nomic-embed-text` = ~0.3 GB · `llama3` = ~4.7 GB

### 4 — Load the demo jobs
```bash
docker compose exec app python scripts/ingest_jobs.py data/demo/demo_jobs.csv
docker compose exec app python scripts/ingest_resume.py data/demo/demo_resume.txt
```

### 5 — Open the app
```
http://localhost:5000
```

---

## 💻 Local Development (No Docker)

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/download) installed locally

### Setup
```bash
git clone https://github.com/pwdevens/job-search-ai.git
cd job-search-ai

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set CHROMA_HOST=localhost, OLLAMA_BASE_URL=http://localhost:11434
```

### Start ChromaDB locally
```bash
# Install ChromaDB CLI
pip install chromadb

# Start persistent server
chroma run --path ./chroma_data --port 8000
```

### Start Ollama and pull models
```bash
# Install Ollama: https://ollama.com/download
ollama serve                          # starts Ollama server (background)
ollama pull phi4-mini                 # ~2.5 GB download
ollama pull nomic-embed-text          # ~0.3 GB download
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

## 📊 Supported Input Formats

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

## ⚙️ Configuration

All settings live in `.env`. Key options:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BACKEND` | `phi4_mini` | `phi4_mini` · `llama3` · `mistral` · `tinyllama` · `mock` |
| `EMBED_BACKEND` | `ollama` | `ollama` (nomic-embed-text) or `sentence_transformers` |
| `TOP_JOBS` | `25` | Number of job matches to return |
| `TOP_RESUME_RECS` | `10` | Number of resume recommendations |
| `TOP_BLIND_SPOTS` | `5` | Number of blind spots to identify |
| `SCHEDULER_CRON` | `0 8 * * 1-5` | Cron schedule (default: Mon–Fri 8 AM) |
| `SCHEDULER_TZ` | `America/New_York` | Timezone for scheduled runs |
| `EMAIL_TO` | `p.w.devens@gmail.com` | Weekly summary recipient |

### LLM options by machine spec

| Machine | Recommended LLM | RAM Usage | Notes |
|---------|----------------|-----------|-------|
| <4 GB RAM | `tinyllama` or `llama3.2:1b` | ~2 GB | Demo quality only; use RAG heavily |
| 4–6 GB RAM | `phi4_mini` | ~3.5 GB | ✅ Best choice for constrained machines |
| 6–10 GB RAM | `llama3` | ~6 GB | ✅ Recommended for quality results |
| 10+ GB RAM | `llama3` or `mistral` | 6–8 GB | Comfortable headroom |
| NVIDIA GPU | `llama3` (GPU) | 4–6 GB VRAM | Uncomment GPU block in docker-compose.yml |

---

## 🧪 Running Tests

```bash
# Install test deps (included in requirements.txt)
pip install pytest pytest-mock

# Run all tests (no live services required)
LLM_BACKEND=mock EMBED_BACKEND=sentence_transformers pytest tests/ -v

# Run specific test file
pytest tests/test_ingest.py -v
pytest tests/test_matcher.py -v
pytest tests/test_email.py -v
```

Tests mock all external services (ChromaDB, Ollama, SMTP). Safe to run in CI.

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
      - run: pytest tests/ -v
        env:
          LLM_BACKEND: mock
          EMBED_BACKEND: sentence_transformers
          CHROMA_HOST: localhost
```

---

## 📧 Email Setup (Gmail App Password)

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

## 🧠 SLM Quality & RAG Strategy

This app uses three layers to compensate for small model limitations:

1. **ATS Knowledge RAG** (built-in): 11 curated articles on ATS parsers, resume formatting, AI screening, skills-based hiring, and more — injected into every agent's context via ChromaDB.
2. **Grounded job data**: All factual claims (job titles, companies, salaries) come from ChromaDB query results, not model memory — eliminating hallucination for structured facts.
3. **Fine-tuning option**: See [`docs/SLM_FINETUNING_GUIDE.md`](docs/SLM_FINETUNING_GUIDE.md) for a complete QLoRA fine-tuning walkthrough for Phi-4-mini.

---

## 📁 Project Structure

```
job-search-ai/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # All settings (env-driven)
│   ├── routes.py            # Flask routes
│   ├── scheduler.py         # APScheduler weekly pipeline
│   ├── agents/
│   │   ├── crew.py          # CrewAI orchestration (3 agents, 3 tasks)
│   │   ├── tools.py         # Custom CrewAI tools
│   │   ├── llm_provider.py  # Ollama/LLM abstraction layer
│   │   └── rag_knowledge.py # ATS knowledge base (11 articles)
│   ├── chroma/
│   │   ├── client.py        # ChromaDB HTTP client wrapper
│   │   └── embeddings.py    # Local embedding (Ollama / ST fallback)
│   ├── email/
│   │   └── sender.py        # SMTP email with HTML template + XLSX attach
│   ├── pipeline/
│   │   ├── ingest.py        # Job CSV/XLSX + resume PDF/TXT ingestion
│   │   ├── matcher.py       # Semantic matching engine
│   │   └── excel_writer.py  # Deduplicated pipeline XLSX writer
│   ├── templates/
│   │   ├── index.html       # Search form
│   │   └── results.html     # Tabbed results (jobs / resume / blind spots)
│   └── static/css/style.css
├── scripts/
│   ├── ingest_jobs.py       # CLI: ingest jobs CSV/XLSX
│   ├── ingest_resume.py     # CLI: ingest resume PDF/TXT
│   └── pull_models.sh       # Download Ollama models
├── tests/
│   ├── conftest.py          # Shared fixtures + env setup
│   ├── test_ingest.py       # Ingestion pipeline tests
│   ├── test_matcher.py      # Matching engine tests
│   └── test_email.py        # Email sender tests
├── data/demo/
│   ├── demo_jobs.csv        # 25 real DC-area AI/data job postings
│   └── demo_resume.txt      # Sample resume for testing
├── docs/
│   └── SLM_FINETUNING_GUIDE.md  # Phi-4-mini QLoRA fine-tuning walkthrough
├── docker-compose.yml       # ChromaDB + Ollama + Flask
├── Dockerfile               # Multi-stage Flask container
├── requirements.txt
├── .env.example             # Copy to .env and fill in values
├── .gitignore
└── run.py                   # App entry point
```

---

## 🛠️ Troubleshooting

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
docker compose exec ollama ollama pull phi4-mini
# Or for local dev:
ollama pull phi4-mini
```

### "No jobs found" after search
```bash
# Make sure you've ingested jobs first
python scripts/ingest_jobs.py data/demo/demo_jobs.csv
# Check collection count
python -c "
import os; os.environ['CHROMA_HOST']='localhost'
from app.chroma.client import jobs_collection
print('Jobs in DB:', jobs_collection().count())
"
```

### Slow performance on CPU
- Switch to a smaller model: set `LLM_BACKEND=llama3_1b` or `LLM_BACKEND=tinyllama` in `.env`
- Switch to ST embeddings: set `EMBED_BACKEND=sentence_transformers` (faster on CPU than Ollama embed)
- Reduce `TOP_JOBS=10` to cut search time

### Email not sending
- Verify `SMTP_USER` and `SMTP_PASS` are set in `.env`
- For Gmail: use an App Password (not your main password), requires 2FA enabled
- Test SMTP config: `python -c "from app.email.sender import _send; print('SMTP module loaded')"`

---

## 🤝 Contributing

This is an open-source tool built for job seekers. Contributions welcome:

- **More knowledge base articles** in `app/agents/rag_knowledge.py`
- **New data sources** (LinkedIn scraper, Indeed RSS, USAJobs API)
- **Better demo datasets** covering different industries/locations
- **UI improvements** (dark/light theme toggle, saved searches, comparison view)
- **Tests** for the agents layer (requires mock LLM integration)

Please open an issue before submitting large PRs.

---

## 📄 License

MIT License — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

## 🙏 Built With

| Tool | Purpose | License |
|------|---------|---------|
| [CrewAI](https://crewai.com) | Multi-agent orchestration | MIT |
| [ChromaDB](https://trychroma.com) | Local vector database | Apache 2.0 |
| [Ollama](https://ollama.com) | Local LLM server | MIT |
| [Phi-4-mini](https://huggingface.co/microsoft/Phi-4-mini-instruct) | Default SLM | MIT |
| [Sentence Transformers](https://sbert.net) | CPU embedding fallback | Apache 2.0 |
| [Flask](https://flask.palletsprojects.com) | Web framework | BSD |
| [APScheduler](https://apscheduler.readthedocs.io) | Weekly scheduler | MIT |
| [Bootstrap 5](https://getbootstrap.com) | UI framework | MIT |

---

*Built by [Patrick Devens](https://github.com/pwdevens) · Washington, DC · 2026*
*Free tool for job seekers competing in a tough market. Star ⭐ if this helped you.*
