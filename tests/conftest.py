"""
Shared pytest configuration and fixtures.
Sets environment variables so tests run without any live services.
"""
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Lightweight test environment ──────────────────────────────────────────────
os.environ.setdefault("LLM_BACKEND",    "mock")
os.environ.setdefault("EMBED_BACKEND",  "sentence_transformers")
os.environ.setdefault("CHROMA_HOST",    "localhost")
os.environ.setdefault("CHROMA_PORT",    "8000")
os.environ.setdefault("OLLAMA_BASE_URL","http://localhost:11434")
os.environ.setdefault("SMTP_USER",      "")   # disable email in tests
os.environ.setdefault("SMTP_PASS",      "")
os.environ.setdefault("PIPELINE_XLSX",  "/tmp/test_pipeline.xlsx")
os.environ.setdefault("SECRET_KEY",     "test-secret-key")
os.environ.setdefault("UPLOAD_FOLDER",  "/tmp/test_uploads")
