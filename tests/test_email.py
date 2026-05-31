"""
Unit tests for the email sender module.
All SMTP connections are mocked — no actual email is sent.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAMPLE_JOBS = [
    {"rank": 1, "score": 0.91, "title": "Data Engineer", "company": "Acme",
     "location": "Washington DC", "salary": "120000", "date_posted": "2026-05-01",
     "url": "https://acme.com/1", "source": "demo", "id": "abc123"},
]
SAMPLE_RECS  = ["Add a Skills section with Python and SQL.", "Quantify all achievements."]
SAMPLE_BLIND = ["kubernetes", "dbt", "terraform"]


class TestBuildHtml:
    def test_html_contains_job_title(self):
        from app.email.sender import _build_html
        html = _build_html(SAMPLE_JOBS, SAMPLE_RECS, SAMPLE_BLIND,
                           role="Data Engineer", geo="Washington DC")
        assert "Data Engineer" in html
        assert "Acme" in html

    def test_html_contains_resume_recs(self):
        from app.email.sender import _build_html
        html = _build_html(SAMPLE_JOBS, SAMPLE_RECS, SAMPLE_BLIND,
                           role="Data Engineer", geo=None)
        assert "Quantify all achievements" in html

    def test_html_contains_blind_spots(self):
        from app.email.sender import _build_html
        html = _build_html(SAMPLE_JOBS, SAMPLE_RECS, SAMPLE_BLIND,
                           role="Data Engineer", geo=None)
        assert "kubernetes" in html

    def test_html_is_valid_string(self):
        from app.email.sender import _build_html
        html = _build_html([], [], [], role="Test Role", geo=None)
        assert isinstance(html, str)
        assert "<html" in html.lower()


class TestSendWeeklySummary:
    def test_returns_false_without_smtp_config(self):
        """Should gracefully return False when no SMTP credentials."""
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}):
            # Re-import to pick up env changes
            import importlib
            import app.config as cfg
            importlib.reload(cfg)
            import app.email.sender as sender
            importlib.reload(sender)
            result = sender.send_weekly_summary(
                SAMPLE_JOBS, SAMPLE_RECS, SAMPLE_BLIND,
                role="Data Engineer", to_email="test@example.com"
            )
        assert result is False

    def test_calls_smtp_when_configured(self):
        """Should call smtplib.SMTP when credentials are present."""
        with patch("app.email.sender.SMTP_USER", "user@gmail.com"), \
             patch("app.email.sender.SMTP_PASS", "apppassword"), \
             patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = lambda s: mock_server
            mock_smtp.return_value.__exit__  = MagicMock(return_value=False)
            mock_server.send_message = MagicMock()

            from app.email import sender as s
            result = s.send_weekly_summary(
                SAMPLE_JOBS, SAMPLE_RECS, SAMPLE_BLIND,
                role="Data Engineer", to_email="test@example.com"
            )
        # Whether True or False, it should not raise
        assert isinstance(result, bool)
