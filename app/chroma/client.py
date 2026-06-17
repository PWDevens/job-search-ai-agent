"""
Weaviate vector database client wrapper.
Connects to Weaviate server (docker-compose service 'weaviate').
Provides thin helpers for ingestion and matching operations.

Features:
  - HTTP connection to Weaviate
  - Auto-schema creation for collections
  - Vector embeddings via sentence-transformers
  - Exponential backoff retry logic
"""
from __future__ import annotations
import logging
import requests
import json
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import CHROMA_JOBS_COL, CHROMA_RESUME_COL
from app.chroma.embeddings import LocalEmbeddingFunction

logger = logging.getLogger(__name__)

# Read from environment, fallback to defaults
import os
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "localhost")
WEAVIATE_PORT = os.getenv("WEAVIATE_PORT", "8080")
WEAVIATE_URL = f"http://{WEAVIATE_HOST}:{WEAVIATE_PORT}"

_client: Optional[requests.Session] = None
_embed_fn = LocalEmbeddingFunction()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
def _create_client():
    """Create HTTP session to Weaviate server."""
    logger.info("Connecting to Weaviate at %s", WEAVIATE_URL)
    session = requests.Session()
    # Test connection
    resp = session.get(f"{WEAVIATE_URL}/v1/meta")
    resp.raise_for_status()
    logger.debug("Weaviate connection successful")
    return session


def get_client():
    """Get or create Weaviate HTTP session."""
    global _client
    if _client is None:
        try:
            _client = _create_client()
        except Exception as exc:
            logger.critical(
                "Failed to connect to Weaviate after 3 attempts: %s. "
                "Ensure Weaviate is running at %s",
                exc, WEAVIATE_URL,
            )
            raise
    return _client


def _normalize_class_name(name: str) -> str:
    """Convert snake_case collection name to PascalCase for Weaviate."""
    parts = name.split("_")
    return "".join(p.capitalize() for p in parts)


def _ensure_class_exists(class_name: str):
    """Create Weaviate class (collection) if it doesn't exist."""
    client = get_client()
    normalized = _normalize_class_name(class_name)

    try:
        # Check if class exists
        resp = client.get(f"{WEAVIATE_URL}/v1/schema/{normalized}")
        if resp.status_code == 200:
            logger.debug("Class '%s' already exists", normalized)
            return
    except:
        pass

    # Create class with schema
    schema = {
        "class": normalized,
        "vectorIndexType": "hnsw",
        "vectorizer": "none",  # We provide vectors manually
        "properties": [
            {"name": "document", "dataType": ["text"]},
            {"name": "metadata", "dataType": ["text"]},  # Store as JSON string
        ],
    }

    resp = client.post(
        f"{WEAVIATE_URL}/v1/schema",
        json=schema,
    )
    if resp.status_code in (200, 201):
        logger.debug("Class '%s' created", normalized)
    else:
        logger.warning("Failed to create class: %s", resp.text)


def get_or_create_collection(name: str, metadata: Optional[Dict] = None):
    """Ensure Weaviate class exists and return normalized name."""
    _ensure_class_exists(name)
    return _normalize_class_name(name)


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
    """Upsert documents with vectors into Weaviate."""
    client = get_client()
    class_name = get_or_create_collection(collection_name)

    if metadatas is None:
        metadatas = [{} for _ in ids]

    # Generate embeddings for all documents
    logger.debug("Generating embeddings for %d documents", len(documents))
    embeddings = _embed_fn.embed(documents)

    # Upsert each document
    for idx, doc_id in enumerate(ids):
        obj = {
            "class": class_name,
            "id": doc_id,
            "properties": {
                "document": documents[idx],
                "metadata": json.dumps(metadatas[idx]),
            },
            "vector": embeddings[idx],
        }

        resp = client.post(
            f"{WEAVIATE_URL}/v1/objects",
            json=obj,
        )

        if resp.status_code not in (200, 201):
            logger.error("Failed to upsert document %s: %s", doc_id, resp.text)
            raise RuntimeError(f"Upsert failed for {doc_id}")

    logger.info("Upserted %d docs into '%s'", len(ids), collection_name)


def query_collection(
    collection_name: str,
    query_texts: List[str],
    n_results: int = 25,
    where: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Query similar documents from Weaviate."""
    client = get_client()
    class_name = get_or_create_collection(collection_name)

    # Generate embeddings for query texts
    query_vectors = _embed_fn.embed(query_texts)

    results = {
        "ids": [[] for _ in query_texts],
        "documents": [[] for _ in query_texts],
        "distances": [[] for _ in query_texts],
        "metadatas": [[] for _ in query_texts],
    }

    # Query for each text
    for query_idx, query_vector in enumerate(query_vectors):
        where_filter = None
        if where:
            where_filter = where

        # Use nearVector search
        query_obj = {
            "nearVector": {"vector": query_vector},
            "limit": n_results,
            "where": where_filter,
        }

        resp = client.post(
            f"{WEAVIATE_URL}/v1/graphql",
            json={
                "query": f"""
                {{
                  Get {{
                    {class_name}(nearVector: {{vector: {query_vector}}}, limit: {n_results}) {{
                      _additional {{ id distance }}
                      document
                      metadata
                    }}
                  }}
                }}
                """
            },
        )

        if resp.status_code != 200:
            logger.error("Query failed: %s", resp.text)
            raise RuntimeError(f"Query failed: {resp.text}")

        data = resp.json()
        objects = data.get("data", {}).get("Get", {}).get(class_name, [])

        for obj in objects:
            results["ids"][query_idx].append(obj.get("_additional", {}).get("id", ""))
            results["documents"][query_idx].append(obj.get("document", ""))
            results["distances"][query_idx].append(
                1 - obj.get("_additional", {}).get("distance", 0)  # Convert distance to similarity
            )
            try:
                meta = json.loads(obj.get("metadata", "{}"))
            except:
                meta = {}
            results["metadatas"][query_idx].append(meta)

    logger.debug("Query returned %d results", len(objects))
    return results


def delete_collection(name: str) -> None:
    """Delete a Weaviate class."""
    client = get_client()
    normalized = _normalize_class_name(name)

    resp = client.delete(f"{WEAVIATE_URL}/v1/schema/{normalized}")
    if resp.status_code in (200, 204):
        logger.info("Deleted class '%s'", normalized)
    else:
        logger.warning("Failed to delete class: %s", resp.text)


def health_check() -> bool:
    """Check if Weaviate is reachable and responding."""
    try:
        client = get_client()
        resp = client.get(f"{WEAVIATE_URL}/v1/meta")
        return resp.status_code == 200
    except Exception as exc:
        logger.warning("Weaviate health check failed: %s", exc)
        return False
