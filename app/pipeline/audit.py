"""
Audit trail logging for job search pipeline.

Logs all searches with:
  - Timestamp and request parameters
  - Resume hash (privacy-preserving)
  - Raw agent outputs
  - Final results
  - Validation status

Uses SQLite for persistence. Queries via SQL or simple API.
"""
from __future__ import annotations
import json
import logging
import sqlite3
from datetime import datetime
from hashlib import md5
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Database path
AUDIT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "audit.db"


def init_audit_db() -> None:
    """Create audit database and tables if they don't exist."""
    AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(AUDIT_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role_description TEXT NOT NULL,
                geo_preference TEXT,
                resume_hash TEXT,
                top_jobs_count INTEGER,
                resume_recs_count INTEGER,
                blind_spots_count INTEGER,
                agent_validation_resume_coach INTEGER,
                agent_validation_career_strategist INTEGER,
                raw_job_matches TEXT,
                raw_resume_recs TEXT,
                raw_blind_spots TEXT,
                final_jobs_json TEXT,
                final_recs_json TEXT,
                final_blind_json TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

    logger.debug("Audit database initialized at %s", AUDIT_DB)


def _hash_resume(resume_text: Optional[str]) -> str:
    """Create privacy-preserving hash of resume (don't log actual content)."""
    if not resume_text:
        return "none"
    return md5(resume_text.encode()).hexdigest()[:12]


def log_search_run(
    role_description: str,
    geo_preference: Optional[str],
    resume_text: Optional[str],
    top_jobs: List[Dict[str, Any]],
    resume_recs: List[str],
    blind_spots: List[str],
    raw_agent_output: Dict[str, str],
    agent_validation: Dict[str, bool],
    error: Optional[str] = None,
) -> int:
    """
    Log a search run to the audit database.

    Returns the run ID for later retrieval.
    """
    init_audit_db()

    resume_hash = _hash_resume(resume_text)

    with sqlite3.connect(AUDIT_DB) as conn:
        cursor = conn.execute(
            """INSERT INTO search_runs (
                timestamp,
                role_description,
                geo_preference,
                resume_hash,
                top_jobs_count,
                resume_recs_count,
                blind_spots_count,
                agent_validation_resume_coach,
                agent_validation_career_strategist,
                raw_job_matches,
                raw_resume_recs,
                raw_blind_spots,
                final_jobs_json,
                final_recs_json,
                final_blind_json,
                error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                role_description,
                geo_preference,
                resume_hash,
                len(top_jobs),
                len(resume_recs),
                len(blind_spots),
                int(agent_validation.get("resume_coach", False)),
                int(agent_validation.get("career_strategist", False)),
                raw_agent_output.get("job_matches", ""),
                raw_agent_output.get("resume_recs", ""),
                raw_agent_output.get("blind_spots", ""),
                json.dumps([
                    {
                        "title": j.get("title"),
                        "company": j.get("company"),
                        "location": j.get("location"),
                        "score": j.get("score"),
                    }
                    for j in top_jobs
                ], default=str),
                json.dumps(resume_recs, default=str),
                json.dumps(blind_spots, default=str),
                error,
            ),
        )
        conn.commit()
        run_id = cursor.lastrowid

    logger.info(
        "Audit logged: run_id=%d role=%s jobs=%d recs=%d blind=%d",
        run_id,
        role_description[:40],
        len(top_jobs),
        len(resume_recs),
        len(blind_spots),
    )

    return run_id


def get_search_run(run_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a specific search run from the audit log."""
    init_audit_db()

    with sqlite3.connect(AUDIT_DB) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM search_runs WHERE id = ?",
            (run_id,),
        )
        row = cursor.fetchone()

    if row:
        return dict(row)
    return None


def list_search_runs(
    limit: int = 100,
    role_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List recent search runs from the audit log.

    Args:
        limit: Max number of runs to return
        role_filter: Optional substring to filter by role_description
    """
    init_audit_db()

    with sqlite3.connect(AUDIT_DB) as conn:
        conn.row_factory = sqlite3.Row

        if role_filter:
            cursor = conn.execute(
                """SELECT * FROM search_runs
                   WHERE role_description LIKE ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (f"%{role_filter}%", limit),
            )
        else:
            cursor = conn.execute(
                """SELECT * FROM search_runs
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (limit,),
            )

        return [dict(row) for row in cursor.fetchall()]


def get_audit_stats() -> Dict[str, Any]:
    """Get summary statistics from the audit log."""
    init_audit_db()

    with sqlite3.connect(AUDIT_DB) as conn:
        stats = {}

        # Total runs
        total = conn.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0]
        stats["total_runs"] = total

        # Runs with errors
        errors = conn.execute(
            "SELECT COUNT(*) FROM search_runs WHERE error IS NOT NULL"
        ).fetchone()[0]
        stats["runs_with_errors"] = errors

        # Agent validation pass rate
        validation_passed = conn.execute(
            """SELECT COUNT(*) FROM search_runs
               WHERE agent_validation_resume_coach = 1
               AND agent_validation_career_strategist = 1"""
        ).fetchone()[0]
        stats["validation_pass_rate"] = (
            f"{(validation_passed / total * 100):.1f}%"
            if total > 0
            else "N/A"
        )

        # Average results per run
        avg_jobs = conn.execute(
            "SELECT AVG(top_jobs_count) FROM search_runs"
        ).fetchone()[0]
        stats["avg_jobs_per_run"] = round(avg_jobs or 0, 1)

        avg_recs = conn.execute(
            "SELECT AVG(resume_recs_count) FROM search_runs"
        ).fetchone()[0]
        stats["avg_recs_per_run"] = round(avg_recs or 0, 1)

        # Most common roles
        most_common = conn.execute(
            """SELECT role_description, COUNT(*) as count FROM search_runs
               GROUP BY role_description
               ORDER BY count DESC
               LIMIT 5"""
        ).fetchall()
        stats["top_5_roles"] = [
            {"role": row[0][:50], "count": row[1]}
            for row in most_common
        ]

    return stats


def cleanup_old_audits(days: int = 90) -> int:
    """
    Delete audit entries older than N days.

    Returns the number of rows deleted.
    """
    init_audit_db()

    with sqlite3.connect(AUDIT_DB) as conn:
        cursor = conn.execute(
            """DELETE FROM search_runs
               WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')""",
            (days,),
        )
        conn.commit()
        deleted = cursor.rowcount

    if deleted > 0:
        logger.info("Cleaned up %d old audit entries (>%d days old)", deleted, days)

    return deleted
