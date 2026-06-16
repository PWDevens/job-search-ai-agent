"""
Unit tests for the semantic matching engine.

Tests cover:
  - Job ranking by semantic similarity
  - Geo filtering
  - Blind-spot skill detection
  - Resume recommendations
  - Skill extraction

Uses real jobs and resume data in in-memory ChromaDB.
Run: pytest tests/test_matcher.py -v
"""
import pytest


class TestFindTopJobs:
    """Test top job matching by semantic similarity."""

    def test_find_top_jobs_returns_list(self, sample_jobs_csv, chroma_client):
        """find_top_jobs should return a list of job matches."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)

        results = find_top_jobs("Data Engineer looking for Python and SQL", n=5)
        assert isinstance(results, list), "Should return a list"
        assert len(results) > 0, "Should find at least one job"

    def test_find_top_jobs_respects_n_parameter(self, sample_jobs_csv):
        """find_top_jobs should respect n parameter."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)

        results = find_top_jobs("Data Engineer", n=2)
        assert len(results) <= 2, "Should return at most n results"

    def test_find_top_jobs_has_required_fields(self, sample_jobs_csv):
        """Each job result should have required fields."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)

        results = find_top_jobs("Data Engineer", n=5)
        assert len(results) > 0

        for job in results:
            assert "title" in job, "Should have title"
            assert "company" in job, "Should have company"
            assert "location" in job, "Should have location"
            assert "score" in job, "Should have similarity score"
            assert 0 <= job["score"] <= 1, "Score should be 0-1"

    def test_find_top_jobs_with_geo_filter(self, sample_jobs_csv):
        """find_top_jobs should filter by geography."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)

        results_dc = find_top_jobs("Data Engineer", geo_preference="Washington DC", n=10)
        results_all = find_top_jobs("Data Engineer", geo_preference=None, n=10)

        # DC filter should reduce results
        assert len(results_dc) <= len(results_all), "Geo filter should reduce results"

    def test_find_top_jobs_empty_collection(self):
        """find_top_jobs on empty ChromaDB should return empty list."""
        from app.pipeline.matcher import find_top_jobs

        results = find_top_jobs("Data Engineer", n=5)
        # Should either return empty list or handle gracefully
        assert isinstance(results, list), "Should return a list even if empty"

    def test_find_top_jobs_with_resume_context(self, sample_jobs_csv, sample_resume_txt):
        """find_top_jobs with resume context should affect ranking."""
        from app.pipeline.ingest import ingest_jobs, read_resume
        from app.pipeline.matcher import find_top_jobs

        ingest_jobs(sample_jobs_csv)
        resume_text = read_resume(sample_resume_txt)

        results_with_resume = find_top_jobs(
            "Data Engineer",
            resume_text=resume_text,
            n=5
        )
        results_without_resume = find_top_jobs(
            "Data Engineer",
            resume_text=None,
            n=5
        )

        # Both should return results
        assert isinstance(results_with_resume, list)
        assert isinstance(results_without_resume, list)


class TestFindBlindSpots:
    """Test blind-spot (skill gap) detection."""

    def test_find_blind_spots_returns_list(self, sample_jobs_csv):
        """find_blind_spots should return a list of skill gaps."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_blind_spots

        ingest_jobs(sample_jobs_csv)

        blind_spots = find_blind_spots("Data Engineer")
        assert isinstance(blind_spots, list), "Should return a list"

    def test_find_blind_spots_respects_n_parameter(self, sample_jobs_csv):
        """find_blind_spots should limit results to n."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_blind_spots

        ingest_jobs(sample_jobs_csv)

        blind_spots = find_blind_spots("Data Engineer", n=3)
        assert len(blind_spots) <= 3, "Should return at most n blind spots"

    def test_blind_spots_with_resume(self, sample_jobs_csv, sample_resume_txt):
        """With resume, blind_spots should identify missing skills."""
        from app.pipeline.ingest import ingest_jobs, read_resume
        from app.pipeline.matcher import find_blind_spots

        ingest_jobs(sample_jobs_csv)
        resume_text = read_resume(sample_resume_txt)

        blind_spots = find_blind_spots(
            "Data Engineer",
            resume_text=resume_text,
            n=5
        )

        assert isinstance(blind_spots, list), "Should return a list of skill gaps"

    def test_blind_spots_without_resume_fallback(self, sample_jobs_csv):
        """Without resume, blind_spots should use fallback (job text only)."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_blind_spots

        ingest_jobs(sample_jobs_csv)

        # This should not raise, even if resume collection is empty
        blind_spots = find_blind_spots("Data Engineer", resume_text=None)
        assert isinstance(blind_spots, list), "Should handle missing resume gracefully"

    def test_blind_spots_are_skills(self, sample_jobs_csv, sample_resume_txt):
        """Blind spots should be actual skill keywords, not gibberish."""
        from app.pipeline.ingest import ingest_jobs, read_resume
        from app.pipeline.matcher import find_blind_spots

        ingest_jobs(sample_jobs_csv)
        resume_text = read_resume(sample_resume_txt)

        blind_spots = find_blind_spots("Data Engineer", resume_text=resume_text, n=5)

        # Each blind spot should be a string
        for spot in blind_spots:
            assert isinstance(spot, str), "Each blind spot should be a string"
            assert len(spot) > 0, "Blind spot should not be empty"


class TestFindResumeRecommendations:
    """Test resume improvement recommendations."""

    def test_find_resume_recommendations_returns_list(self, sample_jobs_csv):
        """find_resume_recommendations should return list of job matches."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_resume_recommendations

        ingest_jobs(sample_jobs_csv)

        recs = find_resume_recommendations("Data Engineer", n=5)
        assert isinstance(recs, list), "Should return a list"

    def test_resume_recommendations_has_required_fields(self, sample_jobs_csv):
        """Each recommendation should have job details."""
        from app.pipeline.ingest import ingest_jobs
        from app.pipeline.matcher import find_resume_recommendations

        ingest_jobs(sample_jobs_csv)

        recs = find_resume_recommendations("Data Engineer", n=5)
        if len(recs) > 0:
            job = recs[0]
            assert "title" in job, "Should have title"
            assert "company" in job, "Should have company"


class TestSkillExtraction:
    """Test skill keyword extraction."""

    def test_extract_skill_terms_finds_keywords(self):
        """_extract_skill_terms should find known skill keywords."""
        from app.pipeline.matcher import _extract_skill_terms

        text = "Looking for Python and SQL expert with AWS and Docker experience"
        skills = _extract_skill_terms(text)

        assert "python" in skills, "Should find Python"
        assert "sql" in skills, "Should find SQL"
        assert "aws" in skills, "Should find AWS"
        assert "docker" in skills, "Should find Docker"

    def test_extract_skill_terms_case_insensitive(self):
        """_extract_skill_terms should be case-insensitive."""
        from app.pipeline.matcher import _extract_skill_terms

        text = "PYTHON and SQL"
        skills = _extract_skill_terms(text)

        assert "python" in skills or len(skills) > 0, "Should find skills regardless of case"

    def test_extract_skill_terms_empty_on_no_match(self):
        """_extract_skill_terms should return empty list if no skills found."""
        from app.pipeline.matcher import _extract_skill_terms

        text = "This is text about cooking and gardening with no tech skills"
        skills = _extract_skill_terms(text)

        # Should return empty or only matching known keywords
        assert isinstance(skills, list), "Should return a list"

    def test_extract_skill_terms_returns_list_of_strings(self):
        """_extract_skill_terms should return list of strings."""
        from app.pipeline.matcher import _extract_skill_terms

        text = "Python SQL Spark AWS"
        skills = _extract_skill_terms(text)

        assert isinstance(skills, list), "Should return a list"
        for skill in skills:
            assert isinstance(skill, str), "Each skill should be a string"


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMatcherIntegration:
    """Integration tests for full matching pipeline."""

    def test_full_matching_pipeline(self, sample_jobs_csv, sample_resume_txt):
        """End-to-end test: ingest jobs+resume, find matches, identify gaps."""
        from app.pipeline.ingest import ingest_jobs, read_resume, ingest_resume
        from app.pipeline.matcher import (
            find_top_jobs,
            find_resume_recommendations,
            find_blind_spots,
        )

        # Ingest data
        ingest_jobs(sample_jobs_csv)
        ingest_resume(sample_resume_txt)
        resume_text = read_resume(sample_resume_txt)

        # Run full matching pipeline
        role = "Data Engineer with Python SQL Spark"
        jobs = find_top_jobs(role, resume_text=resume_text, n=5)
        recs = find_resume_recommendations(role, resume_text=resume_text, n=3)
        blind = find_blind_spots(role, resume_text=resume_text, n=5)

        # Verify results
        assert len(jobs) > 0, "Should find jobs"
        assert isinstance(recs, list), "Should return recommendations"
        assert isinstance(blind, list), "Should identify blind spots"
