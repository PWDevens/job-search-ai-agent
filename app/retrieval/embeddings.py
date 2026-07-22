"""
Single embedding backend using sentence-transformers.
Replaces the dual Ollama/sentence-transformers fallback path.
"""
import logging
import os
from app.config import EMBED_MODEL

logger = logging.getLogger(__name__)

_model = None

# Opt-in only: some models (e.g. Nomic) ship custom architecture code that
# SentenceTransformer runs via trust_remote_code. OFF by default so the local-first
# tool never executes remote model code unless explicitly enabled for an experiment.
_TRUST_REMOTE = os.getenv("EMBED_TRUST_REMOTE", "0") == "1"


def _get_model():
    """Lazy-load the embedding model on first use."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {EMBED_MODEL} (trust_remote_code={_TRUST_REMOTE})")
            _model = SentenceTransformer(EMBED_MODEL, trust_remote_code=_TRUST_REMOTE)
        except Exception as e:
            logger.error(f"Failed to load embedding model {EMBED_MODEL}: {e}")
            raise
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Returns empty list if input is empty."""
    if not texts:
        return []
    return _get_model().encode(texts, show_progress_bar=False, normalize_embeddings=True).tolist()


def embed_one(text: str) -> list[float]:
    """Embed a single text."""
    return embed_texts([text])[0]


class LocalEmbeddingFunction:
    """ChromaDB-compatible embedding function.

    ChromaDB 0.5.x calls __call__(self, input) with list[str],
    expecting list[list[float]].
    """

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Embed a batch of texts for ChromaDB."""
        return embed_texts(input)

    def name(self) -> str:
        """Return the embedding function name."""
        return "local-st"
