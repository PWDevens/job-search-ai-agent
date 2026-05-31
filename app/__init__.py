"""
app/__init__.py — Flask Application Factory
============================================

WHY THIS FILE EXISTS (for Jupyter/notebook users coming to app repos):
-----------------------------------------------------------------------
In a Jupyter notebook, you run cells top-to-bottom in a single file.
In a production app, code is split across many files and Python needs to
know which folders are "packages" (i.e., importable modules).

An __init__.py file tells Python: "this folder is a package."
Without it, `from app.config import ...` would raise an ImportError.

This specific __init__.py also does something extra: it contains the
"application factory" — a function (create_app) that builds and returns
the configured Flask app. Using a factory instead of a global `app`
object is a best practice because it:
  - Makes testing easier (create a fresh app per test)
  - Prevents circular imports
  - Allows multiple configs (dev vs prod) without changing code

WHAT GETS IMPORTED HERE:
  - Flask class (the web framework)
  - Our config values (SECRET_KEY, UPLOAD_FOLDER, etc.)
  - Our Blueprint (the routes defined in app/routes.py)
"""
from __future__ import annotations
import logging
from pathlib import Path

from flask import Flask

from app.config import MAX_CONTENT_BYTES, SECRET_KEY, UPLOAD_FOLDER


def create_app() -> Flask:
    """
    Build and return the configured Flask application.

    Called by run.py at startup:
        app = create_app()
        app.run(...)

    Also called by pytest fixtures in tests/ to get a fresh app per test.
    """
    app = Flask(
        __name__,
        template_folder="templates",   # → app/templates/
        static_folder="static",        # → app/static/
    )

    # Security key (used to sign session cookies — change in .env for production)
    app.secret_key = SECRET_KEY

    # File upload config
    app.config["UPLOAD_FOLDER"]      = str(UPLOAD_FOLDER)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_BYTES

    # Logging — INFO level shows pipeline progress without debug noise
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Register routes Blueprint (defined in app/routes.py)
    # A Blueprint groups related routes so they can be registered/unregistered
    # as a unit. Think of it like a module-level "cell block" of Flask routes.
    from app.routes import bp
    app.register_blueprint(bp)

    return app
