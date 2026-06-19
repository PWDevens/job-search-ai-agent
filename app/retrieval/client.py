"""
ChromaDB embedded persistent client.
Replaces the Weaviate HTTP client with a simpler on-disk vector store.
"""
import logging
import chromadb
from chromadb.config import Settings
from app.config import CHROMA_DB_PATH
from app.retrieval.embeddings import LocalEmbeddingFunction

logger = logging.getLogger(__name__)

_client = None
_embed_fn = None

def _init():
    """Lazy initialization of ChromaDB client and embedding function."""
    global _client, _embed_fn
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH, settings=Settings(anonymized_telemetry=False))
        _embed_fn = LocalEmbeddingFunction()

def get_or_create_collection(name: str, metadata: dict | None = None):
    """Return a ChromaDB collection. Called by rag_knowledge.py to check .count()."""
    _init()
    return _client.get_or_create_collection(
        name=name,
        embedding_function=_embed_fn,
        metadata=metadata or {"hnsw:space": "cosine"}
    )


def upsert_documents(collection_name: str, ids: list[str], documents: list[str],
                     metadatas: list[dict] | None = None) -> None:
    """Upsert documents into a ChromaDB collection.

    ChromaDB 0.5.x rejects empty-dict and None metadata values.
    Sanitize: empty dicts become {"_": ""}, None values become "".
    """
    if metadatas is None:
        metadatas = [{} for _ in ids]

    # Sanitize metadata
    sanitized = []
    for m in metadatas:
        if not m:  # empty dict
            sanitized.append({"_": ""})
        else:
            # Coerce None values to ""
            cleaned = {}
            for k, v in m.items():
                cleaned[k] = "" if v is None else v
            sanitized.append(cleaned)

    col = get_or_create_collection(collection_name)
    col.upsert(ids=ids, documents=documents, metadatas=sanitized)


def query_collection(collection_name: str, query_texts: list[str], n_results: int = 25,
                     where: dict | None = None) -> dict:
    """Query a ChromaDB collection.

    Returns exactly what matcher._format_results expects:
    {"ids": [[...]], "documents": [[...]], "metadatas": [[...]], "distances": [[...]]}

    distances are cosine distances (0=identical); matcher computes (1 - dist) as score.
    """
    col = get_or_create_collection(collection_name)
    result = col.query(
        query_texts=query_texts,
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"]
    )
    return result


def delete_collection(name: str) -> None:
    """Delete a ChromaDB collection. Swallow NotFoundError (collection may not exist)."""
    _init()
    try:
        _client.delete_collection(name)
    except (chromadb.errors.InvalidCollectionException, ValueError):
        # Collection doesn't exist or is already gone; this is fine
        pass


def health_check() -> bool:
    """Return True if the client is usable."""
    _init()
    try:
        _client.heartbeat()
        return True
    except Exception as e:
        logger.warning(f"ChromaDB health check failed: {e}")
        return False
