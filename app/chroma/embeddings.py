"""
Unified embedding interface.
Backend is selected by EMBED_BACKEND env var:
  - "ollama"               → Ollama nomic-embed-text (runs locally, no GPU required)
  - "sentence_transformers"→ all-MiniLM-L6-v2 via HuggingFace (CPU-friendly fallback)
"""
from __future__ import annotations
import logging
import requests
from typing import List

from app.config import (
    EMBED_BACKEND, OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, ST_MODEL
)

logger = logging.getLogger(__name__)

# ── lazy-loaded sentence-transformers model ────────────────────────────────────
_st_model = None


def _get_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading SentenceTransformer model: %s", ST_MODEL)
        _st_model = SentenceTransformer(ST_MODEL)
    return _st_model


# ── public API ────────────────────────────────────────────────────────────────

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Return a list of embedding vectors for the given texts."""
    if not texts:
        return []

    if EMBED_BACKEND == "sentence_transformers":
        return _embed_st(texts)
    return _embed_ollama(texts)


def embed_one(text: str) -> List[float]:
    """Convenience wrapper for a single text."""
    return embed_texts([text])[0]


# ── backends ──────────────────────────────────────────────────────────────────

def _embed_ollama(texts: List[str]) -> List[List[float]]:
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    results = []
    for text in texts:
        try:
            resp = requests.post(url, json={"model": OLLAMA_EMBED_MODEL, "prompt": text}, timeout=60)
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        except Exception as exc:
            logger.warning("Ollama embedding failed (%s), falling back to ST", exc)
            results.append(_embed_st([text])[0])
    return results


def _embed_st(texts: List[str]) -> List[List[float]]:
    model = _get_st_model()
    return model.encode(texts, show_progress_bar=False).tolist()


# ── ChromaDB-compatible embedding function class ───────────────────────────────

class LocalEmbeddingFunction:
    """Drop-in chromadb.EmbeddingFunction implementation."""

    def __call__(self, input: List[str]) -> List[List[float]]:  # noqa: A002
        return embed_texts(input)
