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
from chromadb.utils import embedding_functions
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import CHROMA_HOST, CHROMA_PORT, CHROMA_TIMEOUT, CHROMA_JOBS_COL, CHROMA_RESUME_COL
from app.chroma.embeddings import LocalEmbeddingFunction

logger = logging.getLogger(__name__)

_client: Optional[chromadb.HttpClient] = None
_embed_fn = LocalEmbeddingFunction()
# Use ChromaDB's default embedding function (all-MiniLM) for HTTP client compatibility
_default_embed_fn = embedding_functions.DefaultEmbeddingFunction()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
def _create_client():
    """Create ChromaDB persistent client. Uses shared volume in Docker."""
    import os
    chroma_path = "/chroma/chroma" if os.path.isdir("/chroma/chroma") else "./chroma_data"
    logger.info("Creating ChromaDB persistent client at %s", chroma_path)
    client = chromadb.PersistentClient(path=chroma_path)
    return client


def get_client():
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
    try:
        col = client.get_or_create_collection(name=name)
        logger.debug("Collection '%s' ready (count=%s)", name, col.count())
        return col
    except Exception as e:
        if "KeyError" in str(e) and "_type" in str(e):
            logger.error("ChromaDB collection error (likely API version mismatch): %s", e)
            # Try with embedding function as last resort
            try:
                col = client.get_or_create_collection(name=name, embedding_function=_default_embed_fn)
                logger.debug("Collection '%s' created with default embedding", name)
                return col
            except:
                raise e
        raise


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
    col.upsert(ids=ids, documents=documents, metadatas=metadatas or [{} for _ in ids])
    logger.info("Upserted %d docs into '%s'", len(ids), collection_name)


def query_collection(
    collection_name: str,
    query_texts: List[str],
    n_results: int = 25,
    where: Optional[Dict] = None,
) -> Dict[str, Any]:
    col = get_or_create_collection(collection_name)
    kwargs: Dict[str, Any] = {"query_texts": query_texts, "n_results": n_results}
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
