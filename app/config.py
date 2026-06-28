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
# (ESCO skills-taxonomy config retired iter11 — superseded by O*NET, see app/skills/onet_requirements.py)

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
# ESCO occupation-graph levers RETIRED (iter11): the 3-arm A/B (esco_ret/esco_full vs O*NET-only)
# showed only +0.026-0.028 mean overall — within the GPU-noise floor, concentrated in one synthetic
# cell, 0.000 on realistic Adzuna. ESCO's verbose competence labels never matched posting tokens.
# Superseded by the O*NET authoritative-requirements layer (AUTHORITATIVE_GAPS). See IMPROVEMENT_LOG.

# AUTHORITATIVE_GAPS (iter5): ground career-strategist blind spots + resume-coach recs in the TARGET
# OCCUPATION's real O*NET requirements (matched from the matched jobs' titles, app/skills/onet_requirements.py)
# instead of skills that survived a 500-char truncated posting. DEFAULT ON (iter7): off->on +0.414 mean,
# positive in all 4 cells, switcher gap closed. No-op when the O*NET DB is absent. Disable with =0.
AUTHORITATIVE_GAPS = os.getenv("AUTHORITATIVE_GAPS", "1").lower() in ("1", "true", "yes")

# RUBRIC_V2 (iter6 R1 + iter7 B5): JTBD-aligned scoring. A blind spot counts as grounded if its skill
# is in a retrieved posting OR a real target-occupation requirement (O*NET); a resume rec scores as
# gap-closing if it adds a real occupation requirement. v1 (posting/tech-keyword only) measured
# truncation/tech-bias as much as advice quality. DEFAULT ON (iter7) — the canonical rubric; the
# `rubric_version` column self-identifies runs (set =0 to reproduce a pre-v2 baseline).
RUBRIC_V2 = os.getenv("RUBRIC_V2", "1").lower() in ("1", "true", "yes")

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

# ── Effort dial — a UX axis (breadth/options), NOT an accuracy axis (iter11 A/B: compute != accuracy).
# Usage-persona -> effort + delivery mapping (#4):
#   passive looker        -> quick    (sync web; just show me what's out there)
#   daily user            -> balanced (sync web; default)
#   burnt-out / thorough  -> max      (async; widest search, most options to browse)
#   time-oriented email   -> max      (scheduler; latency-insensitive, see SCHEDULER_EFFORT)
EFFORT = os.getenv("EFFORT", "balanced").lower()
# best_of dropped from thorough/max (iter11 A/B): best-of-N selected on company-citation grounding
# ratio — the WRONG objective for coach/strategist — and net-HURT accuracy (stay_adz spot 1.89->1.67).
# Effort is now deterministic breadth + rerank (the safe levers). best-of-N capability is kept in
# _run_with_grounding for a re-aimed retry (select by auth%/gap-closing). UX value = options surfaced.
EFFORT_BUNDLES = {
    "quick":    {"rerank_passes": 1, "fetch": 40,  "top_jobs": 5,  "best_of": 1, "temp": 0.0},
    "balanced": {"rerank_passes": 2, "fetch": 50,  "top_jobs": 8,  "best_of": 1, "temp": 0.0},
    "thorough": {"rerank_passes": 3, "fetch": 100, "top_jobs": 10, "best_of": 1, "temp": 0.0},
    "max":      {"rerank_passes": 3, "fetch": 150, "top_jobs": 12, "best_of": 1, "temp": 0.0},
}


def effort_bundle(name: str | None = None) -> dict:
    """Return the compute bundle for an effort level (default 'balanced')."""
    return EFFORT_BUNDLES.get((name or EFFORT or "balanced").lower(), EFFORT_BUNDLES["balanced"])

# ── Grounding and improvement config knobs ─────────────────────────────────────
GROUNDING_PASS_RATIO = float(os.getenv("GROUNDING_PASS_RATIO", "0.5"))
RETRIEVAL_BOOST = os.getenv("RETRIEVAL_BOOST", "0") == "1"
PROMPT_FEWSHOT  = os.getenv("PROMPT_FEWSHOT",  "0") == "1"  # opt-in: +0.061 paired (iter3) but within GPU-fleet noise (iter4); field-diverse examples kept

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
