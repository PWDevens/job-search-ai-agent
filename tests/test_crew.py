"""
Unit tests for CrewAI agent orchestration.

Tests cover:
  - SearchRequest/SearchResult dataclasses
  - Agent creation and configuration
  - Task creation and dependencies
  - Pipeline execution with mocked LLM
  - Output parsing from agents
  - Fallback behavior

Uses mocked LLM and ChromaDB for testing.
Run: pytest tests/test_crew.py -v
"""
import pytest
from unittest.mock import patch, MagicMock


class TestSearchRequest:
    """Test SearchRequest dataclass."""

    def test_search_request_creation(self):
        """SearchRequest should create with required fields."""
        from app.agents.crew import SearchRequest

        req = SearchRequest(
            role_description="Data Engineer",
            geo_preference="Remote",
            resume_text="Python SQL Spark",
            extra_context="Open to startups",
        )

        assert req.role_description == "Data Engineer"
        assert req.geo_preference == "Remote"
        assert req.resume_text == "Python SQL Spark"
        assert req.extra_context == "Open to startups"

    def test_search_request_optional_fields(self):
        """SearchRequest should allow optional fields."""
        from app.agents.crew import SearchRequest

        req = SearchRequest(role_description="SWE")
        assert req.role_description == "SWE"
        assert req.geo_preference is None
        assert req.resume_text is None
        assert req.extra_context is None


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_search_result_creation(self):
        """SearchResult should create with empty defaults."""
        from app.agents.crew import SearchResult

        result = SearchResult()
        assert result.top_jobs == []
        assert result.resume_recs == []
        assert result.blind_spots == []
        assert result.raw_agent_output == {}

    def test_search_result_with_data(self):
        """SearchResult should accept populated data."""
        from app.agents.crew import SearchResult

        jobs = [{"title": "SWE", "company": "Acme"}]
        recs = ["Add Python"]
        blind = ["Kubernetes"]

        result = SearchResult(
            top_jobs=jobs,
            resume_recs=recs,
            blind_spots=blind,
            raw_agent_output={"test": "output"},
        )

        assert len(result.top_jobs) == 1
        assert len(result.resume_recs) == 1
        assert len(result.blind_spots) == 1


class TestBuildAgents:
    """Test agent creation."""

    def test_build_agents_returns_tuple(self):
        """_build_agents should return tuple of three agents."""
        from app.agents.crew import _build_agents

        llm = MagicMock()
        agents = _build_agents(llm)

        assert isinstance(agents, tuple), "Should return tuple"
        assert len(agents) == 3, "Should return 3 agents"

    def test_job_matcher_agent_has_tools(self):
        """JobMatcher agent should have search tools."""
        from app.agents.crew import _build_agents

        llm = MagicMock()
        matcher, _, _ = _build_agents(llm)

        assert matcher.role == "Job Matching Specialist"
        assert len(matcher.tools) > 0, "Should have tools"

    def test_resume_coach_agent_configuration(self):
        """ResumeCoach agent should be configured correctly."""
        from app.agents.crew import _build_agents

        llm = MagicMock()
        _, coach, _ = _build_agents(llm)

        assert coach.role == "Resume Coach"
        assert len(coach.tools) > 0, "Should have tools"

    def test_career_strategist_agent_configuration(self):
        """CareerStrategist agent should be configured correctly."""
        from app.agents.crew import _build_agents

        llm = MagicMock()
        _, _, strategist = _build_agents(llm)

        assert strategist.role == "Career Strategist & ATS Analyst"
        assert len(strategist.tools) > 0, "Should have tools"


class TestBuildTasks:
    """Test task creation."""

    def test_build_tasks_returns_tuple(self):
        """_build_tasks should return tuple of three tasks."""
        from app.agents.crew import _build_agents, _build_tasks, SearchRequest

        llm = MagicMock()
        agents = _build_agents(llm)
        req = SearchRequest(role_description="Data Engineer")

        tasks = _build_tasks(*agents, req)

        assert isinstance(tasks, tuple), "Should return tuple"
        assert len(tasks) == 3, "Should return 3 tasks"

    def test_tasks_have_descriptions(self):
        """Tasks should have descriptions."""
        from app.agents.crew import _build_agents, _build_tasks, SearchRequest

        llm = MagicMock()
        agents = _build_agents(llm)
        req = SearchRequest(role_description="Data Engineer")

        tasks = _build_tasks(*agents, req)

        for task in tasks:
            assert task.description, "Task should have description"
            assert task.expected_output, "Task should have expected output"

    def test_tasks_have_agent_assignments(self):
        """Tasks should be assigned to agents."""
        from app.agents.crew import _build_agents, _build_tasks, SearchRequest

        llm = MagicMock()
        agents = _build_agents(llm)
        req = SearchRequest(role_description="Data Engineer")

        tasks = _build_tasks(*agents, req)

        for task in tasks:
            assert task.agent is not None, "Task should have agent"

    def test_task_dependencies(self):
        """Resume and strategist tasks should depend on matcher task."""
        from app.agents.crew import _build_agents, _build_tasks, SearchRequest

        llm = MagicMock()
        agents = _build_agents(llm)
        req = SearchRequest(role_description="Data Engineer")

        match_task, resume_task, strategy_task = _build_tasks(*agents, req)

        # Resume task should depend on match task
        assert len(resume_task.context) > 0, "Resume task should have context"
        # Strategy task should depend on match and resume
        assert len(strategy_task.context) > 0, "Strategy task should have context"


class TestExtractNumberedList:
    """Test extraction of numbered lists from agent output."""

    def test_extract_numbered_list_basic(self):
        """_extract_numbered_list should extract numbered items."""
        from app.agents.crew import _extract_numbered_list

        text = """
        1. First item
        2. Second item
        3. Third item
        """

        items = _extract_numbered_list(text)
        assert len(items) == 3, "Should extract 3 items"
        assert "First item" in items[0], "Should extract item text"

    def test_extract_numbered_list_with_periods(self):
        """_extract_numbered_list should handle both dots and parentheses."""
        from app.agents.crew import _extract_numbered_list

        text = """
        1. Item with period
        2) Item with parenthesis
        3. Another item
        """

        items = _extract_numbered_list(text)
        assert len(items) >= 2, "Should extract multiple items"

    def test_extract_numbered_list_empty(self):
        """_extract_numbered_list should return empty list for no items."""
        from app.agents.crew import _extract_numbered_list

        text = "No numbered items here"
        items = _extract_numbered_list(text)

        assert items == [], "Should return empty list"

    def test_extract_numbered_list_strips_whitespace(self):
        """_extract_numbered_list should strip whitespace from items."""
        from app.agents.crew import _extract_numbered_list

        text = "1.   Item with extra spaces   \n2.   Another   "
        items = _extract_numbered_list(text)

        assert all(not item.startswith(" ") for item in items), \
            "Should strip leading spaces"


class TestRunSearchCrew:
    """Test main crew pipeline execution."""

    def test_run_search_crew_returns_result(self, sample_jobs_csv):
        """run_search_crew should return SearchResult."""
        from app.pipeline.ingest import ingest_jobs
        from app.agents.crew import SearchRequest, run_search_crew

        ingest_jobs(sample_jobs_csv)

        req = SearchRequest(role_description="Data Engineer")

        with patch("app.agents.crew.get_llm") as mock_llm_getter:
            mock_llm = MagicMock()
            mock_llm_getter.return_value = mock_llm

            with patch("app.agents.crew.Crew") as mock_crew_class:
                mock_crew = MagicMock()
                mock_crew_class.return_value = mock_crew
                mock_crew.kickoff.return_value = "Mock crew output"

                result = run_search_crew(req)

                # Should return SearchResult
                from app.agents.crew import SearchResult
                assert isinstance(result, SearchResult), "Should return SearchResult"

    def test_run_search_crew_with_resume(self, sample_jobs_csv, sample_resume_txt):
        """run_search_crew should accept resume context."""
        from app.pipeline.ingest import ingest_jobs, read_resume
        from app.agents.crew import SearchRequest, run_search_crew

        ingest_jobs(sample_jobs_csv)
        resume_text = read_resume(sample_resume_txt)

        req = SearchRequest(
            role_description="Data Engineer",
            resume_text=resume_text,
        )

        with patch("app.agents.crew.get_llm") as mock_llm_getter:
            mock_llm = MagicMock()
            mock_llm_getter.return_value = mock_llm

            with patch("app.agents.crew.Crew") as mock_crew_class:
                mock_crew = MagicMock()
                mock_crew_class.return_value = mock_crew
                mock_crew.kickoff.return_value = "Mock output"

                result = run_search_crew(req)

                from app.agents.crew import SearchResult
                assert isinstance(result, SearchResult), "Should return SearchResult"

    def test_run_search_crew_has_fallback(self, sample_jobs_csv):
        """run_search_crew should have fallback to matcher if agents fail."""
        from app.pipeline.ingest import ingest_jobs
        from app.agents.crew import SearchRequest, run_search_crew

        ingest_jobs(sample_jobs_csv)

        req = SearchRequest(role_description="Data Engineer")

        with patch("app.agents.crew.get_llm") as mock_llm_getter:
            mock_llm = MagicMock()
            mock_llm_getter.return_value = mock_llm

            # Simulate crew failure
            with patch("app.agents.crew.Crew") as mock_crew_class:
                mock_crew = MagicMock()
                mock_crew_class.return_value = mock_crew
                mock_crew.kickoff.side_effect = Exception("Crew failed")

                # Should still return results via fallback
                result = run_search_crew(req)

                from app.agents.crew import SearchResult
                assert isinstance(result, SearchResult), "Should return SearchResult"
                # Fallback should provide at least some results
                assert isinstance(result.top_jobs, list), "Should have jobs list"


class TestCrewIntegration:
    """Integration tests for crew pipeline."""

    def test_full_crew_workflow(self, sample_jobs_csv, sample_resume_txt):
        """End-to-end: SearchRequest → Crew execution → SearchResult."""
        from app.pipeline.ingest import ingest_jobs, read_resume
        from app.agents.crew import SearchRequest, run_search_crew

        # Setup
        ingest_jobs(sample_jobs_csv)
        resume_text = read_resume(sample_resume_txt)

        # Create request
        req = SearchRequest(
            role_description="Data Engineer with Python and SQL",
            geo_preference="Remote",
            resume_text=resume_text,
            extra_context="Open to startups",
        )

        with patch("app.agents.crew.get_llm") as mock_llm_getter:
            mock_llm = MagicMock()
            mock_llm_getter.return_value = mock_llm

            with patch("app.agents.crew.Crew") as mock_crew_class:
                mock_crew = MagicMock()
                mock_crew_class.return_value = mock_crew

                # Mock agent outputs
                mock_crew.kickoff.return_value = "Mocked crew response"

                # Execute
                result = run_search_crew(req)

                # Verify result structure
                from app.agents.crew import SearchResult
                assert isinstance(result, SearchResult)
                assert isinstance(result.top_jobs, list)
                assert isinstance(result.resume_recs, list)
                assert isinstance(result.blind_spots, list)
