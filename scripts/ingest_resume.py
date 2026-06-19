#!/usr/bin/env python3
"""
CLI script to ingest a resume (PDF, TXT, or DOCX) into ChromaDB.

Usage:
    python scripts/ingest_resume.py data/demo/demo_resume.txt
    python scripts/ingest_resume.py /path/to/resume.pdf --clear
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.ingest import ingest_resume
from app.retrieval.client import delete_collection
from app.config import CHROMA_RESUME_COL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest resume into ChromaDB")
    parser.add_argument("filepath", help="Path to resume PDF, TXT, or DOCX")
    parser.add_argument("--clear", action="store_true",
                        help="Delete resume collection before ingesting")
    args = parser.parse_args()

    path = Path(args.filepath)
    if not path.exists():
        logger.error("File not found: %s", path)
        sys.exit(1)

    if args.clear:
        logger.info("Clearing existing resume collection '%s'…", CHROMA_RESUME_COL)
        try:
            delete_collection(CHROMA_RESUME_COL)
        except Exception as exc:
            logger.warning("Could not clear collection: %s", exc)

    logger.info("Ingesting resume: %s", path)
    try:
        count = ingest_resume(path)
        logger.info("✅  Ingested %d resume chunks successfully.", count)
    except Exception as exc:
        logger.error("❌  Ingestion failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
