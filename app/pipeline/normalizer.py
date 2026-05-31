"""
app/pipeline/normalizer.py — Shared Column Normalisation Utilities
===================================================================

WHY THIS MODULE EXISTS:
-----------------------
Both ingest.py and excel_writer.py need to read user-uploaded CSV/XLSX
files whose column headers may differ from our standard schema in any of
these ways:

  1. Capitalisation:      "Title", "TITLE", "title" → "title"
  2. Leading/trailing spaces: "title ", " Title" → "title"
  3. Spaces instead of underscores: "date found" → "date_found"
  4. Hyphens or dots:    "date-found", "date.found" → "date_found"
  5. Multiple separators: "date__found", "date  found" → "date_found"
  6. Common aliases:      "position" → "title", "employer" → "company"
                          "link" → "url", "status" → "application_status"
                          etc.

All normalisation goes through two functions:

  normalize_headers(df)  → returns DataFrame with standardised column names
  fuzzy_remap(df)        → maps known aliases to canonical names AFTER
                           normalize_headers has already run

USAGE:
  from app.pipeline.normalizer import normalize_headers, fuzzy_remap

  df = pd.read_csv(path, dtype=str)
  df = normalize_headers(df)   # always run first
  df = fuzzy_remap(df)         # then remap aliases
"""
from __future__ import annotations
import re
import logging
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def normalize_col(name: str) -> str:
    """
    Normalise a single column name string to snake_case.

    Steps (in order):
      1. Cast to string (handles None, int column names from Excel)
      2. Strip leading/trailing whitespace
      3. Lowercase everything
      4. Replace runs of whitespace, hyphens, dots, slashes → single underscore
      5. Collapse multiple consecutive underscores → one underscore
      6. Strip any leading/trailing underscores left over

    Examples:
      "Title "         → "title"
      "DATE FOUND"     → "date_found"
      "Date-Of-Last-Update" → "date_of_last_update"
      "Application Status"  → "application_status"
      " Job   Title "  → "job_title"
      "URL/Link"       → "url_link"   (then fuzzy_remap → "url")
    """
    name = str(name).strip()
    name = name.lower()
    name = re.sub(r"[\s\-\.\/\\]+", "_", name)   # separators → underscore
    name = re.sub(r"_+", "_", name)               # collapse multiples
    name = name.strip("_")                         # clean edges
    return name


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply normalize_col to every column header in the DataFrame.
    Returns a copy — never mutates the original.
    """
    df = df.copy()
    original = list(df.columns)
    df.columns = [normalize_col(c) for c in df.columns]
    changed = [(o, n) for o, n in zip(original, df.columns) if o != n]
    if changed:
        for orig, norm in changed:
            logger.debug("Header normalised: %r → %r", orig, norm)
    return df


def fuzzy_remap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map common column-name aliases to canonical names.
    Always run AFTER normalize_headers (assumes headers are already
    lowercase, underscored, stripped).

    Canonical names (our schema):
      title | company | location | description | salary | url |
      date_posted | date_found | date_of_last_update |
      source | application_status
    """
    # ── Alias map (alias → canonical) ─────────────────────────────────────────
    # Keys must already be in normalised form (lowercase, underscored).
    ALIAS_MAP: dict[str, str] = {
        # ── title ─────────────────────────────────────────────────────────────
        "job_title":         "title",
        "job title":         "title",   # pre-normalised fallback (spaces kept)
        "position":          "title",
        "role":              "title",
        "job_role":          "title",
        "role_title":        "title",
        "posting_title":     "title",
        "open_position":     "title",

        # ── company ───────────────────────────────────────────────────────────
        "employer":          "company",
        "organization":      "company",
        "organisation":      "company",
        "org":               "company",
        "company_name":      "company",
        "employer_name":     "company",
        "hiring_company":    "company",
        "firm":              "company",

        # ── description ───────────────────────────────────────────────────────
        "job_description":   "description",
        "desc":              "description",
        "summary":           "description",
        "details":           "description",
        "body":              "description",
        "posting":           "description",
        "job_posting":       "description",
        "responsibilities":  "description",
        "about_the_role":    "description",

        # ── location ──────────────────────────────────────────────────────────
        "city":              "location",
        "geo":               "location",
        "loc":               "location",
        "place":             "location",
        "job_location":      "location",
        "work_location":     "location",
        "office_location":   "location",
        "region":            "location",
        "state":             "location",
        "metro":             "location",

        # ── salary ────────────────────────────────────────────────────────────
        "pay":               "salary",
        "compensation":      "salary",
        "comp":              "salary",
        "wage":              "salary",
        "pay_range":         "salary",
        "salary_range":      "salary",
        "salary_band":       "salary",
        "total_comp":        "salary",
        "tc":                "salary",
        "base_salary":       "salary",
        "base":              "salary",
        "pay_rate":          "salary",

        # ── url ───────────────────────────────────────────────────────────────
        "link":              "url",
        "job_url":           "url",
        "apply_url":         "url",
        "apply_link":        "url",
        "application_url":   "url",
        "application_link":  "url",
        "job_link":          "url",
        "href":              "url",
        "posting_url":       "url",
        "listing_url":       "url",
        "url_link":          "url",    # artifact of normalising "URL/Link"

        # ── date_posted ───────────────────────────────────────────────────────
        "posted":            "date_posted",
        "post_date":         "date_posted",
        "date_published":    "date_posted",
        "published":         "date_posted",
        "posting_date":      "date_posted",
        "date_listed":       "date_posted",
        "listed":            "date_posted",
        "job_posted":        "date_posted",

        # ── date_found ────────────────────────────────────────────────────────
        "date_added":        "date_found",
        "found_date":        "date_found",
        "discovery_date":    "date_found",
        "date_discovered":   "date_found",
        "added":             "date_found",
        "date_saved":        "date_found",
        "saved_date":        "date_found",
        "date_noted":        "date_found",

        # ── date_of_last_update ───────────────────────────────────────────────
        "last_updated":      "date_of_last_update",
        "updated":           "date_of_last_update",
        "update_date":       "date_of_last_update",
        "last_update":       "date_of_last_update",
        "date_updated":      "date_of_last_update",
        "modified":          "date_of_last_update",
        "date_modified":     "date_of_last_update",
        "last_modified":     "date_of_last_update",

        # ── source ────────────────────────────────────────────────────────────
        "job_source":        "source",
        "found_on":          "source",
        "platform":          "source",
        "site":              "source",
        "job_board":         "source",
        "via":               "source",
        "channel":           "source",
        "origin":            "source",

        # ── application_status ────────────────────────────────────────────────
        "status":            "application_status",
        "app_status":        "application_status",
        "application":       "application_status",
        "apply_status":      "application_status",
        "applied_status":    "application_status",
        "tracking_status":   "application_status",
        "stage":             "application_status",
        "pipeline_stage":    "application_status",
        "hiring_stage":      "application_status",
    }

    renamed = {col: ALIAS_MAP[col] for col in df.columns if col in ALIAS_MAP}
    if renamed:
        for old, new in renamed.items():
            logger.debug("Column alias remapped: %r → %r", old, new)
        df = df.rename(columns=renamed)

    return df


# ── Standard schema definition ────────────────────────────────────────────────

#: Canonical column names in our schema (order used for new rows).
STANDARD_COLS: List[str] = [
    "title",
    "company",
    "location",
    "description",
    "salary",
    "url",
    "date_posted",
    "date_found",
    "date_of_last_update",
    "source",
    "application_status",
]

#: Valid application_status values (canonical).
VALID_STATUSES: set = {
    "Have Not Applied",
    "Applied",
    "Under Consideration",
    "Interviewing",
    "Offer Received",
    "Rejected",
    "Withdrawn",
}


def normalise_status(raw: str) -> str:
    """
    Case-insensitive lookup of raw status against VALID_STATUSES.
    Returns canonical form if matched; logs a warning and returns raw if not.
    """
    stripped = str(raw).strip()
    for vs in VALID_STATUSES:
        if vs.lower() == stripped.lower():
            return vs
    if stripped:
        logger.warning("Unrecognised application_status %r — stored as-is.", stripped)
    return stripped
