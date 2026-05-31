"""
Application entry point.
  python run.py              → Flask dev server (no scheduler)
  ENABLE_SCHEDULER=true python run.py  → Flask + background scheduler
"""
import logging
import os

from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

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
