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

# ── Local LLM (Ollama) ────────────────────────────────────────────────────────
OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL",  "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL",     "qwen2.5:3b")
AGENT_MODEL       = os.getenv("AGENT_MODEL",      "phi4-mini")   # agents default to phi4-mini; override via env

# ── Embedding (single backend: sentence-transformers) ─────────────────────────
EMBED_MODEL       = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

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
