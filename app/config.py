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
CHROMA_SKILLS_COL  = os.getenv("CHROMA_SKILLS_COLLECTION", "skills")

# ── Skills taxonomy layer (occupation competencies; see app/skills/) ──────────
SKILLS_DB_PATH     = os.getenv("SKILLS_DB_PATH", str(BASE_DIR / "data" / "skills" / "skills.db"))
SKILL_MATCH_FLOOR  = float(os.getenv("SKILL_MATCH_FLOOR", "0.70"))  # embedding-NN cosine floor (precision-first; calibrated 2026-06: correct matches land 0.72-0.94)

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
OLLAMA_NUM_CTX    = int(os.getenv("OLLAMA_NUM_CTX",      "8192"))  # 4096 truncates the ~5.2k-tok job_matcher prompt → agents fail; 8192 needed for llama3.1/gemma
OLLAMA_TEMPERATURE= float(os.getenv("OLLAMA_TEMPERATURE", "0.2")) # set 0.0 for greedy/reproducible eval baselines
OLLAMA_TIMEOUT    = float(os.getenv("OLLAMA_TIMEOUT",    "300"))  # per-request HTTP timeout (long-context generation)

# ── RunPod Serverless (optional) ──────────────────────────────────────────────
# Set both to route the agents' Ollama /api/chat calls at a RunPod serverless
# endpoint instead of a local/pod Ollama (base.py wraps the request as
# {"input": <chat payload>} → POST /run → poll /status → unwrap "output").
# Leave RUNPOD_ENDPOINT_ID empty to use the direct OLLAMA_BASE_URL path.
# Inject ESCO occupation-essential skills into the career-strategist prompt.
# OFF by default: a 2026-06 A/B (stay-field Adzuna) showed it HURT grounding
# (3.6%->1.8%) and raised fallback (55%->82%) — ESCO's verbose competence labels
# ("specialist nursing care") don't match crisp posting tokens ("RN"), steering
# the agent toward ungroundable phrasings. Re-enable only with a posting-derived
# vocabulary (e.g. Lightcast) whose labels match real postings.
STRATEGIST_USE_OCCUPATION_SKILLS = os.getenv("STRATEGIST_USE_OCCUPATION_SKILLS", "").lower() in ("1", "true", "yes")

# Occupation-graph levers, split after the 2026-06 2x2 A/B decomposed them:
#  - retrieval expansion (skill-aware query) lifts the job dimension (+0.31 on
#    switching x Adzuna) and embeddings tolerate ESCO's verbose labels — KEEP.
#  - prompt context (essential skills into the strategist) reconfirmed the #1
#    regression: grounding down, fallback up (18%->82%) — leave OFF.
# USE_GRAPH_DATA stays as a convenience that turns on BOTH (back-compat / A/B).
USE_GRAPH_DATA = os.getenv("USE_GRAPH_DATA", "").lower() in ("1", "true", "yes")
GRAPH_RETRIEVAL = USE_GRAPH_DATA or os.getenv("GRAPH_RETRIEVAL", "").lower() in ("1", "true", "yes")
GRAPH_PROMPT_CONTEXT = USE_GRAPH_DATA or os.getenv("GRAPH_PROMPT_CONTEXT", "").lower() in ("1", "true", "yes")

RUNPOD_ENDPOINT_ID   = os.getenv("RUNPOD_ENDPOINT_ID", "")
RUNPOD_API_KEY       = os.getenv("RUNPOD_API_KEY", "")              # account API key (Settings → API Keys)
RUNPOD_POLL_TIMEOUT  = int(os.getenv("RUNPOD_POLL_TIMEOUT",  "600"))  # max seconds to wait for a job
RUNPOD_POLL_INTERVAL = float(os.getenv("RUNPOD_POLL_INTERVAL", "2"))  # seconds between /status polls

# ── Embedding (single backend: sentence-transformers) ─────────────────────────
EMBED_MODEL       = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# ── Live job search (Adzuna — free aggregator API) ────────────────────────────
# Free app_id + app_key from https://developer.adzuna.com (2-min signup).
ADZUNA_APP_ID     = os.getenv("ADZUNA_APP_ID",  "")
ADZUNA_APP_KEY    = os.getenv("ADZUNA_APP_KEY", "")
ADZUNA_COUNTRY    = os.getenv("ADZUNA_COUNTRY", "us")   # us, gb, au, ca, ...
ADZUNA_MAX_DAYS   = int(os.getenv("ADZUNA_MAX_DAYS", "30"))  # freshness filter

# ── Reranker passes (1 = retrieval only; 2 = +role+resume; 3 = +resume recs) ─
RERANK_PASSES = int(os.getenv("RERANK_PASSES", "2"))

# ── Grounding and improvement config knobs ─────────────────────────────────────
GROUNDING_PASS_RATIO = float(os.getenv("GROUNDING_PASS_RATIO", "0.5"))
RETRIEVAL_BOOST = os.getenv("RETRIEVAL_BOOST", "0") == "1"
PROMPT_FEWSHOT  = os.getenv("PROMPT_FEWSHOT",  "0") == "1"

# ── Reranker model ────────────────────────────────────────────────────────────
RERANK_MODEL = os.getenv("RERANK_MODEL", "bge-reranker-v2-m3")

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
