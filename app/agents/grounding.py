"""
Grounding check: validate agent citations against retrieved jobs.
Catches hallucinated company/job references.
"""
import logging
import re
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def extract_citations(items: list[BaseModel], field: str) -> list[str]:
    """Extract cited strings from a model field.

    For JobMatch.company: direct extraction.
    For ResumeRec.why / BlindSpot.why: split on em-dash, hyphen, common separators.

    Returns list of cited company-ish strings.
    """
    citations = []

    for item in items:
        if not hasattr(item, field):
            continue

        text = getattr(item, field, "")
        if not text:
            continue

        # For company fields, just return the company name
        if field == "company":
            citations.append(text)
        else:
            # For free-text fields (why, evidence), split on separators
            # Look for "Title — Company" or similar patterns
            parts = re.split(r'[–—\-;,]', text)
            for part in parts:
                cleaned = part.strip()
                if cleaned and len(cleaned) > 2:  # Skip empty/single-char
                    # Try to extract company name (usually after "at" or similar)
                    if ' at ' in cleaned.lower():
                        company = cleaned.split(' at ', 1)[-1].strip()
                        if company:
                            citations.append(company)
                    else:
                        citations.append(cleaned)

    return citations


def check_grounding(cited_companies: list[str], retrieved_jobs: list[dict]) -> list[str]:
    """Check if cited companies are present in retrieved jobs.

    Matches case-insensitively. A citation matches if:
    - cited company is a substring of retrieved company/title, or
    - retrieved company/title is a substring of citation

    Returns list of ungrounded citations (empty = all grounded).
    """
    if not cited_companies or not retrieved_jobs:
        return []

    # Build a set of company/title strings from retrieved jobs
    retrieved_set = set()
    for job in retrieved_jobs:
        company = job.get("company", "").lower().strip()
        title = job.get("title", "").lower().strip()
        if company:
            retrieved_set.add(company)
        if title:
            retrieved_set.add(title)

    ungrounded = []
    for citation in cited_companies:
        citation_lower = citation.lower().strip()
        if not citation_lower:
            continue

        # Check if this citation is in our retrieved set (or is a substring)
        found = False
        for retrieved in retrieved_set:
            if (citation_lower in retrieved or retrieved in citation_lower):
                found = True
                break

        if not found:
            ungrounded.append(citation)

    return ungrounded
