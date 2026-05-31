"""
app/email/__init__.py — Email Sub-Package Marker
=================================================

WHY THIS FILE EXISTS:
---------------------
Marks `email/` as a Python package so this import works:

    from app.email.sender import send_weekly_summary

NOTE — why not just call it `mail/`?
  Python ships with a built-in module called `email` (used for MIME
  message construction). Naming our folder `email` could cause import
  conflicts on some Python versions. We keep the name but ensure
  `from __future__ import annotations` is used in sender.py and that
  Python resolves `app.email` (our package) vs `email` (stdlib) correctly
  because we always import as `from app.email.sender import ...` — the
  full path avoids any ambiguity.

WHAT'S IN THIS PACKAGE:
  sender.py → Composes and sends the weekly job-search summary email.
              Builds a rich HTML email with:
                - Score progress bars for each matched job
                - Numbered resume recommendations
                - Blind-spot list with closure plans
                - Attached job_pipeline.xlsx
              Connects to Gmail (or any SMTP server) using credentials
              from your .env file. Returns True on success, False on
              failure — never raises, so a broken email config won't
              crash the whole pipeline.

JUPYTER ANALOGY:
  In a notebook you might use smtplib directly in a cell. Here we wrap
  it in a dedicated module so the scheduler can call
  `send_weekly_summary(...)` with one line, and tests can mock it
  without touching real SMTP connections.
"""
