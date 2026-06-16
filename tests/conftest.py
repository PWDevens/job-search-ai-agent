"""
Shared pytest configuration and fixtures.
Sets up test environment with in-memory ChromaDB and mock services.

Key features:
  - In-memory ChromaDB (no server needed)
  - Mock LLM provider
  - Test data fixtures (jobs CSV, resumes)
  - Isolated test database per test
"""
import os
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Set environment variables BEFORE imports ──────────────────────────────────
os.environ.setdefault("LLM_BACKEND",    "mock")
os.environ.setdefault("EMBED_BACKEND",  "sentence_transformers")
os.environ.setdefault("CHROMA_HOST",    "localhost")
os.environ.setdefault("CHROMA_PORT",    "8000")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("SMTP_USER",      "")
os.environ.setdefault("SMTP_PASS",      "")
os.environ.setdefault("SECRET_KEY",     "test-secret-key")
os.environ.setdefault("CHROMA_TIMEOUT", "5")


# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB: Use ephemeral (in-memory) mode for tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def chroma_client():
    """
    Session-scoped in-memory ChromaDB client.
    Used by all tests to avoid spinning up a server.
    """
    import chromadb
    from chromadb.config import Settings

    client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
    return client


@pytest.fixture(autouse=True)
def mock_chroma_get_client(chroma_client):
    """
    Auto-use fixture: patches app.chroma.client.get_client() to return
    the in-memory client instead of connecting to a real server.
    """
    with patch("app.chroma.client.get_client", return_value=chroma_client):
        yield chroma_client


@pytest.fixture(autouse=True)
def cleanup_chroma_collections(chroma_client):
    """
    Auto-use fixture: clean up all collections before each test.
    Ensures tests don't interfere with each other.
    """
    yield
    for collection_name in ["jobs", "resume_chunks"]:
        try:
            chroma_client.delete_collection(collection_name)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# LLM: Mock provider
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_llm():
    """
    Auto-use fixture: mock the LLM provider.
    Returns deterministic responses for testing agents.
    """
    mock = MagicMock()
    mock.invoke.return_value = "Mock LLM response"
    with patch("app.agents.llm_provider.get_llm", return_value=mock):
        yield mock


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: Sample data for testing
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_path_factory():
    """Temporary directory factory for creating test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_jobs_csv(tmp_path):
    """
    Minimal valid jobs CSV with required and optional columns.
    Used for testing ingest_jobs() and matching.
    """
    csv = tmp_path / "jobs.csv"
    csv.write_text(
        "title,company,location,description,salary,url,date_posted\n"
        "Data Engineer,Acme Corp,Washington DC,"
        "Build data pipelines with Python SQL and Spark. 3+ yrs exp required.,120000,https://acme.com/job1,2026-05-01\n"
        "ML Engineer,Beta Inc,Remote,"
        "Deploy LLMs using PyTorch and Kubernetes. Exp with deep learning.,150000,https://beta.com/job2,2026-05-02\n"
        "Senior SWE,Gamma Ltd,San Francisco,"
        "Full-stack development with React TypeScript and AWS. 5+ yrs.,180000,https://gamma.com/job3,2026-05-03\n"
    )
    return csv


@pytest.fixture
def sample_jobs_xlsx(tmp_path):
    """
    Minimal valid jobs XLSX file (alternative to CSV).
    """
    import pandas as pd

    xlsx = tmp_path / "jobs.xlsx"
    df = pd.DataFrame({
        "title": ["Data Engineer", "ML Engineer"],
        "company": ["Acme Corp", "Beta Inc"],
        "location": ["Washington DC", "Remote"],
        "description": [
            "Build data pipelines with Python SQL and Spark.",
            "Deploy LLMs using PyTorch and Kubernetes.",
        ],
        "salary": [120000, 150000],
        "url": ["https://acme.com/job1", "https://beta.com/job2"],
    })
    df.to_excel(xlsx, index=False)
    return xlsx


@pytest.fixture
def sample_resume_txt(tmp_path):
    """
    Minimal valid resume text file.
    Used for testing ingest_resume() and resume matching.
    """
    txt = tmp_path / "resume.txt"
    txt.write_text(
        textwrap.dedent("""\
            Jane Doe
            jane@example.com | (555) 123-4567

            SUMMARY
            Data Engineer with 5 years of Python, SQL, and Apache Spark experience.
            Expertise in building ETL pipelines and data warehousing.

            SKILLS
            Python, SQL, Spark, AWS, Docker, Kubernetes, Pandas, NumPy

            EXPERIENCE
            Data Engineer at FakeCorp (2021-2026)
            - Built ETL pipelines processing 100GB+ daily using Python and Spark
            - Managed AWS infrastructure with Terraform
            - Mentored junior engineers

            EDUCATION
            B.S. Computer Science, State University (2021)
        """)
    )
    return txt


@pytest.fixture
def sample_resume_pdf(tmp_path):
    """
    Minimal valid resume PDF (creates simple PDF for testing).
    """
    pdf = tmp_path / "resume.pdf"
    # Create a minimal PDF using reportlab
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(pdf), pagesize=letter)
        c.drawString(100, 750, "Jane Doe")
        c.drawString(100, 730, "Data Engineer with 5 years Python SQL Spark experience")
        c.drawString(100, 710, "Skills: Python, SQL, Spark, AWS, Docker")
        c.save()
    except ImportError:
        # Fallback: create a mock PDF file
        pdf.write_bytes(b"%PDF-1.4\n%Mock PDF for testing\n")
    return pdf


@pytest.fixture
def sample_large_jobs_csv(tmp_path):
    """
    Larger CSV with 100 jobs for performance testing.
    """
    csv = tmp_path / "large_jobs.csv"
    lines = [
        "title,company,location,description,salary,url,date_posted"
    ]
    for i in range(100):
        lines.append(
            f"Data Engineer,Company{i},Remote,"
            f"Build pipelines with Python SQL Spark. Role {i}.,{120000+i*1000},"
            f"https://example.com/job{i},2026-05-01"
        )
    csv.write_text("\n".join(lines))
    return csv


# ─────────────────────────────────────────────────────────────────────────────
# Session-level setup
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Session-level setup: configure test environment."""
    # Ensure embedding backend is set
    os.environ.setdefault("EMBED_BACKEND", "sentence_transformers")
    yield
