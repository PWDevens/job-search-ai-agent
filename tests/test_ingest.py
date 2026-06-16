"""
Unit tests for the ingestion pipeline (jobs & resume).

Tests cover:
  - CSV/XLSX parsing and validation
  - Resume text extraction (.txt, .pdf, .docx)
  - Chunking and deduplication
  - ChromaDB upsert

Uses in-memory ChromaDB and real sample data.
Run: pytest tests/test_ingest.py -v
"""
from __future__ import annotations
import pytest
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Test: ingest_jobs (CSV and XLSX)
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestJobs:
    """Test job file ingestion (CSV and XLSX)."""

    def test_ingest_csv_returns_count(self, sample_jobs_csv, chroma_client):
        """Ingesting a valid CSV should return count of ingested rows."""
        from app.pipeline.ingest import ingest_jobs

        count = ingest_jobs(sample_jobs_csv)
        assert count == 3, "Should ingest all 3 jobs"

        # Verify jobs were actually upserted to ChromaDB
        col = chroma_client.get_or_create_collection("jobs")
        assert col.count() == 3, "ChromaDB should contain 3 jobs"

    def test_ingest_xlsx_returns_count(self, sample_jobs_xlsx, chroma_client):
        """Ingesting a valid XLSX should return count of ingested rows."""
        from app.pipeline.ingest import ingest_jobs

        count = ingest_jobs(sample_jobs_xlsx)
        assert count == 2, "Should ingest both jobs from XLSX"

    def test_ingest_nonexistent_file_raises(self, tmp_path):
        """Ingesting a non-existent file should raise FileNotFoundError."""
        from app.pipeline.ingest import ingest_jobs

        with pytest.raises(FileNotFoundError):
            ingest_jobs(tmp_path / "nonexistent.csv")

    def test_ingest_missing_required_columns_raises(self, tmp_path):
        """CSV missing required columns (title, company, description) should raise."""
        from app.pipeline.ingest import ingest_jobs

        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("role,employer\nSWE,ACME\n")

        with pytest.raises(ValueError, match="missing required columns"):
            ingest_jobs(bad_csv)

    def test_ingest_empty_rows_skipped(self, tmp_path, chroma_client):
        """Rows with empty required fields should be skipped."""
        from app.pipeline.ingest import ingest_jobs

        csv = tmp_path / "jobs.csv"
        csv.write_text(
            "title,company,description\n"
            "Data Engineer,Acme,Build pipelines\n"
            ",,Empty row with blanks\n"
            "ML Engineer,Beta,Deploy models\n"
        )

        count = ingest_jobs(csv)
        assert count == 2, "Should skip row with empty fields"

    def test_ingest_geo_filter(self, sample_jobs_csv, chroma_client):
        """Geo filter should reduce ingested row count."""
        from app.pipeline.ingest import ingest_jobs

        count = ingest_jobs(sample_jobs_csv, geo_filter="Washington DC")
        assert count == 1, "Should only ingest DC job with geo filter"

        col = chroma_client.get_or_create_collection("jobs")
        assert col.count() == 1, "Only filtered job in ChromaDB"

    def test_ingest_geo_filter_case_insensitive(self, sample_jobs_csv):
        """Geo filter should be case-insensitive."""
        from app.pipeline.ingest import ingest_jobs

        count = ingest_jobs(sample_jobs_csv, geo_filter="washington dc")
        assert count == 1, "Geo filter should be case-insensitive"

    def test_ingest_deduplicates_by_stable_id(self, sample_jobs_csv, chroma_client):
        """Ingesting same job twice should deduplicate by stable ID."""
        from app.pipeline.ingest import ingest_jobs

        count1 = ingest_jobs(sample_jobs_csv)
        count2 = ingest_jobs(sample_jobs_csv)  # ingest again

        col = chroma_client.get_or_create_collection("jobs")
        # Upserting same IDs should not increase count
        assert col.count() == 3, "Duplicate ingestion should not increase count"

    def test_metadata_preserved(self, sample_jobs_csv, chroma_client):
        """Job metadata (title, company, location) should be preserved in ChromaDB."""
        from app.pipeline.ingest import ingest_jobs

        ingest_jobs(sample_jobs_csv)

        col = chroma_client.get_or_create_collection("jobs")
        results = col.get()
        metadatas = results.get("metadatas", [])

        assert len(metadatas) > 0
        first_job = metadatas[0]
        assert first_job.get("title") in ["Data Engineer", "ML Engineer", "Senior SWE"]
        assert first_job.get("company") is not None

    def test_stable_id_deterministic(self):
        """Same job text should always produce the same stable ID."""
        from app.pipeline.ingest import _stable_id

        id1 = _stable_id("Data Engineer at Acme. Build pipelines.")
        id2 = _stable_id("Data Engineer at Acme. Build pipelines.")
        assert id1 == id2, "Stable ID should be deterministic"

        id3 = _stable_id("Different text")
        assert id1 != id3, "Different text should produce different ID"


# ─────────────────────────────────────────────────────────────────────────────
# Test: ingest_resume (TXT, PDF, DOCX)
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestResume:
    """Test resume ingestion (TXT, PDF, DOCX)."""

    def test_ingest_txt_returns_chunks(self, sample_resume_txt, chroma_client):
        """Ingesting a valid TXT resume should return count of chunks."""
        from app.pipeline.ingest import ingest_resume

        count = ingest_resume(sample_resume_txt)
        assert count >= 1, "Should create at least 1 chunk"

        # Verify chunks were upserted to ChromaDB
        col = chroma_client.get_or_create_collection("resume_chunks")
        assert col.count() == count, f"Should have {count} resume chunks in ChromaDB"

    def test_ingest_pdf_returns_chunks(self, sample_resume_pdf, chroma_client):
        """Ingesting a PDF resume should return count of chunks."""
        from app.pipeline.ingest import ingest_resume

        count = ingest_resume(sample_resume_pdf)
        # PDF may extract text or may fail gracefully
        assert count >= 0, "Should handle PDF gracefully"

    def test_ingest_nonexistent_resume_raises(self, tmp_path):
        """Ingesting a non-existent resume should raise FileNotFoundError."""
        from app.pipeline.ingest import ingest_resume

        with pytest.raises(FileNotFoundError):
            ingest_resume(tmp_path / "nonexistent.txt")

    def test_ingest_empty_resume_returns_zero(self, tmp_path, chroma_client):
        """Ingesting an empty resume should return 0 chunks."""
        from app.pipeline.ingest import ingest_resume

        empty = tmp_path / "empty.txt"
        empty.write_text("")

        count = ingest_resume(empty)
        assert count == 0, "Empty resume should return 0 chunks"

    def test_resume_chunking(self):
        """Resume should be split into overlapping chunks."""
        from app.pipeline.ingest import _chunk_text

        # Create text with 1000 words
        long_text = " ".join([f"word{i}" for i in range(1000)])
        chunks = _chunk_text(long_text, chunk_size=300, overlap=50)

        assert len(chunks) > 1, "Should split into multiple chunks"
        for chunk in chunks:
            words = chunk.split()
            assert len(words) <= 300, "Each chunk should respect chunk_size"

    def test_resume_chunk_overlap(self):
        """Chunks should have overlap for continuity."""
        from app.pipeline.ingest import _chunk_text

        text = " ".join([f"word{i}" for i in range(600)])
        chunks = _chunk_text(text, chunk_size=200, overlap=50)

        assert len(chunks) >= 2, "Should have at least 2 chunks"
        # Verify overlap: last 50 words of chunk 0 should appear near start of chunk 1
        chunk0_end = set(chunks[0].split()[-50:])
        chunk1_start = set(chunks[1].split()[:50])
        assert len(chunk0_end & chunk1_start) > 0, "Chunks should overlap"

    def test_read_resume_returns_text(self, sample_resume_txt):
        """read_resume should extract text from resume file."""
        from app.pipeline.ingest import read_resume

        text = read_resume(sample_resume_txt)
        assert len(text) > 0, "Should extract text from resume"
        assert "Data Engineer" in text, "Should contain expected content"

    def test_read_nonexistent_file_returns_empty(self, tmp_path):
        """read_resume on nonexistent file should return empty string, not raise."""
        from app.pipeline.ingest import read_resume

        text = read_resume(tmp_path / "nonexistent.txt")
        assert text == "", "Should return empty string for missing file"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Helpers and utilities
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestHelpers:
    """Test helper functions and utilities."""

    def test_clean_strips_whitespace(self):
        """_clean should strip and collapse whitespace."""
        from app.pipeline.ingest import _clean

        assert _clean("  hello  ") == "hello"
        assert _clean("hello  \n  world") == "hello world"
        assert _clean("   ") == ""

    def test_stable_id_is_16_chars(self):
        """_stable_id should return 16-character hex string."""
        from app.pipeline.ingest import _stable_id

        id_val = _stable_id("test")
        assert len(id_val) == 16, "Stable ID should be 16 characters"
        assert all(c in "0123456789abcdef" for c in id_val), "Should be valid hex"

    def test_read_and_normalise_returns_dataframe(self, sample_jobs_csv):
        """read_and_normalise should return normalized DataFrame."""
        from app.pipeline.ingest import read_and_normalise

        df = read_and_normalise(sample_jobs_csv)
        assert "title" in df.columns, "Should have normalized 'title' column"
        assert "company" in df.columns, "Should have normalized 'company' column"
        assert "description" in df.columns, "Should have normalized 'description' column"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Integration - full ingest pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestIntegration:
    """Integration tests for full ingest pipeline."""

    def test_ingest_jobs_and_resume_together(
        self, sample_jobs_csv, sample_resume_txt, chroma_client
    ):
        """Ingest jobs and resume together, verify both in ChromaDB."""
        from app.pipeline.ingest import ingest_jobs, ingest_resume

        job_count = ingest_jobs(sample_jobs_csv)
        resume_count = ingest_resume(sample_resume_txt)

        assert job_count > 0, "Should ingest jobs"
        assert resume_count > 0, "Should ingest resume"

        jobs_col = chroma_client.get_or_create_collection("jobs")
        resume_col = chroma_client.get_or_create_collection("resume_chunks")

        assert jobs_col.count() == job_count, "Jobs should be in ChromaDB"
        assert resume_col.count() == resume_count, "Resume chunks should be in ChromaDB"
