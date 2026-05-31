"""
Unit tests for the semantic matching engine.
All ChromaDB calls are mocked — no running services required.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("LLM_BACKEND", "mock")
os.environ.setdefault("EMBED_BACKEND", "sentence_transformers")


MOCK_QUERY_RESULT = {
    "ids":        [["id1", "id2", "id3"]],
    "documents":  [["Data Engineer at Acme. Build pipelines.",
                    "ML Engineer at Beta. Deploy LLMs.",
                    "Data Scientist at Gamma. Statistical modeling."]],
    "metadatas":  [[
        {"title": "Data Engineer", "company": "Acme", "location": "Washington DC",
         "url": "https://acme.com/1", "salary": "120000", "date_posted": "2026-05-01", "source": "demo"},
        {"title": "ML Engineer",   "company": "Beta", "location": "Remote",
         "url": "https://beta.com/2", "salary": "150000", "date_posted": "2026-05-02", "source": "demo"},
        {"title": "Data Scientist","company": "Gamma","location": "New York",
         "url": "https://gamma.com/3","salary": "110000", "date_posted": "2026-05-03", "source": "demo"},
    ]],
    "distances":  [[0.12, 0.25, 0.38]],
}


class TestFindTopJobs:
    def test_returns_list(self):
        with patch("app.pipeline.matcher.query_collection", return_value=MOCK_QUERY_RESULT):
            from app.pipeline.matcher import find_top_jobs
            result = find_top_jobs("Data Engineer Python SQL", n=3)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_rank_is_sequential(self):
        with patch("app.pipeline.matcher.query_collection", return_value=MOCK_QUERY_RESULT):
            from app.pipeline.matcher import find_top_jobs
            result = find_top_jobs("Data Engineer", n=3)
        assert [j["rank"] for j in result] == [1, 2, 3]

    def test_score_is_similarity_not_distance(self):
        with patch("app.pipeline.matcher.query_collection", return_value=MOCK_QUERY_RESULT):
            from app.pipeline.matcher import find_top_jobs
            result = find_top_jobs("Data Engineer", n=3)
        # Distance 0.12 → score 0.88, etc.
        assert result[0]["score"] == pytest.approx(0.88, abs=0.01)
        assert result[0]["score"] > result[1]["score"]

    def test_required_fields_present(self):
        with patch("app.pipeline.matcher.query_collection", return_value=MOCK_QUERY_RESULT):
            from app.pipeline.matcher import find_top_jobs
            result = find_top_jobs("Engineer", n=3)
        for job in result:
            for field in ("rank", "score", "title", "company", "location", "url"):
                assert field in job

    def test_respects_n_parameter(self):
        with patch("app.pipeline.matcher.query_collection", return_value=MOCK_QUERY_RESULT):
            from app.pipeline.matcher import find_top_jobs
            result = find_top_jobs("Engineer", n=2)
        assert len(result) == 2

    def test_empty_query_still_works(self):
        empty_result = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]
        }
        with patch("app.pipeline.matcher.query_collection", return_value=empty_result):
            from app.pipeline.matcher import find_top_jobs
            result = find_top_jobs("", n=5)
        assert result == []


class TestFindBlindSpots:
    def test_returns_list_of_strings(self):
        with patch("app.pipeline.matcher.query_collection", return_value=MOCK_QUERY_RESULT):
            from app.pipeline.matcher import find_blind_spots
            result = find_blind_spots("Data Engineer python sql", resume_text="python sql")
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_blind_spots_not_in_resume(self):
        with patch("app.pipeline.matcher.query_collection", return_value=MOCK_QUERY_RESULT):
            from app.pipeline.matcher import find_blind_spots
            resume = "python sql pandas"
            result = find_blind_spots("Data Engineer", resume_text=resume)
        # "python" and "sql" are in resume → should not be blind spots
        assert "python" not in result
        assert "sql" not in result

    def test_respects_n_limit(self):
        with patch("app.pipeline.matcher.query_collection", return_value=MOCK_QUERY_RESULT):
            from app.pipeline.matcher import find_blind_spots
            result = find_blind_spots("engineer", resume_text="nothing", n=2)
        assert len(result) <= 2
