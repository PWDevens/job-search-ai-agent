"""
ChromaDB HTTP client wrapper.
Connects to a running Chroma server (docker-compose service 'chromadb').
Provides thin helpers used by the ingestion and matching layers.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from app.config import CHROMA_HOST, CHROMA_PORT, CHROMA_JOBS_COL, CHROMA_RESUME_COL
from app.chroma.embeddings import LocalEmbeddingFunction

logger = logging.getLogger(__name__)

_client: Optional[chromadb.HttpClient] = None
_embed_fn = LocalEmbeddingFunction()


def get_client() -> chromadb.HttpClient:
    global _client
    if _client is None:
        logger.info("Connecting to ChromaDB at %s:%s", CHROMA_HOST, CHROMA_PORT)
        _client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_or_create_collection(name: str, metadata: Optional[Dict] = None):
    client = get_client()
    col = client.get_or_create_collection(
        name=name,
        embedding_function=_embed_fn,
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
