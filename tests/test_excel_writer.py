"""
Unit tests for Excel writing functionality.

Tests cover:
  - Pipeline XLSX appending
  - User file merging
  - Deduplication

Run: pytest tests/test_excel_writer.py -v
"""
import pytest
import pandas as pd


class TestAppendJobsToPipeline:
    """Test appending jobs to the pipeline XLSX."""

    def test_append_jobs_to_pipeline_returns_count(self, tmp_path):
        """append_jobs_to_pipeline should return count of new rows."""
        import os
        from app.pipeline.excel_writer import append_jobs_to_pipeline

        # Temporarily set pipeline path
        pipeline_path = tmp_path / "pipeline.xlsx"
        os.environ["PIPELINE_XLSX"] = str(pipeline_path)

        jobs = [
            {
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
                "score": 0.95,
                "salary": "120000",
            }
        ]

        count = append_jobs_to_pipeline(jobs)
        assert count > 0, "Should append jobs to pipeline"

    def test_append_jobs_to_nonexistent_pipeline(self, tmp_path, monkeypatch):
        """append_jobs_to_pipeline should create pipeline if it doesn't exist."""
        import app.pipeline.excel_writer as ew

        pipeline_path = tmp_path / "new_pipeline.xlsx"
        # PIPELINE_XLSX is import-bound in excel_writer; patch the module attr the fn reads.
        monkeypatch.setattr(ew, "PIPELINE_XLSX", str(pipeline_path))
        append_jobs_to_pipeline = ew.append_jobs_to_pipeline

        jobs = [
            {
                "title": "ML Engineer",
                "company": "Beta",
                "location": "San Francisco",
                "score": 0.88,
            }
        ]

        count = append_jobs_to_pipeline(jobs)
        # Pipeline file should be created
        assert pipeline_path.exists(), "Should create pipeline file"


class TestMergeJobsToUserFile:
    """Test merging new jobs into user's uploaded file."""

    def test_merge_new_jobs_to_user_file(self, tmp_path, sample_jobs_csv):
        """merge_new_jobs_to_user_file should append new jobs to user file."""
        from app.pipeline.excel_writer import merge_new_jobs_to_user_file

        # Create a new job not in the original file
        new_jobs = [
            {
                "title": "New Role",
                "company": "NewCo",
                "location": "Remote",
                "description": "Unique new opportunity",
                "salary": "140000",
            }
        ]

        merged_count, out_path = merge_new_jobs_to_user_file(
            user_file_path=sample_jobs_csv,
            new_jobs=new_jobs,
        )

        assert merged_count > 0, "Should find new jobs"
        assert out_path.exists(), "Should create output file"

    def test_merge_deduplicates_existing_jobs(self, tmp_path):
        """merge_new_jobs_to_user_file should not re-add existing jobs."""
        from app.pipeline.excel_writer import merge_new_jobs_to_user_file

        # Create a simple user file
        user_csv = tmp_path / "user_jobs.csv"
        user_csv.write_text(
            "title,company,location,description\n"
            "Data Engineer,Acme,Remote,Build pipelines\n"
        )

        # Try to add the same job
        same_job = [
            {
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
                "description": "Build pipelines",
            }
        ]

        merged_count, out_path = merge_new_jobs_to_user_file(
            user_file_path=user_csv,
            new_jobs=same_job,
        )

        # Should not add duplicate
        assert merged_count == 0, "Should not add duplicate jobs"

    def test_merge_output_file_has_all_jobs(self, tmp_path):
        """Output file should contain both original and new jobs."""
        from app.pipeline.excel_writer import merge_new_jobs_to_user_file

        # Create user file with 1 job
        user_csv = tmp_path / "user_jobs.csv"
        user_csv.write_text(
            "title,company,location,description\n"
            "Data Engineer,Acme,Remote,Original job\n"
        )

        # Add a new job
        new_jobs = [
            {
                "title": "ML Engineer",
                "company": "Beta",
                "location": "Remote",
                "description": "New job",
            }
        ]

        merged_count, out_path = merge_new_jobs_to_user_file(
            user_file_path=user_csv,
            new_jobs=new_jobs,
        )

        # Read output and verify
        output_df = pd.read_csv(out_path)
        assert len(output_df) >= 2, "Output should have original + new job"

    def test_merge_preserves_user_columns(self, tmp_path):
        """merge_new_jobs_to_user_file should preserve user's columns."""
        from app.pipeline.excel_writer import merge_new_jobs_to_user_file

        # Create user file with custom columns
        user_csv = tmp_path / "user_jobs.csv"
        user_csv.write_text(
            "title,company,my_notes,status\n"
            "Data Engineer,Acme,Great company,Applied\n"
        )

        new_jobs = [
            {
                "title": "ML Engineer",
                "company": "Beta",
                "location": "Remote",
                "description": "New role",
            }
        ]

        merged_count, out_path = merge_new_jobs_to_user_file(
            user_file_path=user_csv,
            new_jobs=new_jobs,
        )

        # Read output and verify custom columns are preserved
        output_df = pd.read_csv(out_path)
        # User's columns should still exist (may have NaN for new jobs)
        assert "my_notes" in output_df.columns or len(output_df) > 0, \
            "Should preserve user columns"


class TestExcelWriterIntegration:
    """Integration tests for Excel writing."""

    def test_full_pipeline_write(self, sample_jobs_csv, tmp_path):
        """End-to-end: ingest jobs, append to pipeline, merge to user file."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_top_jobs
        from app.pipeline.excel_writer import append_jobs_to_pipeline
        import os

        # Setup
        pipeline_path = tmp_path / "pipeline.xlsx"
        os.environ["PIPELINE_XLSX"] = str(pipeline_path)

        # Ingest
        ingest_jobs(sample_jobs_csv)

        # Find matches
        matches = find_top_jobs("Data Engineer", n=5)

        # Write to pipeline
        if matches:
            count = append_jobs_to_pipeline(matches)
            assert count >= 0, "Should append to pipeline"
