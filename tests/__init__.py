"""
tests/__init__.py — Test Package Marker
========================================

WHY THIS FILE EXISTS:
---------------------
Makes the `tests/` folder a Python package so pytest can discover test
files reliably across different operating systems and Python versions.

For modern pytest (≥ 7) this file is optional, but including it is a
best practice because it prevents namespace collision if you ever have
two test files with the same name in different directories.

HOW PYTEST DISCOVERS TESTS (without a framework like unittest):
  1. pytest scans for files named test_*.py or *_test.py
  2. Inside those files it finds functions named test_* and classes
     named Test* containing methods named test_*
  3. It runs each one and reports pass / fail

RUNNING THE TEST SUITE:
  # All tests (no live services required — everything is mocked)
  LLM_BACKEND=mock EMBED_BACKEND=sentence_transformers pytest tests/ -v

  # Single file
  pytest tests/test_ingest.py -v

  # With coverage report
  pytest tests/ --cov=app --cov-report=term-missing

WHAT EACH TEST FILE COVERS:
  conftest.py        → Shared fixtures + env var setup (runs before every test)
  test_ingest.py     → CSV/XLSX loading, chunking, geo filtering, error handling
  test_matcher.py    → Cosine similarity ranking, blind-spot extraction, edge cases
  test_email.py      → HTML email construction, SMTP mock, SMTP-disabled fallback

NO LIVE SERVICES NEEDED:
  ChromaDB, Ollama, and SMTP are all mocked in tests. You can run the
  full suite on a machine with no Docker installed.
"""
