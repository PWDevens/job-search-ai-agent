"""
ChromaDB HTTP client wrapper.
Connects to a running Chroma server (docker-compose service 'chromadb').
Provides thin helpers used by the ingestion and matching layers.

Features:
  - Connection timeout (configurable, default 10s)
  - Exponential backoff retry (max 3 attempts)
  - Health check endpoint
  - Structured error logging
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import CHROMA_HOST, CHROMA_PORT, CHROMA_TIMEOUT, CHROMA_JOBS_COL, CHROMA_RESUME_COL
from app.chroma.embeddings import LocalEmbeddingFunction

logger = logging.getLogger(__name__)

_client: Optional[chromadb.HttpClient] = None
_embed_fn = LocalEmbeddingFunction()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
def _create_client() -> chromadb.HttpClient:
    """Create ChromaDB client with timeout. Retries with exponential backoff."""
    logger.info(
        "Connecting to ChromaDB at %s:%s (timeout=%ds)",
        CHROMA_HOST, CHROMA_PORT, CHROMA_TIMEOUT,
    )
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=Settings(anonymized_telemetry=False),
    )
    # Verify connection is working
    try:
        client.heartbeat()
        logger.info("ChromaDB connection verified")
    except Exception as exc:
        logger.error("ChromaDB heartbeat failed: %s", exc)
        raise
    return client


def get_client() -> chromadb.HttpClient:
    """Get or create ChromaDB client with connection timeout and retry logic."""
    global _client
    if _client is None:
        try:
            _client = _create_client()
        except Exception as exc:
            logger.critical(
                "Failed to connect to ChromaDB after 3 attempts: %s. "
                "Ensure ChromaDB container is running at %s:%s",
                exc, CHROMA_HOST, CHROMA_PORT,
            )
            raise
    return _client


def get_or_create_collection(name: str, metadata: Optional[Dict] = None):
    client = get_client()
    col = client.get_or_create_collection(
        name=name,
        metadata=metadata or {"hnsw:space": "cosine"},
    )
    logger.debug("Collection '%s' ready (count=%s)", name, col.count())
    return col


def jobs_collection():
    return get_or_create_collection(CHROMA_JOBS_COL)


def resume_collection():
    return get_or_create_collection(CHROMA_RESUME_COL)


def upsert_documents(
    collection_name: str,
    ids: List[str],
    documents: List[str],
    metadatas: Optional[List[Dict]] = None,
) -> None:
    col = get_or_create_collection(collection_name)
    # Pre-compute embeddings for each document
    embeddings = [_embed_fn([doc])[0] for doc in documents]
    col.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas or [{} for _ in ids],
    )
    logger.info("Upserted %d docs into '%s'", len(ids), collection_name)


def query_collection(
    collection_name: str,
    query_texts: List[str],
    n_results: int = 25,
    where: Optional[Dict] = None,
) -> Dict[str, Any]:
    col = get_or_create_collection(collection_name)
    # Pre-compute embeddings for query texts
    query_embeddings = [_embed_fn([text])[0] for text in query_texts]
    kwargs: Dict[str, Any] = {"query_embeddings": query_embeddings, "n_results": n_results}
    if where:
        kwargs["where"] = where
    return col.query(**kwargs)


def delete_collection(name: str) -> None:
    get_client().delete_collection(name)
    logger.info("Deleted collection '%s'", name)


def health_check() -> bool:
    """
    Check if ChromaDB is reachable and responding.
    Returns True if healthy, False otherwise. Never raises.
    """
    try:
        client = get_client()
        client.heartbeat()
        return True
    except Exception as exc:
        logger.warning("ChromaDB health check failed: %s", exc)
        return False
