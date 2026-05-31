"""
SMTP email sender.
Sends weekly job-search summary emails with inline HTML and an XLSX attachment.
Supports Gmail App Passwords, generic SMTP, and optional STARTTLS.
All credentials come from environment variables — nothing is hardcoded.
"""
from __future__ import annotations
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import (
    EMAIL_TO, SMTP_HOST, SMTP_PASS, SMTP_PORT,
    SMTP_USE_TLS, SMTP_USER, PIPELINE_XLSX,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def send_weekly_summary(
    top_jobs:     List[Dict[str, Any]],
    resume_recs:  List[str],
    blind_spots:  List[str],
    role:         str,
    geo:          Optional[str] = None,
    to_email:     str           = EMAIL_TO,
) -> bool:
    """
    Compose and send the weekly job-search summary email.
    Returns True on success, False on failure (logged).
    """
    if not SMTP_USER or not SMTP_PASS:
        logger.warning(
            "SMTP credentials not configured (SMTP_USER / SMTP_PASS). "
            "Set them in .env to enable email summaries."
        )
        return False

    subject = f"[Job-Search AI] Weekly Summary — {role[:50]}"
    html    = _build_html(top_jobs, resume_recs, blind_spots, role, geo)
    msg     = _build_message(to_email, subject, html)

    # Attach pipeline XLSX if it exists
    xlsx = Path(PIPELINE_XLSX)
    if xlsx.exists():
        _attach_file(msg, xlsx)

    return _send(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_message(to: str, subject: str, html: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))
    return msg


def _attach_file(msg: MIMEMultipart, path: Path) -> None:
    part = MIMEBase("application", "octet-stream")
    part.set_payload(path.read_bytes())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
    msg.attach(part)


def _send(msg: MIMEMultipart) -> bool:
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            if SMTP_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        logger.info("Email sent to %s via %s:%s", msg["To"], SMTP_HOST, SMTP_PORT)
        return True
    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        return False


def _build_html(
    jobs:        List[Dict[str, Any]],
    recs:        List[str],
    blinds:      List[str],
    role:        str,
    geo:         Optional[str],
) -> str:
    from datetime import datetime
    date_str = datetime.now().strftime("%B %d, %Y")

    job_rows = ""
    for j in jobs:
        score_pct = int(j.get("score", 0) * 100)
        color     = "#198754" if score_pct >= 80 else "#fd7e14" if score_pct >= 60 else "#6c757d"
        url       = j.get("url", "")
        link      = f'<a href="{url}" style="color:#0d6efd;">Apply →</a>' if url else "—"
        job_rows += f"""
        <tr>
          <td style="padding:6px 10px;">{j.get('rank','')}</td>
          <td style="padding:6px 10px;">
            <span style="background:{color};color:#fff;padding:2px 8px;border-radius:999px;font-size:11px;">
              {score_pct}%
            </span>
          </td>
          <td style="padding:6px 10px;font-weight:600;">{j.get('title','')}</td>
          <td style="padding:6px 10px;">{j.get('company','')}</td>
          <td style="padding:6px 10px;">{j.get('location','—')}</td>
          <td style="padding:6px 10px;">{j.get('salary','—')}</td>
          <td style="padding:6px 10px;">{link}</td>
        </tr>"""

    rec_items  = "".join(f"<li style='margin-bottom:8px;'>{r}</li>" for r in recs)
    blind_items = "".join(f"<li style='margin-bottom:8px;'>{b}</li>" for b in blinds)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:0;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:750px;margin:30px auto;background:#161b22;border-radius:12px;overflow:hidden;">
  <tr><td style="background:#0d6efd;padding:24px 32px;">
    <h1 style="margin:0;font-size:22px;color:#fff;">🤖 Job-Search AI — Weekly Summary</h1>
    <p style="margin:6px 0 0;color:#cfe2ff;font-size:14px;">{date_str} &nbsp;·&nbsp; {role[:70]} &nbsp;·&nbsp; {geo or 'All Locations'}</p>
  </td></tr>

  <tr><td style="padding:24px 32px;">
    <!-- Top Jobs -->
    <h2 style="color:#58a6ff;border-bottom:1px solid #30363d;padding-bottom:8px;">🏆 Top {len(jobs)} Job Matches</h2>
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:#21262d;text-align:left;">
          <th style="padding:8px 10px;">#</th>
          <th style="padding:8px 10px;">Score</th>
          <th style="padding:8px 10px;">Title</th>
          <th style="padding:8px 10px;">Company</th>
          <th style="padding:8px 10px;">Location</th>
          <th style="padding:8px 10px;">Salary</th>
          <th style="padding:8px 10px;">Link</th>
        </tr>
      </thead>
      <tbody>{job_rows}</tbody>
    </table>
    <p style="font-size:12px;color:#8b949e;margin-top:8px;">📎 Full pipeline spreadsheet attached.</p>
  </td></tr>

  <tr><td style="padding:0 32px 24px;">
    <!-- Resume Recs -->
    <h2 style="color:#3fb950;border-bottom:1px solid #30363d;padding-bottom:8px;">📝 Top Resume Recommendations</h2>
    <ol style="font-size:14px;padding-left:18px;">{rec_items or '<li>No structured recommendations this run.</li>'}</ol>
  </td></tr>

  <tr><td style="padding:0 32px 32px;">
    <!-- Blind Spots -->
    <h2 style="color:#d29922;border-bottom:1px solid #30363d;padding-bottom:8px;">🔦 Blind Spots to Address</h2>
    <ol style="font-size:14px;padding-left:18px;">{blind_items or '<li>No blind spots detected this run.</li>'}</ol>
  </td></tr>

  <tr><td style="background:#21262d;padding:16px 32px;text-align:center;font-size:12px;color:#8b949e;">
    Generated by <strong>Job-Search AI</strong> — 100% local, open-source, no cloud APIs.<br/>
    <a href="https://github.com/pwdevens/job-search-ai" style="color:#58a6ff;">github.com/pwdevens/job-search-ai</a>
  </td></tr>
</table>
</body>
</html>"""
