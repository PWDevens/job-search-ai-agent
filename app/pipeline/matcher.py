"""
Semantic matching engine.

Uses ChromaDB vector search to:
  1. Find top-N jobs most similar to the candidate's role description + resume.
  2. Generate grounding context for the ResumeCoach agent.
  3. Surface blind-spot skills (in top jobs but absent from resume).

Updated to propagate the extended schema fields:
  date_found, date_of_last_update, application_status
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from app.chroma.client import query_collection
from app.config import (
    CHROMA_JOBS_COL, CHROMA_RESUME_COL,
    TOP_BLIND_SPOTS, TOP_JOBS, TOP_RESUME_RECS,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def find_top_jobs(
    role_description: str,
    geo_preference:   Optional[str] = None,
    resume_text:      Optional[str] = None,
    n:                int           = TOP_JOBS,
) -> List[Dict[str, Any]]:
    """
    Return the top-N matching jobs ranked by cosine similarity.
    Query = role_description + optional first 400 chars of resume.
    """
    query  = _build_query(role_description, resume_text)
    where  = _geo_where(geo_preference)
    results = query_collection(CHROMA_JOBS_COL, [query], n_results=n, where=where)
    return _format_results(results, n)


def find_resume_recommendations(
    role_description: str,
    resume_text:      Optional[str] = None,
    n:                int           = TOP_RESUME_RECS,
) -> List[Dict[str, Any]]:
    """
    Return top job matches for the ResumeCoach agent's grounding context.
    Same mechanics as find_top_jobs but uses the resume-recs count.
    """
    query   = _build_query(role_description, resume_text)
    results = query_collection(CHROMA_JOBS_COL, [query], n_results=n)
    return _format_results(results, n)


def find_blind_spots(
    role_description: str,
    resume_text:      Optional[str] = None,
    n:                int           = TOP_BLIND_SPOTS,
) -> List[str]:
    """
    Return skill/keyword terms that appear frequently in matched jobs
    but are absent or rare in the user's resume chunks.
    """
    jobs          = find_top_jobs(role_description, resume_text=resume_text, n=20)
    all_job_text  = " ".join(j.get("document", "") for j in jobs).lower()

    resume_chunks: List[str] = []
    if resume_text:
        resume_chunks = [resume_text.lower()]
    else:
        try:
            res = query_collection(CHROMA_RESUME_COL, [role_description], n_results=10)
            resume_chunks = [d.lower() for d in (res.get("documents", [[]])[0] or [])]
        except Exception:
            pass
    resume_blob = " ".join(resume_chunks)

    candidate_terms = _extract_skill_terms(all_job_text)
    blind           = [t for t in candidate_terms if t not in resume_blob]
    return blind[:n]


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

_SKILL_KEYWORDS = [
    "python", "sql", "excel", "tableau", "power bi", "machine learning",
    "deep learning", "pytorch", "tensorflow", "nlp", "llm", "langchain",
    "crewai", "docker", "kubernetes", "aws", "azure", "gcp", "spark",
    "airflow", "dbt", "git", "agile", "scrum", "product management",
    "data engineering", "etl", "ci/cd", "fastapi", "flask", "react",
    "typescript", "javascript", "rust", "go", "java", "scala",
    "communication", "leadership", "stakeholder", "cross-functional",
    "a/b testing", "experiment", "analytics", "statistics", "r", "sas",
    "vector database", "chromadb", "rag", "fine-tuning", "llmops",
    "huggingface", "peft", "lora", "mlflow", "ray", "seldon",
    "terraform", "snowflake", "databricks", "kafka", "redis",
]


def _extract_skill_terms(text: str) -> List[str]:
    return [kw for kw in _SKILL_KEYWORDS if kw in text]


def _build_query(role_description: str, resume_text: Optional[str]) -> str:
    parts = [role_description.strip()]
    if resume_text:
        parts.append(resume_text[:400])
    return " ".join(parts)


def _geo_where(geo: Optional[str]) -> Optional[Dict]:
    if not geo:
        return None
    # ChromaDB where filter: location field contains geo string
    return {"location": {"$contains": geo}}


def _format_results(raw: Dict[str, Any], n: int) -> List[Dict[str, Any]]:
    """
    Convert raw ChromaDB query output into clean dicts.
    Propagates ALL metadata fields including the extended schema:
      date_found, date_of_last_update, application_status
    """
    docs      = raw.get("documents",  [[]])[0] or []
    metas     = raw.get("metadatas",  [[]])[0] or []
    distances = raw.get("distances",  [[]])[0] or []
    ids       = raw.get("ids",        [[]])[0] or []

    jobs = []
    for i, (doc, meta, dist, uid) in enumerate(
        zip(docs, metas, distances, ids), start=1
    ):
        score = round(1 - dist, 4)   # cosine similarity: 1 = perfect match
        jobs.append({
            "rank":                 i,
            "id":                   uid,
            "score":                score,
            "document":             doc,
            # ── Core fields ───────────────────────────────────────────────────
            "title":                meta.get("title",    ""),
            "company":              meta.get("company",  ""),
            "location":             meta.get("location", ""),
            "salary":               meta.get("salary",   ""),
            "url":                  meta.get("url",      ""),
            # ── Date fields ───────────────────────────────────────────────────
            "date_posted":          meta.get("date_posted",         ""),
            "date_found":           meta.get("date_found",          ""),
            "date_of_last_update":  meta.get("date_of_last_update", ""),
            # ── Application tracking ──────────────────────────────────────────
            "application_status":   meta.get("application_status", "Have Not Applied"),
            # ── Source ───────────────────────────────────────────────────────
            "source":               meta.get("source", ""),
        })
    return jobs[:n]
