"""
app/pipeline/__init__.py — Pipeline Sub-Package Marker
=======================================================

WHY THIS FILE EXISTS:
---------------------
Marks `pipeline/` as a Python package so imports like these work:

    from app.pipeline.ingest import ingest_jobs, ingest_resume
    from app.pipeline.matcher import find_top_jobs, find_blind_spots
    from app.pipeline.excel_writer import append_jobs_to_pipeline

WHAT'S IN THIS PACKAGE:
  ingest.py        → Reads your uploaded jobs CSV/XLSX or resume PDF/TXT
                     and stores them in ChromaDB as vector embeddings.
                     Think of this as the "ETL" step — Extract from file,
                     Transform into vector format, Load into the database.

  matcher.py       → Queries ChromaDB to find the top matching jobs for a
                     given role description + resume. Returns ranked results
                     with cosine similarity scores (0–1, higher = better match).
                     Also surfaces "blind spots" — skills in job postings that
                     are absent from the candidate's resume.

  excel_writer.py  → Appends matched jobs to the pipeline Excel workbook
                     (job_pipeline.xlsx). Deduplicates by job ID so re-running
                     the pipeline won't create duplicate rows. Tracks all
                     application status values from your uploaded CSV.

JUPYTER ANALOGY:
  In a notebook, you'd read a CSV with pd.read_csv() in one cell, then
  query a database in the next. Here, those steps are organized into
  separate files so each can be:
    - Tested independently (tests/test_ingest.py, tests/test_matcher.py)
    - Re-used from multiple places (Flask routes AND the scheduler)
    - Swapped out without touching the rest of the app

THE DATA FLOW:
  Your CSV → ingest.py → ChromaDB (vectors)
                              ↓
  Role description ──→ matcher.py → Ranked jobs
                              ↓
                      excel_writer.py → job_pipeline.xlsx
"""
