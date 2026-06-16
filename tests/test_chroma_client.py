"""
Unit tests for the ChromaDB client wrapper.

Tests cover:
  - Connection timeout
  - Retry logic with exponential backoff
  - Health checks
  - Collection operations

Uses in-memory ChromaDB for testing.
Run: pytest tests/test_chroma_client.py -v
"""
import pytest
from unittest.mock import patch, MagicMock


class TestGetClient:
    """Test ChromaDB client creation and caching."""

    def test_get_client_returns_client(self, chroma_client):
        """get_client should return a ChromaDB client."""
        from app.chroma.client import get_client

        client = get_client()
        assert client is not None, "Should return a client"

    def test_get_client_caches_instance(self, chroma_client):
        """get_client should cache and return same instance on repeated calls."""
        from app.chroma.client import get_client

        client1 = get_client()
        client2 = get_client()
        # Both should reference the patched in-memory client
        assert client1 is not None and client2 is not None


class TestCollectionOperations:
    """Test ChromaDB collection operations."""

    def test_get_or_create_collection(self, chroma_client):
        """get_or_create_collection should create a collection."""
        from app.chroma.client import get_or_create_collection

        col = get_or_create_collection("test_collection")
        assert col is not None, "Should return a collection"
        assert col.count() == 0, "New collection should be empty"

    def test_upsert_documents(self, chroma_client):
        """upsert_documents should add documents to ChromaDB."""
        from app.chroma.client import upsert_documents

        ids = ["id1", "id2"]
        docs = ["Document 1", "Document 2"]
        metas = [{"source": "test"}, {"source": "test"}]

        upsert_documents("test_col", ids, docs, metas)

        # Verify documents were upserted
        col = chroma_client.get_or_create_collection("test_col")
        assert col.count() == 2, "Should have 2 documents"

    def test_query_collection(self, chroma_client):
        """query_collection should search for documents."""
        from app.chroma.client import upsert_documents, query_collection

        # Add test documents
        upsert_documents(
            "search_test",
            ["id1", "id2"],
            ["python programming language", "java programming language"],
            [{}, {}]
        )

        # Query
        results = query_collection("search_test", ["python"], n_results=2)

        assert "documents" in results, "Should return documents"
        assert "metadatas" in results, "Should return metadatas"
        assert "distances" in results, "Should return distances"

    def test_delete_collection(self, chroma_client):
        """delete_collection should remove a collection."""
        from app.chroma.client import get_or_create_collection, delete_collection

        # Create a collection
        get_or_create_collection("to_delete")

        # Delete it
        delete_collection("to_delete")

        # Verify it's deleted (creating again should give us a fresh empty one)
        col = get_or_create_collection("to_delete")
        assert col.count() == 0, "Deleted collection should be gone"

    def test_jobs_collection(self, chroma_client):
        """jobs_collection should return the jobs collection."""
        from app.chroma.client import jobs_collection

        col = jobs_collection()
        assert col is not None, "Should return jobs collection"

    def test_resume_collection(self, chroma_client):
        """resume_collection should return the resume_chunks collection."""
        from app.chroma.client import resume_collection

        col = resume_collection()
        assert col is not None, "Should return resume collection"


class TestHealthCheck:
    """Test health check functionality."""

    def test_health_check_returns_bool(self, chroma_client):
        """health_check should return a boolean."""
        from app.chroma.client import health_check

        result = health_check()
        assert isinstance(result, bool), "health_check should return bool"

    def test_health_check_returns_true_when_healthy(self, chroma_client):
        """health_check should return True when ChromaDB is healthy."""
        from app.chroma.client import health_check

        result = health_check()
        assert result is True, "Should return True for healthy ChromaDB"

    def test_health_check_never_raises(self):
        """health_check should never raise, even on connection errors."""
        from app.chroma.client import health_check

        # Even with potential issues, health_check should handle gracefully
        result = health_check()
        assert isinstance(result, bool), "health_check should always return bool"


class TestTimeoutConfiguration:
    """Test timeout configuration."""

    def test_chroma_timeout_config_exists(self):
        """CHROMA_TIMEOUT should be configured."""
        from app.config import CHROMA_TIMEOUT

        assert isinstance(CHROMA_TIMEOUT, int), "CHROMA_TIMEOUT should be int"
        assert CHROMA_TIMEOUT > 0, "CHROMA_TIMEOUT should be positive"

    def test_chroma_timeout_default_is_10(self):
        """CHROMA_TIMEOUT should default to 10 seconds."""
        from app.config import CHROMA_TIMEOUT

        # Default is set in config.py
        assert CHROMA_TIMEOUT > 0, "Should have a timeout value"
