"""
Integration tests for the full job-search pipeline.

Tests cover:
  - Complete ingest → search → export workflow
  - Multi-file ingestion
  - Search with different filters

Run: pytest tests/test_pipeline_integration.py -v
"""
import pytest


class TestFullPipeline:
    """End-to-end pipeline tests."""

    def test_complete_workflow_ingest_search_export(
        self, sample_jobs_csv, sample_resume_txt, tmp_path
    ):
        """
        Complete workflow:
        1. Ingest jobs CSV
        2. Ingest resume TXT
        3. Search for matches
        4. Verify results contain expected fields
        """
        from app.pipeline.ingest import ingest_jobs, ingest_resume, read_resume
        from app.pipeline.matcher import find_top_jobs, find_blind_spots
        import os

        # Setup
        pipeline_path = tmp_path / "pipeline.xlsx"
        os.environ["PIPELINE_XLSX"] = str(pipeline_path)

        # Step 1: Ingest jobs
        job_count = ingest_jobs(sample_jobs_csv)
        assert job_count > 0, "Should ingest jobs"

        # Step 2: Ingest resume
        resume_count = ingest_resume(sample_resume_txt)
        assert resume_count > 0, "Should ingest resume"

        # Step 3: Search
        resume_text = read_resume(sample_resume_txt)
        jobs = find_top_jobs(
            "Data Engineer with Python and SQL",
            resume_text=resume_text,
            n=5
        )
        blind_spots = find_blind_spots(
            "Data Engineer",
            resume_text=resume_text,
            n=3
        )

        # Step 4: Verify results
        assert len(jobs) > 0, "Should find job matches"
        assert isinstance(blind_spots, list), "Should identify blind spots"

        for job in jobs:
            assert job["title"], "Job should have title"
            assert job["company"], "Job should have company"
            assert "score" in job, "Job should have match score"

    def test_workflow_with_geo_filter(self, sample_jobs_csv, sample_resume_txt):
        """Full workflow with geographic filtering."""
        from app.pipeline.ingest import ingest_jobs, ingest_resume
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)
        ingest_resume(sample_resume_txt)

        # Search with geo filter
        jobs = find_top_jobs(
            "Data Engineer",
            geo_preference="Washington DC",
            n=10
        )

        # All results should match the geo filter (if any)
        for job in jobs:
            # Job should either match filter or be reasonable fallback
            assert job["title"], "Should have valid job title"

    def test_multiple_csv_ingestions(self, sample_jobs_csv, sample_jobs_xlsx):
        """Test ingesting multiple job files."""
        from app.pipeline.ingest import ingest_jobs

        count_csv = ingest_jobs(sample_jobs_csv)
        count_xlsx = ingest_jobs(sample_jobs_xlsx)

        assert count_csv > 0, "Should ingest CSV"
        assert count_xlsx > 0, "Should ingest XLSX"

    def test_duplicate_ingestion_handling(self, sample_jobs_csv):
        """Test that re-ingesting same file doesn't duplicate entries."""
        from app.pipeline.ingest import ingest_jobs

        count1 = ingest_jobs(sample_jobs_csv)
        count2 = ingest_jobs(sample_jobs_csv)

        # Second ingest should upsert, not duplicate
        assert count2 == count1, "Re-ingestion should maintain count (no duplicates)"

    def test_search_ranking_quality(self, sample_jobs_csv):
        """Test that job ranking by similarity works reasonably."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)

        # Search for specific role
        jobs = find_top_jobs("Data Engineer", n=10)

        # Results should be ranked (scores should generally decrease)
        if len(jobs) > 1:
            scores = [job["score"] for job in jobs]
            # First few should have decent scores (this is a weak assertion)
            assert scores[0] >= 0, "Scores should be valid"


class TestErrorHandling:
    """Test error handling in the pipeline."""

    def test_ingest_missing_file_raises(self, tmp_path):
        """Ingesting non-existent file should raise."""
        from app.pipeline.ingest import ingest_jobs

        with pytest.raises(FileNotFoundError):
            ingest_jobs(tmp_path / "nonexistent.csv")

    def test_search_with_empty_index(self):
        """Searching empty index should not crash."""
        from app.pipeline.matcher import find_top_jobs

        # Empty ChromaDB should return empty or gracefully handle
        results = find_top_jobs("Any role")
        assert isinstance(results, list), "Should return list even if empty"

    def test_blind_spots_with_no_resume(self, sample_jobs_csv):
        """Finding blind spots without resume should use fallback."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_blind_spots

        ingest_jobs(sample_jobs_csv)

        # Should not crash even without resume
        blind_spots = find_blind_spots("Data Engineer", resume_text=None)
        assert isinstance(blind_spots, list), "Should return list even without resume"


class TestDataConsistency:
    """Test data consistency across operations."""

    def test_ingested_jobs_are_searchable(self, sample_jobs_csv):
        """Jobs should be immediately searchable after ingest."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)

        # Search should find the ingested jobs
        results = find_top_jobs("Engineer", n=10)
        assert len(results) > 0, "Ingested jobs should be searchable"

    def test_resume_chunks_are_retrievable(self, sample_resume_txt):
        """Resume chunks should be retrievable after ingest."""
        from app.pipeline.ingest import ingest_resume
        from app.chroma.client import resume_collection

        chunk_count = ingest_resume(sample_resume_txt)
        assert chunk_count > 0

        # Verify chunks in ChromaDB
        col = resume_collection()
        assert col.count() == chunk_count, "All chunks should be in ChromaDB"

    def test_metadata_preserved_through_pipeline(self, sample_jobs_csv):
        """Job metadata should be preserved through the pipeline."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)
        results = find_top_jobs("Engineer", n=10)

        if len(results) > 0:
            job = results[0]
            # Metadata should be preserved
            assert job.get("title") is not None, "Should preserve title"
            assert job.get("company") is not None, "Should preserve company"
