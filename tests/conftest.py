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
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("SMTP_USER",      "")
os.environ.setdefault("SMTP_PASS",      "")
os.environ.setdefault("SECRET_KEY",     "test-secret-key")


class _FakeEmbeddingFunction:
    """Deterministic bag-of-words embedding for tests — gives lexical cosine similarity
    (shared tokens -> closer) without loading the bge model. Chroma EmbeddingFunction API."""
    def __call__(self, input):
        return [self._vec(t) for t in input]

    def embed_query(self, input):
        return self.__call__(input)

    @staticmethod
    def _vec(text, dim=256):
        import hashlib, math, re
        v = [0.0] * dim
        for tok in re.findall(r"[a-z0-9]+", (text or "").lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def name(self):
        return "fake-test-embed"


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval: Mock ChromaDB client and embedding function for tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_retrieval_client():
    """
    Auto-use fixture: back app.retrieval.client with a REAL in-memory ChromaDB + a fast
    deterministic (lexical) embedding. Tests get working ingest/query without touching disk
    or loading the bge model — so integration tests actually exercise retrieval, while staying
    fast and isolated (fresh ephemeral client per test).
    """
    import chromadb
    from chromadb.config import Settings
    import app.retrieval.client as rc

    # EphemeralClient shares one in-memory backend per process, so reset for per-test isolation.
    client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False, allow_reset=True))
    client.reset()
    embed_fn = _FakeEmbeddingFunction()

    # Skip the heavy cross-encoder reranker in tests (vector order is fine) without overriding
    # the RERANK_MODEL config constant — passthrough where it's used.
    def _passthrough_rerank(query, docs, top_n=None):
        return docs[:top_n] if top_n else docs

    # Patch the module globals; _init() sees a non-None _client and won't overwrite with PersistentClient.
    with patch.object(rc, "_client", client), patch.object(rc, "_embed_fn", embed_fn), \
         patch("app.pipeline.matcher.rerank", _passthrough_rerank), \
         patch("app.pipeline.pipeline.rerank", _passthrough_rerank):
        yield client


@pytest.fixture
def chroma_client(mock_retrieval_client):
    """The in-memory ChromaDB client backing retrieval in tests (alias of the autouse fixture)."""
    return mock_retrieval_client


# ─────────────────────────────────────────────────────────────────────────────
# LLM: Mock chat function
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_llm():
    """
    Auto-use fixture: mock app.agents.base.chat() to return deterministic
    Pydantic model instances for testing agents without Ollama.
    """
    from app.agents.models import JobMatchList, ResumeRecList, CareerStrategy, JobMatch, ResumeRec, BlindSpot, StrategyRec

    def mock_chat(system: str, user: str, schema):
        """Return a mock model instance based on the schema."""
        if schema == JobMatchList:
            return JobMatchList(matches=[
                JobMatch(
                    rank=1,
                    title="Mock Job",
                    company="Mock Corp",
                    location="Remote",
                    salary="$100k",
                    url="https://mock.com/job1",
                    why_it_fits="Matches your skills in testing"
                )
            ])
        elif schema == ResumeRecList:
            return ResumeRecList(recommendations=[
                ResumeRec(
                    priority="HIGH",
                    title="Add metrics",
                    current_state="Resume lacks quantified achievements",
                    fix="Add numbers: 'improved X by Y%'",
                    why="Mock Corp values quantification",
                    impact="Better ATS ranking"
                )
            ])
        elif schema == CareerStrategy:
            return CareerStrategy(
                blind_spots=[
                    BlindSpot(
                        skill="Cloud Architecture",
                        why="Mock Corp — Cloud DevOps",
                        remediation="Take AWS Solutions Architect course",
                        time_to_proficiency="3 months",
                        priority="HIGH"
                    )
                ],
                strategy=[
                    StrategyRec(
                        title="Build cloud portfolio",
                        evidence="Mock Corp and others heavily hiring",
                        action="Complete 2 AWS projects for portfolio"
                    )
                ]
            )
        else:
            # Fallback: return empty instance
            return schema()

    with patch("app.agents.base.chat", side_effect=mock_chat):
        yield mock_chat


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: Sample data for testing
# ─────────────────────────────────────────────────────────────────────────────

# NOTE: do NOT define a `tmp_path_factory` fixture here — it shadows pytest's built-in
# session-scoped factory (returning a plain Path with no .mktemp), which breaks every
# tmp_path-dependent test ('WindowsPath' has no attribute 'mktemp'). Use the built-ins.


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
    # Test environment configured via env vars set at top of conftest.py
    yield
