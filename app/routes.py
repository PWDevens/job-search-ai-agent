"""
app/routes.py — Flask Routes
=============================

GET  /               → Search form (index.html)
POST /search         → Run agent pipeline, render results, merge into user file
POST /ingest         → Upload and ingest jobs CSV/XLSX or resume PDF/TXT
GET  /health         → Docker liveness probe
GET  /pipeline       → Download internal pipeline XLSX
GET  /download-merged → Download user's file with new leads appended
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Optional

from flask import (
    Blueprint, flash, jsonify, redirect,
    render_template, request, send_file, session, url_for,
)
from werkzeug.utils import secure_filename
import uuid

from app.config import PIPELINE_XLSX, UPLOAD_FOLDER
from app.validation import (
    validate_search_input,
    validate_file_upload,
    ValidationError,
)

logger = logging.getLogger(__name__)
bp     = Blueprint("main", __name__)

ALLOWED_JOBS   = {".csv", ".xlsx", ".xls"}
ALLOWED_RESUME = {".pdf", ".txt", ".docx"}

# Simple rate limiting: track requests per session
import time
from collections import defaultdict
_search_timestamps = defaultdict(list)


def _check_rate_limit(session_id: str, max_per_minute: int = 10) -> bool:
    """
    Check if session has exceeded rate limit (searches per minute).
    Returns True if within limit, False if exceeded.
    """
    now = time.time()
    cutoff = now - 60  # 1 minute window

    # Clean old timestamps
    _search_timestamps[session_id] = [
        ts for ts in _search_timestamps[session_id] if ts > cutoff
    ]

    if len(_search_timestamps[session_id]) >= max_per_minute:
        return False

    # Record this request
    _search_timestamps[session_id].append(now)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Session-based file management
# ─────────────────────────────────────────────────────────────────────────────

def _get_session_upload_dir() -> Path:
    """
    Get session-specific upload directory.
    Each session gets its own subdirectory to prevent filename collisions.
    """
    session_id = session.get("_id")
    if not session_id:
        # Generate new session ID if not present
        session_id = str(uuid.uuid4())
        session["_id"] = session_id

    session_dir = Path(UPLOAD_FOLDER) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _cleanup_session_uploads() -> None:
    """Delete all uploaded files for the current session."""
    session_id = session.get("_id")
    if not session_id:
        return

    session_dir = Path(UPLOAD_FOLDER) / session_id
    if session_dir.exists():
        import shutil
        try:
            shutil.rmtree(session_dir)
            logger.debug("Cleaned up session uploads: %s", session_id)
        except Exception as exc:
            logger.warning("Failed to cleanup session uploads: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _allowed(filename: str, extensions: set) -> bool:
    return Path(filename).suffix.lower() in extensions


def _save_upload(file, extensions: set) -> Optional[Path]:
    """Validate extension, secure filename, and save to session-specific directory."""
    if not file or not file.filename:
        return None
    if not _allowed(file.filename, extensions):
        return None

    # Validate file size (before saving)
    try:
        # Check Content-Length header first
        content_length = request.content_length
        if content_length and content_length > 16 * 1024 * 1024:  # 16 MB
            raise ValidationError(
                f"File too large ({content_length/1024/1024:.1f}MB). Maximum is 16MB."
            )
    except (ValidationError, ValueError) as exc:
        logger.warning("File upload validation failed: %s", exc)
        raise

    fname = secure_filename(file.filename)
    session_dir = _get_session_upload_dir()
    dest  = session_dir / fname
    file.save(dest)

    # Double-check file size after saving
    actual_size = dest.stat().st_size
    if actual_size > 16 * 1024 * 1024:
        dest.unlink()  # Delete oversized file
        raise ValidationError(
            f"File too large ({actual_size/1024/1024:.1f}MB). Maximum is 16MB."
        )

    return dest


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@bp.route("/search", methods=["POST"])
def search():
    # Rate limiting
    session_id = session.get("_id")
    if not _check_rate_limit(session_id or "anonymous"):
        flash(
            "Too many searches. Please wait a minute before searching again.",
            "warning"
        )
        return redirect(url_for("main.index"))

    # Input validation
    try:
        role_description, geo_preference, extra_context = validate_search_input(
            request.form.get("role_description", ""),
            request.form.get("geo_preference", ""),
            request.form.get("extra_context", ""),
        )
    except ValidationError as exc:
        flash(f"Invalid input: {exc}", "danger")
        return redirect(url_for("main.index"))

    # ── 1. Optional resume upload ─────────────────────────────────────────────
    resume_text: Optional[str] = None
    resume_file = request.files.get("resume_file")
    if resume_file and resume_file.filename:
        saved_resume = _save_upload(resume_file, ALLOWED_RESUME)
        if saved_resume:
            try:
                from app.pipeline.ingest import ingest_resume, read_resume
                ingest_resume(str(saved_resume))
                resume_text = read_resume(saved_resume)[:4000]
                logger.info("Resume ingested: %s (%d chars)", saved_resume.name, len(resume_text or ""))
            except Exception as exc:
                logger.warning("Resume ingest failed: %s", exc)
                flash(f"Resume could not be read ({exc}). Proceeding without it.", "warning")
            finally:
                # Always clean up uploaded resume file after processing
                if saved_resume.exists():
                    saved_resume.unlink()
                    logger.debug("Cleaned up resume file: %s", saved_resume.name)
        else:
            flash("Resume file type not supported (.pdf, .txt, .docx only).", "warning")

    # ── 2. Optional jobs file upload ──────────────────────────────────────────
    jobs_file_path: Optional[Path] = None
    jobs_file = request.files.get("jobs_file")
    if jobs_file and jobs_file.filename:
        saved_jobs = _save_upload(jobs_file, ALLOWED_JOBS)
        if saved_jobs:
            try:
                from app.pipeline.ingest import ingest_jobs
                n = ingest_jobs(str(saved_jobs), geo_filter=geo_preference)
                logger.info("Jobs file ingested: %d rows from %s", n, saved_jobs.name)
                flash(f"✅ Ingested {n} jobs from '{saved_jobs.name}' into the search index.", "info")
                # Keep reference for merging, but mark for cleanup
                jobs_file_path = saved_jobs
            except Exception as exc:
                logger.warning("Jobs file ingest failed: %s", exc)
                flash(f"Jobs file could not be read ({exc}). Using existing index.", "warning")
                jobs_file_path = None  # don't attempt merge if ingest failed
                # Clean up failed file
                if saved_jobs.exists():
                    saved_jobs.unlink()
                    logger.debug("Cleaned up failed jobs file: %s", saved_jobs.name)
        else:
            flash("Jobs file type not supported (.csv, .xlsx, .xls only).", "warning")

    # Store the jobs file path in the session so /download-merged can retrieve it
    if jobs_file_path:
        session["uploaded_jobs_path"] = str(jobs_file_path)
    else:
        session.pop("uploaded_jobs_path", None)

    # ── 3. Run pipeline ────────────────────────────────────────────────
    top_jobs, resume_recs, blind_spots = [], [], []
    agent_validation = {
        "resume_coach": False,
        "career_strategist": False,
    }
    merged_count = 0

    try:
        from app.pipeline.pipeline import SearchRequest, run
        mode = "switch" if request.form.get("mode", "stay").lower() == "switch" else "stay"
        req = SearchRequest(
            role_description=role_description,
            geo_preference=geo_preference,
            resume_text=resume_text,
            extra_context=extra_context,
            mode=mode,
        )
        result = run(req)
        top_jobs    = result.top_jobs
        resume_recs = result.resume_recs
        blind_spots = result.blind_spots
        agent_validation = result.agent_validation or agent_validation

    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        # Graceful degradation: fall back to matcher-only results
        try:
            from app.pipeline.matcher import (
                find_top_jobs, find_resume_recommendations, find_blind_spots
            )
            top_jobs    = find_top_jobs(role_description, geo_preference, resume_text)
            resume_recs_raw = find_resume_recommendations(role_description, resume_text)
            resume_recs = [
                f"{r.get('title','?')} at {r.get('company','?')}" for r in resume_recs_raw
            ]
            blind_spots = find_blind_spots(role_description, resume_text)
            flash(
                "AI agents encountered an issue — showing raw match results. "
                f"({exc})",
                "warning",
            )
        except Exception as exc2:
            logger.error("Matcher fallback also failed: %s", exc2)
            flash(f"Pipeline failed: {exc2}", "danger")

    # ── 4. Write to internal pipeline XLSX ───────────────────────────────────
    if top_jobs:
        try:
            from app.pipeline.excel_writer import append_jobs_to_pipeline
            new_in_pipeline = append_jobs_to_pipeline(top_jobs)
            logger.info("Pipeline XLSX: +%d new rows", new_in_pipeline)
        except Exception as exc:
            logger.warning("Failed to write pipeline XLSX: %s", exc)

    # ── 5. Merge new leads back into user's uploaded file ────────────────────
    if top_jobs and jobs_file_path and jobs_file_path.exists():
        try:
            from app.pipeline.excel_writer import merge_new_jobs_to_user_file
            merged_count, out_path = merge_new_jobs_to_user_file(
                user_file_path=jobs_file_path,
                new_jobs=top_jobs,
            )
            if merged_count > 0:
                session["merged_jobs_path"] = str(out_path)
                flash(
                    f"✅ Found {merged_count} new job lead(s) not in your uploaded file. "
                    f"Download your updated file below.",
                    "success",
                )
            else:
                session.pop("merged_jobs_path", None)
                flash(
                    "No new leads found beyond what's already in your uploaded file.",
                    "info",
                )
        except Exception as exc:
            logger.warning("Merge into user file failed: %s", exc)
            session.pop("merged_jobs_path", None)
            flash(f"Could not merge results into your file ({exc}).", "warning")
    else:
        session.pop("merged_jobs_path", None)

    return render_template(
        "results.html",
        role        = role_description,
        geo         = geo_preference,
        top_jobs    = top_jobs,
        resume_recs = resume_recs,
        blind_spots = blind_spots,
        merged_count= merged_count,
        has_merged_file = bool(session.get("merged_jobs_path")),
        agent_validation = agent_validation,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /ingest — manual ingestion endpoint (no pipeline run)
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/ingest", methods=["POST"])
def ingest():
    """
    Standalone ingestion endpoint.
    Accepts a jobs CSV/XLSX or resume file and loads it into ChromaDB without
    running the full agent pipeline. Useful for pre-loading data.
    """
    geo_filter = request.form.get("geo_filter", "").strip() or None
    messages   = []
    errors     = []

    # Jobs file
    jobs_file = request.files.get("jobs_file")
    if jobs_file and jobs_file.filename:
        saved = _save_upload(jobs_file, ALLOWED_JOBS)
        if saved:
            try:
                from app.pipeline.ingest import ingest_jobs
                n = ingest_jobs(str(saved), geo_filter=geo_filter)
                messages.append(f"Ingested {n} jobs from '{saved.name}'.")
            except Exception as exc:
                errors.append(f"Jobs ingest failed: {exc}")
        else:
            errors.append("Jobs file format not supported.")

    # Resume file
    resume_file = request.files.get("resume_file")
    if resume_file and resume_file.filename:
        saved = _save_upload(resume_file, ALLOWED_RESUME)
        if saved:
            try:
                from app.pipeline.ingest import ingest_resume
                n = ingest_resume(str(saved))
                messages.append(f"Ingested resume '{saved.name}' ({n} chunks).")
            except Exception as exc:
                errors.append(f"Resume ingest failed: {exc}")
        else:
            errors.append("Resume file format not supported.")

    for msg in messages:
        flash(msg, "success")
    for err in errors:
        flash(err, "danger")

    return redirect(url_for("main.index"))


# ─────────────────────────────────────────────────────────────────────────────
# /pipeline — download internal pipeline XLSX
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/pipeline", methods=["GET"])
def download_pipeline():
    path = Path(PIPELINE_XLSX)
    if not path.exists():
        flash("Pipeline workbook not found. Run a search first.", "warning")
        return redirect(url_for("main.index"))
    return send_file(
        path,
        as_attachment=True,
        download_name="job_pipeline.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /download-merged — download user file with new leads appended
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/download-merged", methods=["GET"])
def download_merged():
    """
    Download the user's original uploaded file with new AI-found job leads
    appended to it. File path is stored in the server-side session after a
    successful /search run.
    """
    merged_path_str = session.get("merged_jobs_path")
    if not merged_path_str:
        flash(
            "No merged file available. Upload a jobs file and run a search first.",
            "warning",
        )
        return redirect(url_for("main.index"))

    path = Path(merged_path_str)
    if not path.exists():
        flash("Merged file has expired. Please re-run the search.", "warning")
        session.pop("merged_jobs_path", None)
        return redirect(url_for("main.index"))

    suffix   = path.suffix.lower()
    mimetype = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if suffix == ".xlsx"
        else "text/csv"
    )
    stem         = path.stem
    download_name = f"{stem}_with_new_leads{suffix}"

    return send_file(
        path,
        as_attachment=True,
        download_name=download_name,
        mimetype=mimetype,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /health — Docker liveness probe
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("/logout", methods=["GET", "POST"])
def logout():
    """
    Clean up session uploads and clear session data.
    """
    session_id = session.get("_id")
    _cleanup_session_uploads()
    session.clear()
    flash("Session cleared. Uploaded files have been deleted.", "info")
    logger.info("Session logged out and cleaned up: %s", session_id)
    return redirect(url_for("main.index"))


@bp.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint for Docker/Kubernetes liveness probes.
    Returns 200 if ChromaDB is reachable, 503 otherwise.
    """
    from app.retrieval.client import health_check

    if health_check():
        return jsonify({
            "status": "ok",
            "service": "job-search-ai",
            "chroma_db": "healthy",
        }), 200
    else:
        return jsonify({
            "status": "degraded",
            "service": "job-search-ai",
            "chroma_db": "unavailable",
        }), 503
