"""
Unit tests for the ingestion pipeline.
These tests use a local ChromaDB in-memory instance and mock Ollama — no services required.
Run with:  LLM_BACKEND=mock pytest tests/ -v
"""
from __future__ import annotations
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── ensure repo root is importable ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("LLM_BACKEND", "mock")
os.environ.setdefault("EMBED_BACKEND", "sentence_transformers")
os.environ.setdefault("CHROMA_HOST", "localhost")

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_jobs_csv(tmp_path: Path) -> Path:
    """Create a minimal valid jobs CSV file."""
    csv = tmp_path / "jobs.csv"
    csv.write_text(
        "title,company,location,description,salary,url,date_posted\n"
        "Data Engineer,Acme Corp,Washington DC,"
        "Build pipelines with Python SQL and Spark,120000,https://acme.com/job1,2026-05-01\n"
        "ML Engineer,Beta Inc,Remote,"
        "Deploy LLMs with PyTorch and Kubernetes,150000,https://beta.com/job2,2026-05-02\n"
    )
    return csv


@pytest.fixture()
def sample_resume_txt(tmp_path: Path) -> Path:
    """Create a minimal valid resume text file."""
    txt = tmp_path / "resume.txt"
    txt.write_text(
        textwrap.dedent("""\
            Jane Doe
            Data Engineer with 5 years of Python SQL Spark experience.
            Skills: Python, SQL, Apache Spark, AWS, Docker.
            Experience: Built ETL pipelines at FakeCoorp (2021-2026).
            Education: B.S. Computer Science.
        """)
    )
    return txt


# ── Tests: ingest_jobs ────────────────────────────────────────────────────────

class TestIngestJobs:
    def test_ingest_csv_returns_count(self, sample_jobs_csv, tmp_path):
        """Ingesting a valid CSV should return the number of rows."""
        with patch("app.chroma.client.get_client") as mock_client:
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            mock_client.return_value.get_or_create_collection.return_value = mock_col

            from app.pipeline.ingest import ingest_jobs
            count = ingest_jobs(sample_jobs_csv)

        assert count == 2

    def test_ingest_missing_file_raises(self, tmp_path):
        """Ingesting a non-existent file should raise FileNotFoundError."""
        from app.pipeline.ingest import ingest_jobs
        with pytest.raises(FileNotFoundError):
            ingest_jobs(tmp_path / "nonexistent.csv")

    def test_ingest_geo_filter(self, sample_jobs_csv):
        """Geo filter should reduce row count."""
        with patch("app.chroma.client.get_client") as mock_client:
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            mock_client.return_value.get_or_create_collection.return_value = mock_col

            from app.pipeline.ingest import ingest_jobs
            count = ingest_jobs(sample_jobs_csv, geo_filter="Washington DC")

        assert count == 1  # only the DC row

    def test_ingest_missing_required_col_raises(self, tmp_path):
        """CSV missing required columns should raise ValueError."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("role,employer\nSWE,ACME\n")

        from app.pipeline.ingest import ingest_jobs
        with pytest.raises(ValueError, match="missing required columns"):
            ingest_jobs(bad_csv)

    def test_stable_id_is_deterministic(self):
        """Same text should always produce the same ID."""
        from app.pipeline.ingest import _stable_id
        assert _stable_id("hello") == _stable_id("hello")
        assert _stable_id("hello") != _stable_id("world")


# ── Tests: ingest_resume ──────────────────────────────────────────────────────

class TestIngestResume:
    def test_ingest_txt_returns_chunks(self, sample_resume_txt):
        """Ingesting a valid TXT resume should return > 0 chunks."""
        with patch("app.chroma.client.get_client") as mock_client:
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            mock_client.return_value.get_or_create_collection.return_value = mock_col

            from app.pipeline.ingest import ingest_resume
            count = ingest_resume(sample_resume_txt)

        assert count >= 1

    def test_ingest_empty_resume_raises(self, tmp_path):
        """Ingesting an empty file should raise ValueError."""
        empty = tmp_path / "empty.txt"
        empty.write_text("")

        from app.pipeline.ingest import ingest_resume
        with pytest.raises(ValueError, match="empty"):
            ingest_resume(empty)

    def test_chunk_text_word_count(self):
        """Chunks should not exceed chunk_size + overlap words."""
        from app.pipeline.ingest import _chunk_text
        long_text = " ".join([f"word{i}" for i in range(1000)])
        chunks = _chunk_text(long_text, chunk_size=300, overlap=50)
        for chunk in chunks:
            assert len(chunk.split()) <= 300
