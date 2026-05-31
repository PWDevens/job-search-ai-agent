#!/usr/bin/env python3
"""
CLI script to ingest job postings (CSV or XLSX) into ChromaDB.

Usage:
    python scripts/ingest_jobs.py data/demo/demo_jobs.csv
    python scripts/ingest_jobs.py jobs.xlsx --geo "Washington DC"
    python scripts/ingest_jobs.py jobs.csv --geo "Remote" --clear
"""
import argparse
import logging
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.ingest import ingest_jobs
from app.chroma.client import delete_collection
from app.config import CHROMA_JOBS_COL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest jobs CSV/XLSX into ChromaDB")
    parser.add_argument("filepath", help="Path to jobs CSV or XLSX file")
    parser.add_argument(
        "--geo", default=None,
        help="Filter rows by location substring (e.g. 'Washington DC', 'Remote')"
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Delete the jobs collection before ingesting (fresh start)"
    )
    args = parser.parse_args()

    path = Path(args.filepath)
    if not path.exists():
        logger.error("File not found: %s", path)
        sys.exit(1)

    if args.clear:
        logger.info("Clearing existing jobs collection '%s'…", CHROMA_JOBS_COL)
        try:
            delete_collection(CHROMA_JOBS_COL)
        except Exception as exc:
            logger.warning("Could not clear collection: %s", exc)

    logger.info("Ingesting jobs from: %s (geo filter: %s)", path, args.geo or "none")
    try:
        count = ingest_jobs(path, geo_filter=args.geo)
        logger.info("✅  Ingested %d jobs successfully.", count)
    except Exception as exc:
        logger.error("❌  Ingestion failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
