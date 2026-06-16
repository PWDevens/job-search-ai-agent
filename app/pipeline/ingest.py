"""
app/pipeline/ingest.py — Job and Resume Ingestion Pipeline
===========================================================

Jobs (CSV / XLSX)  → ChromaDB 'jobs' collection
Resume (PDF / TXT) → ChromaDB 'resume_chunks' collection

Supported CSV schema (all columns):
  REQUIRED: title, company, description
  OPTIONAL: location, salary, url, date_posted, date_found,
            date_of_last_update, source, application_status

Column headers are normalised automatically before validation, so
user files with spaces, mixed case, trailing whitespace, or common
aliases (e.g. "Job Title", "Employer", "Status") are all handled
gracefully. See app/pipeline/normalizer.py for details.

Application status values recognised (case-insensitive):
  Have Not Applied | Applied | Under Consideration | Interviewing |
  Offer Received   | Rejected | Withdrawn

Each job document stored in ChromaDB:
  "<title> at <company>. <description>"

Resume is chunked into ~300-word windows for granular retrieval.
"""
from __future__ import annotations
import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.chroma.client import upsert_documents
from app.config import CHROMA_JOBS_COL, CHROMA_RESUME_COL
from app.pipeline.normalizer import (
    normalize_headers,
    fuzzy_remap,
    normalise_status,
    VALID_STATUSES,
)

logger = logging.getLogger(__name__)

# ── Required columns (minimum for a valid jobs file) ──────────────────────────
REQUIRED_COLS = {"title", "company", "description"}

# ── All recognised optional columns ───────────────────────────────────────────
OPTIONAL_COLS = {
    "location", "salary", "url",
    "date_posted", "date_found", "date_of_last_update",
    "source", "application_status",
}


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _stable_id(text: str) -> str:
    """Deterministic 16-char SHA-1 hex digest used as ChromaDB document ID."""
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def _chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """Split text into overlapping word-count windows for resume chunking."""
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i: i + chunk_size]))
        i += chunk_size - overlap
    return chunks or [text]


def _clean(val) -> str:
    """Strip NaN, collapse whitespace, return a plain string."""
    if pd.isna(val):
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


def _read_dataframe(path: Path) -> pd.DataFrame:
    """
    Read a CSV or XLSX file into a DataFrame with all columns as strings.
    Then normalise headers and remap aliases so the rest of the pipeline
    always sees canonical column names regardless of what the user uploaded.
    """
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)

    df = normalize_headers(df)   # strip, lower, underscores
    df = fuzzy_remap(df)         # "Job Title" → "title" etc.
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers (also used by excel_writer for merge dedup)
# ─────────────────────────────────────────────────────────────────────────────

def read_and_normalise(path: Path) -> pd.DataFrame:
    """
    Public entry point: read a CSV/XLSX and return a fully normalised DataFrame.
    Called by both ingest_jobs() and excel_writer.merge_new_jobs_to_user_file().
    """
    return _read_dataframe(path)


# ─────────────────────────────────────────────────────────────────────────────
# Job ingestion
# ─────────────────────────────────────────────────────────────────────────────

def ingest_jobs(
    filepath:   str | Path,
    geo_filter: Optional[str] = None,
) -> int:
    """
    Load jobs from a CSV or XLSX file and upsert them into ChromaDB.

    Args:
        filepath:   Path to the jobs file (CSV or XLSX).
        geo_filter: Optional city/state string to pre-filter rows by location.
                    Case-insensitive substring match against the 'location' column.

    Returns:
        Number of job documents upserted into ChromaDB.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If required columns (title, company, description)
                           are missing even after normalisation + alias remapping.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Jobs file not found: {path}")

    df = _read_dataframe(path)

    # Validate required columns
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"Jobs file missing required columns after normalisation: {missing}\n"
            f"  Columns found: {list(df.columns)}\n"
            f"  Required:      {sorted(REQUIRED_COLS)}"
        )

    # Optional geographic pre-filter
    if geo_filter:
        loc_col = next(
            (c for c in df.columns if "location" in c or "geo" in c), None
        )
        if loc_col:
            mask = df[loc_col].str.contains(geo_filter, case=False, na=False)
            df = df[mask]
            logger.info("Geo filter '%s' → %d rows retained", geo_filter, len(df))

    ids, docs, metas = [], [], []
    for _, row in df.iterrows():
        title   = _clean(row.get("title",       ""))
        company = _clean(row.get("company",     ""))
        desc    = _clean(row.get("description", ""))

        if not (title and company and desc):
            logger.debug("Skipping row with empty required field: %r / %r", title, company)
            continue

        doc = f"{title} at {company}. {desc}"
        doc_id = _stable_id(doc)

        meta: Dict[str, str] = {
            "title":   title,
            "company": company,
        }
        for col in OPTIONAL_COLS:
            raw = row.get(col, "")
            if col == "application_status":
                meta[col] = normalise_status(_clean(raw)) if _clean(raw) else ""
            else:
                meta[col] = _clean(raw)

        ids.append(doc_id)
        docs.append(doc)
        metas.append(meta)

    if not ids:
        logger.warning("No valid job rows found in %s", path)
        return 0

    upsert_documents(CHROMA_JOBS_COL, ids, docs, metas)
    logger.info("Ingested %d jobs from %s", len(ids), path)
    return len(ids)


# ─────────────────────────────────────────────────────────────────────────────
# Resume ingestion
# ─────────────────────────────────────────────────────────────────────────────

def read_resume(path: Path) -> str:
    """
    Extract plain text from a resume file (.txt, .pdf, .docx).
    Returns an empty string on failure (never raises).
    """
    suffix = path.suffix.lower()
    try:
        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")

        if suffix == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    return "\n".join(
                        page.extract_text() or "" for page in pdf.pages
                    )
            except Exception:
                import PyPDF2
                with open(path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    return "\n".join(
                        p.extract_text() or "" for p in reader.pages
                    )

        if suffix == ".docx":
            try:
                import docx
                doc = docx.Document(path)
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                logger.warning("python-docx not installed; cannot read .docx resume.")

    except Exception as exc:
        logger.error("Failed to read resume %s: %s", path, exc)

    return ""


def ingest_resume(filepath: str | Path) -> int:
    """
    Read and chunk a resume file, then upsert chunks into ChromaDB.

    Args:
        filepath: Path to resume (.txt, .pdf, or .docx).

    Returns:
        Number of chunks upserted.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found: {path}")

    text = read_resume(path)
    if not text.strip():
        logger.warning("Resume %s appears to be empty after text extraction.", path)
        return 0

    chunks = _chunk_text(text, chunk_size=300, overlap=50)
    ids    = [_stable_id(c) for c in chunks]
    metas  = [{"source": str(path), "chunk_index": str(i)} for i in range(len(chunks))]

    upsert_documents(CHROMA_RESUME_COL, ids, chunks, metas)
    logger.info("Ingested resume: %d chunks from %s", len(chunks), path)
    return len(chunks)
