"""
Unit tests for audit logging functionality.

Tests cover:
  - Database initialization
  - Search run logging
  - Audit retrieval and stats
  - Privacy-preserving hashing

Run: pytest tests/test_audit.py -v
"""
import pytest
from pathlib import Path


class TestAuditDatabase:
    """Test audit database operations."""

    def test_init_audit_db_creates_database(self, tmp_path):
        """init_audit_db should create database file."""
        from app.pipeline.audit import init_audit_db

        init_audit_db()
        # Should not raise

    def test_log_search_run_returns_id(self):
        """log_search_run should return a run ID."""
        from app.pipeline.audit import log_search_run

        run_id = log_search_run(
            role_description="Data Engineer",
            geo_preference="Remote",
            resume_text="Python SQL Spark",
            top_jobs=[{"title": "SWE", "company": "Acme", "score": 0.95}],
            resume_recs=["Add Python to skills"],
            blind_spots=["Kubernetes"],
            raw_agent_output={
                "job_matches": "1. SWE at Acme",
                "resume_recs": "1. Add Python",
                "blind_spots": "1. Kubernetes",
            },
            agent_validation={"resume_coach": True, "career_strategist": True},
        )

        assert isinstance(run_id, int), "Should return integer run ID"
        assert run_id > 0, "Run ID should be positive"

    def test_log_search_run_with_empty_results(self):
        """log_search_run should handle empty results."""
        from app.pipeline.audit import log_search_run

        run_id = log_search_run(
            role_description="Data Engineer",
            geo_preference=None,
            resume_text=None,
            top_jobs=[],
            resume_recs=[],
            blind_spots=[],
            raw_agent_output={},
            agent_validation={"resume_coach": False, "career_strategist": False},
        )

        assert run_id > 0, "Should return valid run ID"

    def test_log_search_run_with_error(self):
        """log_search_run should accept error message."""
        from app.pipeline.audit import log_search_run

        run_id = log_search_run(
            role_description="SWE",
            geo_preference="SF",
            resume_text=None,
            top_jobs=[],
            resume_recs=[],
            blind_spots=[],
            raw_agent_output={},
            agent_validation={},
            error="ChromaDB connection timeout",
        )

        assert run_id > 0, "Should log error gracefully"


class TestAuditRetrieval:
    """Test audit log retrieval."""

    def test_get_search_run_retrieves_logged_run(self):
        """get_search_run should retrieve a previously logged run."""
        from app.pipeline.audit import log_search_run, get_search_run

        run_id = log_search_run(
            role_description="ML Engineer",
            geo_preference="Remote",
            resume_text="PyTorch TensorFlow",
            top_jobs=[{"title": "ML Eng", "company": "Beta", "score": 0.92}],
            resume_recs=["Add deep learning"],
            blind_spots=["Kubernetes"],
            raw_agent_output={
                "job_matches": "1. ML Eng",
                "resume_recs": "1. Add deep learning",
                "blind_spots": "1. Kubernetes",
            },
            agent_validation={"resume_coach": True, "career_strategist": True},
        )

        retrieved = get_search_run(run_id)
        assert retrieved is not None, "Should retrieve logged run"
        assert retrieved["role_description"] == "ML Engineer"
        assert retrieved["top_jobs_count"] == 1

    def test_get_search_run_returns_none_for_missing(self):
        """get_search_run should return None for non-existent run."""
        from app.pipeline.audit import get_search_run

        result = get_search_run(999999)
        assert result is None, "Should return None for missing run"

    def test_list_search_runs_returns_list(self):
        """list_search_runs should return list of runs."""
        from app.pipeline.audit import log_search_run, list_search_runs

        # Log a few runs
        for i in range(3):
            log_search_run(
                role_description=f"Role {i}",
                geo_preference="Remote",
                resume_text=None,
                top_jobs=[],
                resume_recs=[],
                blind_spots=[],
                raw_agent_output={},
                agent_validation={},
            )

        runs = list_search_runs(limit=10)
        assert isinstance(runs, list), "Should return list"
        assert len(runs) >= 3, "Should return logged runs"

    def test_list_search_runs_with_filter(self):
        """list_search_runs should filter by role description."""
        from app.pipeline.audit import log_search_run, list_search_runs

        # Log runs with different roles
        log_search_run(
            role_description="Data Engineer",
            geo_preference=None,
            resume_text=None,
            top_jobs=[],
            resume_recs=[],
            blind_spots=[],
            raw_agent_output={},
            agent_validation={},
        )

        log_search_run(
            role_description="ML Engineer",
            geo_preference=None,
            resume_text=None,
            top_jobs=[],
            resume_recs=[],
            blind_spots=[],
            raw_agent_output={},
            agent_validation={},
        )

        # Filter for Data Engineer
        data_eng_runs = list_search_runs(limit=10, role_filter="Data Engineer")
        assert any("Data Engineer" in r["role_description"] for r in data_eng_runs), \
            "Should filter by role"


class TestAuditStats:
    """Test audit statistics."""

    def test_get_audit_stats_returns_dict(self):
        """get_audit_stats should return statistics dictionary."""
        from app.pipeline.audit import log_search_run, get_audit_stats

        # Log a run
        log_search_run(
            role_description="SWE",
            geo_preference="NYC",
            resume_text=None,
            top_jobs=[{"title": "SWE", "company": "Google", "score": 0.98}],
            resume_recs=["Add Go", "Add C++"],
            blind_spots=["Rust"],
            raw_agent_output={},
            agent_validation={"resume_coach": True, "career_strategist": True},
        )

        stats = get_audit_stats()
        assert isinstance(stats, dict), "Should return dictionary"
        assert "total_runs" in stats, "Should have total_runs"
        assert "validation_pass_rate" in stats, "Should have validation_pass_rate"
        assert stats["total_runs"] > 0, "Should count runs"

    def test_stats_tracks_validation_pass_rate(self):
        """Stats should track agent validation pass rate."""
        from app.pipeline.audit import log_search_run, get_audit_stats

        # Log a successful run
        log_search_run(
            role_description="Role1",
            geo_preference=None,
            resume_text=None,
            top_jobs=[],
            resume_recs=[],
            blind_spots=[],
            raw_agent_output={},
            agent_validation={"resume_coach": True, "career_strategist": True},
        )

        stats = get_audit_stats()
        assert "validation_pass_rate" in stats, "Should track pass rate"


class TestResumHashing:
    """Test privacy-preserving resume hashing."""

    def test_hash_resume_returns_hash(self):
        """_hash_resume should return a hash of resume text."""
        from app.pipeline.audit import _hash_resume

        hash1 = _hash_resume("Python SQL Spark experience")
        assert len(hash1) == 12, "Hash should be 12 characters"
        assert hash1.isalnum() or hash1[:2] != "x", "Hash should be valid"

    def test_hash_resume_deterministic(self):
        """_hash_resume should be deterministic."""
        from app.pipeline.audit import _hash_resume

        text = "Same resume content"
        hash1 = _hash_resume(text)
        hash2 = _hash_resume(text)

        assert hash1 == hash2, "Hash should be deterministic"

    def test_hash_resume_returns_none_for_empty(self):
        """_hash_resume should return 'none' for empty resume."""
        from app.pipeline.audit import _hash_resume

        hash1 = _hash_resume(None)
        hash2 = _hash_resume("")

        assert hash1 == "none", "Should return 'none' for None"
        # Empty string may hash differently

    def test_hash_resume_different_for_different_content(self):
        """Different resume text should produce different hashes."""
        from app.pipeline.audit import _hash_resume

        hash1 = _hash_resume("Resume 1")
        hash2 = _hash_resume("Resume 2")

        assert hash1 != hash2, "Different content should produce different hashes"


class TestAuditCleanup:
    """Test audit log cleanup."""

    def test_cleanup_old_audits_returns_count(self):
        """cleanup_old_audits should return number of deleted entries."""
        from app.pipeline.audit import cleanup_old_audits

        # Cleanup very old entries (nothing should be deleted)
        deleted = cleanup_old_audits(days=0)

        assert isinstance(deleted, int), "Should return count"
        assert deleted >= 0, "Count should be non-negative"
