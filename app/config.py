"""
Central configuration — reads from environment variables with sensible defaults.
All secrets belong in .env (never committed).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Vector store (ChromaDB embedded, on-disk) ────────────────────────────────
CHROMA_DB_PATH     = os.getenv("CHROMA_DB_PATH", str(BASE_DIR / "data" / "chroma"))
CHROMA_JOBS_COL    = os.getenv("CHROMA_JOBS_COLLECTION",   "jobs")
CHROMA_RESUME_COL  = os.getenv("CHROMA_RESUME_COLLECTION", "resume_chunks")

# ── Hardware tier + model selection ──────────────────────────────────────────
from app import hardware as _hw

HARDWARE_TIER = os.getenv("HARDWARE_TIER") or _hw.detect_tier()
# AGENT_MODEL: env override → hardware-selected quantized model
AGENT_MODEL   = os.getenv("AGENT_MODEL")   or _hw.select_model(HARDWARE_TIER)

# ── Local LLM (Ollama) ────────────────────────────────────────────────────────
OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL",  "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL",     "qwen2.5:3b")

# Ollama inference options (override via env — for hardware simulation + reproducible evals)
def _int_or_none(v):
    return int(v) if v not in (None, "") else None

OLLAMA_NUM_GPU    = _int_or_none(os.getenv("OLLAMA_NUM_GPU"))     # None=auto, 0=force CPU, N=GPU layers (cap to mimic smaller VRAM)
OLLAMA_NUM_THREAD = _int_or_none(os.getenv("OLLAMA_NUM_THREAD"))  # cap CPU threads to mimic an average CPU
OLLAMA_NUM_CTX    = int(os.getenv("OLLAMA_NUM_CTX",      "4096"))
OLLAMA_TEMPERATURE= float(os.getenv("OLLAMA_TEMPERATURE", "0.2")) # set 0.0 for greedy/reproducible eval baselines

# ── Embedding (single backend: sentence-transformers) ─────────────────────────
EMBED_MODEL       = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# ── Reranker passes (1 = retrieval only; 2 = +role+resume; 3 = +resume recs) ─
RERANK_PASSES = int(os.getenv("RERANK_PASSES", "2"))

# ── Context window sizes (chars) — tunable per hardware/model capacity ────────
RESUME_SNIPPET_CHARS = int(os.getenv("RESUME_SNIPPET_CHARS", "600"))
RESUME_MID_CHARS     = int(os.getenv("RESUME_MID_CHARS",     "1500"))
RESUME_FULL_CHARS    = int(os.getenv("RESUME_FULL_CHARS",    "3000"))
JOB_CONTEXT_CHARS    = int(os.getenv("JOB_CONTEXT_CHARS",    "400"))

# ── Pipeline output ───────────────────────────────────────────────────────────
PIPELINE_XLSX     = os.getenv("PIPELINE_XLSX", str(BASE_DIR / "data" / "job_pipeline.xlsx"))
TOP_JOBS          = int(os.getenv("TOP_JOBS",          "25"))
TOP_RESUME_RECS   = int(os.getenv("TOP_RESUME_RECS",   "10"))
TOP_BLIND_SPOTS   = int(os.getenv("TOP_BLIND_SPOTS",    "5"))

# ── Email / SMTP ──────────────────────────────────────────────────────────────
SMTP_HOST         = os.getenv("SMTP_HOST",         "smtp.gmail.com")
SMTP_PORT         = int(os.getenv("SMTP_PORT",      "587"))
SMTP_USER         = os.getenv("SMTP_USER",          "")
SMTP_PASS         = os.getenv("SMTP_PASS",          "")
EMAIL_TO          = os.getenv("EMAIL_TO",           "p.w.devens@gmail.com")
SMTP_USE_TLS      = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_TZ      = os.getenv("SCHEDULER_TZ",  "America/New_York")
SCHEDULER_CRON    = os.getenv("SCHEDULER_CRON", "0 8 * * 1-5")    # Mon-Fri 08:00

# ── Flask ─────────────────────────────────────────────────────────────────────
_SECRET_KEY_ENV = os.getenv("SECRET_KEY")
if not _SECRET_KEY_ENV or _SECRET_KEY_ENV == "change-me-in-production":
    # Generate random SECRET_KEY if not configured (security best practice)
    import secrets
    SECRET_KEY = secrets.token_urlsafe(32)
    import logging
    logging.getLogger(__name__).warning(
        "WARNING: SECRET_KEY not configured. Generated random key for this session. "
        "Set SECRET_KEY environment variable in .env for persistent key across restarts."
    )
else:
    SECRET_KEY = _SECRET_KEY_ENV

UPLOAD_FOLDER        = BASE_DIR / "data" / "uploads"
MAX_CONTENT_BYTES    = 16 * 1024 * 1024   # 16 MB
UPLOAD_RETENTION_HOURS = int(os.getenv("UPLOAD_RETENTION_HOURS", "24"))

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
