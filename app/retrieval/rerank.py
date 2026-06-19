"""
Two-stage reranker: FlashRank cross-encoder rescores bi-encoder candidates.

ponytail: ms-marco-MiniLM-L-12-v2 (~34 MB, ONNX, no torch). Upgrade path:
  set RERANK_MODEL=bge-reranker-v2-m3 for stronger accuracy (~600 MB, slower on CPU).
  set RERANK_MODEL=none to disable and fall through to raw vector order.
"""
import logging
import os

logger = logging.getLogger(__name__)

RERANK_MODEL = os.getenv("RERANK_MODEL", "ms-marco-MiniLM-L-12-v2")

_ranker = None  # lazy-load on first call


def _get_ranker():
    global _ranker
    if _ranker is None and RERANK_MODEL != "none":
        from flashrank import Ranker
        logger.info(f"Loading reranker: {RERANK_MODEL}")
        _ranker = Ranker(model_name=RERANK_MODEL)
    return _ranker


def rerank(query: str, passages: list[dict], top_n: int) -> list[dict]:
    """Rerank passages by cross-encoder relevance. Returns top_n dicts.

    Each passage dict must have 'id' and 'document' keys (matcher._format_results shape).
    Falls back to input order if RERANK_MODEL=none or flashrank unavailable.
    """
    ranker = _get_ranker()
    if not ranker or not passages:
        return passages[:top_n]

    try:
        from flashrank import RerankRequest
        req = RerankRequest(
            query=query,
            passages=[{"id": str(i), "text": p.get("document", "")} for i, p in enumerate(passages)],
        )
        ranked = ranker.rerank(req)
        # ranked is list of dicts with "id" (str index) and "score"
        return [passages[int(r["id"])] for r in ranked[:top_n]]
    except Exception as e:
        logger.warning(f"Reranker failed, falling back to vector order: {e}")
        return passages[:top_n]


if __name__ == "__main__":
    # ponytail: self-check — run with: python -m app.retrieval.rerank
    docs = [
        {"id": "a", "document": "Senior Data Scientist Python SQL machine learning PyTorch deep learning", "title": "Data Scientist"},
        {"id": "b", "document": "Executive Chef culinary arts restaurant kitchen management food preparation", "title": "Chef"},
        {"id": "c", "document": "Plumber pipe fitting water systems residential commercial plumbing", "title": "Plumber"},
        {"id": "d", "document": "Machine Learning Engineer TensorFlow model training inference optimization", "title": "ML Engineer"},
        {"id": "e", "document": "Kindergarten Teacher early childhood education classroom management", "title": "Teacher"},
    ]
    result = rerank("data scientist machine learning Python", docs, top_n=2)
    titles = [r["title"] for r in result]
    assert len(result) == 2, f"Expected 2 results, got {len(result)}"
    assert "Data Scientist" in titles or "ML Engineer" in titles, \
        f"Expected a data/ML role in top-2, got: {titles}"
    print(f"PASS: top-2 for data science query = {titles}")
