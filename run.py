"""
Application entry point.
  python run.py              → Flask dev server (no scheduler)
  ENABLE_SCHEDULER=true python run.py  → Flask + background scheduler

Logging:
  - Console output (INFO level)
  - Rotating file logs in logs/ directory
    - app.log: all application logs
    - errors.log: ERROR level only (for quick troubleshooting)
"""
import logging
import logging.handlers
import os
from pathlib import Path

from app import create_app

# Create logs directory
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Root logger configuration
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Console handler (INFO level for cleaner output)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(console_formatter)

# File handler: rotating logs (10 MB per file, keep 5 backups)
file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "app.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

# Error file handler: ERROR level only (for quick troubleshooting)
error_handler = logging.handlers.RotatingFileHandler(
    log_dir / "errors.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=3,
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(file_formatter)

# Add handlers to root logger
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)
root_logger.addHandler(error_handler)

# Log startup
logger = logging.getLogger(__name__)
logger.info("=" * 80)
logger.info("Job-Search AI Agent starting")
logger.info("Logs: console (INFO), file (%s/app.log), errors (%s/errors.log)", log_dir, log_dir)
logger.info("=" * 80)

app = create_app()

if __name__ == "__main__":
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        from app.scheduler import start_scheduler, stop_scheduler
        import atexit
        start_scheduler()
        atexit.register(stop_scheduler)

    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        use_reloader=False,   # avoid double-scheduler with reloader
    )
