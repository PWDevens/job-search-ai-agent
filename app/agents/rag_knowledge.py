"""
ATS / hiring best-practice RAG knowledge base.

Content lives as occupation-agnostic markdown files in app/agents/knowledge/.
On first use we (re)load them into a dedicated ChromaDB collection, then answer
queries via vector search (retrieve only the few most relevant articles — keeps
agent prompts small). Edit the .md files to change the knowledge; no code edits.

All content is original, curated text — no copyrighted reproductions.
"""
from __future__ import annotations
import hashlib
import logging
from pathlib import Path
from typing import List, Tuple

from app.retrieval.client import (
    get_or_create_collection, upsert_documents, query_collection, delete_collection,
)

logger = logging.getLogger(__name__)

_ATS_COLLECTION = "ats_knowledge"
_KNOWLEDGE_DIR  = Path(__file__).parent / "knowledge"
_INITIALIZED    = False


def _load_articles() -> List[Tuple[str, str]]:
    """Read every knowledge/*.md as (title, body). Title = first H1 or filename."""
    articles = []
    for path in sorted(_KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        first = text.splitlines()[0]
        title = first.lstrip("#").strip() if first.startswith("#") else path.stem
        articles.append((title, text))
    return articles


def _sid(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def _ensure_initialized() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    articles = _load_articles()
    if not articles:
        logger.warning("No knowledge markdown found in %s", _KNOWLEDGE_DIR)
        _INITIALIZED = True
        return
    # Rebuild fresh so edited/removed articles never linger as stale vectors.
    try:
        delete_collection(_ATS_COLLECTION)
    except Exception:
        pass
    get_or_create_collection(_ATS_COLLECTION)
    ids   = [_sid(title) for title, _ in articles]
    docs  = [body for _, body in articles]
    metas = [{"title": title, "source": "ats_knowledge_base"} for title, _ in articles]
    upsert_documents(_ATS_COLLECTION, ids, docs, metas)
    _INITIALIZED = True
    logger.info("ATS knowledge base loaded (%d articles from markdown)", len(articles))


def query_ats_knowledge(query: str, n: int = 4) -> List[str]:
    """Return the top-n most relevant ATS knowledge articles for the query."""
    _ensure_initialized()
    results = query_collection(_ATS_COLLECTION, [query], n_results=n)
    return results.get("documents", [[]])[0] or []
