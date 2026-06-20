"""
APScheduler-based weekly job-search pipeline scheduler.
Runs the full CrewAI pipeline Mon–Fri at 08:00 America/New_York (configurable).
Sends email summary via SMTP after each run.

Usage (standalone):
    python -m app.scheduler

Or started automatically by the Flask app in production mode:
    ENABLE_SCHEDULER=true python run.py
"""
from __future__ import annotations
import logging
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import (
    EMAIL_TO, SCHEDULER_CRON, SCHEDULER_TZ,
    TOP_BLIND_SPOTS, TOP_JOBS, TOP_RESUME_RECS,
    UPLOAD_FOLDER, UPLOAD_RETENTION_HOURS,
)

logger = logging.getLogger(__name__)

# ── Cleanup job ────────────────────────────────────────────────────────────────

def _cleanup_old_uploads() -> None:
    """Delete uploaded files older than UPLOAD_RETENTION_HOURS."""
    import time
    from pathlib import Path

    cutoff_time = time.time() - (UPLOAD_RETENTION_HOURS * 3600)
    upload_dir = Path(UPLOAD_FOLDER)

    if not upload_dir.exists():
        return

    deleted_count = 0
    for file_path in upload_dir.glob("*"):
        if not file_path.is_file():
            continue

        if file_path.stat().st_mtime < cutoff_time:
            try:
                file_path.unlink()
                deleted_count += 1
                logger.debug("Cleaned up stale upload: %s", file_path.name)
            except Exception as exc:
                logger.warning("Failed to delete %s: %s", file_path.name, exc)

    if deleted_count > 0:
        logger.info("[Scheduler] Cleaned up %d stale upload files", deleted_count)


# ── Scheduled job ──────────────────────────────────────────────────────────────

def _run_pipeline() -> None:
    """Execute the full job-search pipeline and send an email summary."""
    logger.info("[Scheduler] Starting pipeline run at %s", datetime.now().isoformat())

    role_description = os.getenv(
        "SCHEDULED_ROLE",
        "Data Engineer / AI Engineer with Python, SQL, and LLM experience. "
        "Targeting remote or DC-area hybrid roles.",
    )
    geo_preference = os.getenv("SCHEDULED_GEO", "Washington DC")

    # Optional: ingest a fresh jobs file before running
    jobs_path   = os.getenv("SCHEDULED_JOBS_PATH", "")
    resume_path = os.getenv("SCHEDULED_RESUME_PATH", "")
    if jobs_path:
        try:
            from app.pipeline.ingest import ingest_jobs
            n = ingest_jobs(jobs_path, geo_filter=geo_preference)
            logger.info("[Scheduler] Ingested %d jobs from %s", n, jobs_path)
        except Exception as exc:
            logger.warning("[Scheduler] Job ingestion failed: %s", exc)

    if resume_path:
        try:
            from app.pipeline.ingest import ingest_resume
            ingest_resume(resume_path)
        except Exception as exc:
            logger.warning("[Scheduler] Resume ingestion failed: %s", exc)

    # Run pipeline
    try:
        from app.agents.pipeline import SearchRequest, run
        req    = SearchRequest(
            role_description=role_description,
            geo_preference=geo_preference,
        )
        result = run(req)
    except Exception as exc:
        logger.error("[Scheduler] Pipeline failed: %s", exc, exc_info=True)
        return

    # Send email summary
    try:
        from app.email.sender import send_weekly_summary
        ok = send_weekly_summary(
            top_jobs=result.top_jobs,
            resume_recs=result.resume_recs,
            blind_spots=result.blind_spots,
            role=role_description,
            geo=geo_preference,
            to_email=EMAIL_TO,
        )
        if ok:
            logger.info("[Scheduler] Email summary sent to %s", EMAIL_TO)
        else:
            logger.warning("[Scheduler] Email not sent — check SMTP config in .env")
    except Exception as exc:
        logger.error("[Scheduler] Email send failed: %s", exc)

    logger.info(
        "[Scheduler] Run complete — jobs:%d  recs:%d  blind:%d",
        len(result.top_jobs), len(result.resume_recs), len(result.blind_spots),
    )


# ── Scheduler lifecycle ────────────────────────────────────────────────────────

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    """
    Start the APScheduler background scheduler.
    Safe to call multiple times — returns existing scheduler if already running.
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)

    # Parse cron expression (default: "0 8 * * 1-5")
    parts = SCHEDULER_CRON.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
    else:
        minute, hour, day, month, day_of_week = "0", "8", "*", "*", "1-5"

    _scheduler.add_job(
        _run_pipeline,
        trigger=CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=SCHEDULER_TZ,
        ),
        id="weekly_job_search",
        name="Weekly Job-Search Pipeline",
        replace_existing=True,
        misfire_grace_time=3600,   # tolerate up to 1h of system downtime
    )

    # Add cleanup job: run every 4 hours
    _scheduler.add_job(
        _cleanup_old_uploads,
        trigger=CronTrigger(hour="*/4", timezone=SCHEDULER_TZ),
        id="cleanup_uploads",
        name="Cleanup Old Upload Files",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "[Scheduler] Started — cron='%s' tz='%s'", SCHEDULER_CRON, SCHEDULER_TZ
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped.")


# ── Run standalone ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    start_scheduler()
    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        stop_scheduler()
