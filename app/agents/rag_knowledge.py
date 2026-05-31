"""
ATS / HR / Hiring best-practice RAG knowledge base.

On first call, loads curated knowledge articles into a dedicated ChromaDB
collection ("ats_knowledge"). Subsequent calls do a vector search over it.

The knowledge base covers:
  - How ATS parsers work (keyword extraction, section detection, file formats)
  - Resume formatting best practices
  - AI/LLM-driven screening systems
  - Skills-based hiring trends
  - Cover-letter and LinkedIn optimization
  - Salary negotiation signals
  - DEI and blind-resume considerations

All content is original, curated text — no copyrighted reproductions.
"""
from __future__ import annotations
import hashlib
import logging
from typing import List

from app.chroma.client import get_or_create_collection, upsert_documents

logger = logging.getLogger(__name__)

_ATS_COLLECTION = "ats_knowledge"
_INITIALIZED    = False

# ─────────────────────────────────────────────────────────────────────────────
# Curated knowledge articles
# Each entry: (title, body_text)
# ─────────────────────────────────────────────────────────────────────────────

_KNOWLEDGE_BASE: List[tuple] = [

    ("How ATS Parsers Read Resumes",
     """Applicant Tracking Systems (ATS) parse resumes by extracting text and mapping
it to structured fields: contact info, work history, education, and skills.
Most modern ATS platforms (Workday, Greenhouse, Lever, iCIMS, Taleo) use a
combination of rule-based regex patterns and ML classifiers.

Key parsing rules:
1. FILE FORMAT: Submit PDF or DOCX. PDFs created from Word/Google Docs parse
   cleanly. PDFs exported from image editors or scanned documents fail badly.
   Never use tables, text boxes, headers/footers, or multi-column layouts —
   these confuse almost every parser.
2. SECTION HEADERS: Use plain headers — "Work Experience," "Education," "Skills."
   Fancy names like "My Journey" or "Where I've Been" are frequently skipped.
3. DATES: Use consistent Month Year format (e.g., Jan 2022 – Mar 2024).
   Year-only ranges work but are less precise. Always include both start and end.
4. JOB TITLES: Match the exact title or close variants used in the job posting.
   ATS systems score exact matches higher than synonyms.
5. KEYWORDS: ATS scores resumes by keyword density relative to the job description.
   Include both acronyms and full forms (e.g., "NLP" and "Natural Language Processing").
6. SKILLS SECTION: A clearly labeled Skills or Technical Skills section dramatically
   improves keyword extraction. List skills as a comma-separated or bulleted list,
   not embedded in paragraphs.
"""),

    ("ATS Keyword Optimization Strategies",
     """The single most effective ATS optimization tactic is keyword mirroring:
copy the exact language from the job description into your resume.

STRATEGY 1 — TITLE MIRRORING:
If the posting says "Senior Data Engineer," your most recent job title line
should include "Data Engineer" even if your official title was "Analytics Engineer."
Add the JD title in parentheses: "Analytics Engineer (Data Engineer)."

STRATEGY 2 — SKILLS MATRIX:
Create a two-column skills section listing all relevant tools, frameworks, and
methodologies. Update this section for each application to mirror the JD's priority.

STRATEGY 3 — CONTEXT KEYWORDS:
Beyond tools, ATS systems increasingly score for context: "led," "managed,"
"architected," "reduced," "increased." Use strong action verbs that match
the seniority level of the target role.

STRATEGY 4 — EDUCATION KEYWORDS:
Spell out degree names fully: "Bachelor of Science in Computer Science" rather
than "B.S. CS." Include relevant coursework for junior roles.

STRATEGY 5 — CERTIFICATIONS:
List certifications with the full official name and the issuer:
"AWS Certified Solutions Architect – Associate (Amazon Web Services, 2024)."
Abbreviations alone (e.g., "AWS SAA") are often missed by parsers.

STRATEGY 6 — AVOID OVER-STUFFING:
Keyword stuffing (hidden white text, font-color: white tricks) is instantly
detected by modern ATS and results in automatic disqualification.
"""),

    ("AI-Driven Hiring: LLM Screening and What It Means for Candidates",
     """As of 2025–2026, a growing share of enterprise hiring funnels use
LLM-based resume screening (e.g., HireVue AI, Eightfold, Phenom People).
These differ from traditional ATS in important ways:

HOW LLM SCREENERS WORK:
- They read the entire resume as a document, not as parsed fields.
- They compare it semantically against the job description — exact keywords
  matter less; contextual relevance matters more.
- They score candidates on dimensions: skills match, career trajectory,
  tenure stability, role relevance, and sometimes inferred soft skills.
- They may generate a recruiter summary ("This candidate has 6 years in MLOps
  with strong Python skills but lacks production LLM deployment experience").

IMPLICATIONS FOR CANDIDATES:
1. Write in clear, natural prose — not bullet-point fragments. LLMs parse
   full sentences better than disconnected keywords.
2. Demonstrate impact in context: "Reduced model inference latency by 40%
   by migrating from batch to streaming pipelines" beats "Improved pipelines."
3. Use a brief professional summary (3–5 sentences) at the top. LLM screeners
   heavily weight the summary for initial classification.
4. Quantify everything you can. Numbers are strong signals for LLM scorers.
5. Show progression. LLMs detect career trajectory — random lateral moves
   without narrative context score lower.
"""),

    ("Resume Formatting Best Practices for Human Readers",
     """Once through ATS, your resume reaches a human reviewer who typically
spends 6–10 seconds on first scan. Formatting for this audience:

VISUAL HIERARCHY:
- Name in large bold at top (18–22pt).
- Contact info on one line: City, State | email | LinkedIn URL | GitHub URL.
- Section headers left-aligned, all-caps or bold, with a horizontal rule.
- Consistent font (Calibri, Garamond, or Arial) at 10–11pt for body.

ACHIEVEMENT FORMAT — PAR / CAR / STAR:
Every bullet should follow: Problem → Action → Result.
Bad:  "Worked on data pipelines."
Good: "Redesigned ETL pipeline (Python, Airflow) cutting daily batch runtime
       from 4 h to 22 min, enabling same-day reporting for a 30-person analytics team."

LENGTH RULES:
- Under 5 years experience: 1 page max.
- 5–15 years: 1–2 pages.
- 15+ years / executive / academic: 2–3 pages.
- Never truncate to fit; truncating real experience is worse than going to page 2.

SECTIONS (in order):
1. Contact / Header
2. Professional Summary (3–5 sentences; optional for experienced candidates)
3. Skills / Technical Skills
4. Work Experience (reverse chronological)
5. Education
6. Certifications / Licenses
7. Projects / Open-Source (highly valued for AI/data roles)
8. Publications / Speaking (senior / research roles)
"""),

    ("Skills-Based Hiring: The Shift Away from Credentials",
     """Since 2022, skills-based hiring has accelerated significantly.
IBM, Google, Apple, and many Fortune 500 firms now explicitly state they do
not require a 4-year degree for most technical roles.

WHAT THIS MEANS:
- Bootcamp certificates, self-taught portfolios, and open-source contributions
  now carry real weight if presented correctly.
- LinkedIn's Skills Match score is used by over 77% of recruiters.
- GitHub activity (commit frequency, project stars, README quality) is a
  credible signal for software and AI/ML roles.

HOW TO LEVERAGE SKILLS-BASED HIRING:
1. Build in public: Open-source a project that demonstrates your target skills.
   A polished GitHub repo with a real use case beats a line on a resume.
2. Complete micro-credentials: Coursera, edX, DataCamp, and Codecademy
   certificates are recognized by skills-based ATS filters.
3. Add a skills assessment: LinkedIn Skills Assessments (free) add a verified
   badge to your profile for SQL, Python, Excel, etc.
4. Quantify learning speed: Mention time-to-competency for new skills
   ("Self-taught PyTorch in 6 weeks; deployed first model within 2 months").
"""),

    ("ATS Red Flags: What Gets Resumes Automatically Rejected",
     """Common automatic rejection triggers in ATS and LLM screeners:

FORMATTING RED FLAGS:
- Tables, text boxes, headers/footers (content invisible to parser)
- Graphics, icons, infographic-style resumes
- Two-column layouts (parser reads columns as one jumbled stream)
- Non-standard section headers
- Missing dates on jobs
- Job gaps with no explanation (>6 months often triggers flag)

CONTENT RED FLAGS:
- Job-hopping pattern: 3+ jobs in under 18 months each, with no explanation
- Overqualification mismatch: senior title applying for IC role
- Buzzword stuffing with no supporting evidence ("synergy," "passionate")
- Generic objective statement ("Seeking a challenging role...")
- Unexplained employment gaps after age 25

TECHNICAL RED FLAGS:
- PDF created from a scan or photo (no selectable text)
- File name with spaces or special chars: "Patrick Resume FINAL v3 (1).pdf"
  → Use: "FirstLast_Resume_2026.pdf"
- File size over 5 MB (some ATS reject large files)

MITIGATION STRATEGIES:
- Test your resume through a free ATS checker (Jobscan, Resume Worded free tier)
- Always submit as Word DOCX unless PDF is specifically requested
- Use a resume-specific filename with your name and year
"""),

    ("LinkedIn Profile Optimization for Job Search",
     """LinkedIn's recruiter search algorithm (Recruiter Spotlight) ranks profiles
by: keyword relevance, profile completeness, recency of activity, connections
with the hiring company, and Skills Assessments.

HIGH-IMPACT OPTIMIZATIONS:
1. HEADLINE (220 chars): Do not just paste your job title.
   Use: "Data Engineer | Python · Spark · AWS | Building scalable ML pipelines"
2. ABOUT SECTION (2,600 chars): Write in first person. Mirror keywords from
   your target roles. End with a clear CTA: "Open to Senior DE roles in DC/Remote."
3. FEATURED SECTION: Pin your GitHub, a portfolio project, or a relevant post.
4. EXPERIENCE: Match your resume. Add 3–5 bullets per role, achievement-focused.
5. SKILLS: Add 50 skills (LinkedIn max). Prioritize skills from target JDs.
   Get endorsements from former colleagues for top skills.
6. OPEN TO WORK: Use the "Open to Work" badge (visible to recruiters; optionally
   hidden from current employer). Set target titles, locations, and start date.
7. ACTIVITY: Comment on 3–5 posts/week in your industry. Algorithm rewards active
   profiles. Original posts get 3× more profile views than comments alone.
"""),

    ("Understanding AI Bias in Hiring and How to Navigate It",
     """AI hiring tools have documented biases that candidates can partially mitigate:

KNOWN BIAS VECTORS:
- Name-based bias: Resumes with non-Anglo names receive fewer callbacks
  in studies (Kline et al., 2022). Some candidates use initials or Anglicized
  names for initial screening.
- Photo bias: Never include a photo on US/UK resumes (illegal to request;
  biases screeners regardless).
- Address bias: Some ATS filter by zip code for on-site roles. If willing to
  relocate, do not include a full address — use "Washington, DC Area" or
  "Open to Relocation."
- Education prestige bias: Some ATS have embedded institution rankings.
  Counter by emphasizing skills, projects, and outcomes.
- Tenure bias: LLM screeners may penalize frequent job changes even when
  justified (contract roles, startup closures). Add "(Contract)" after
  role titles for non-permanent positions.

PROACTIVE STRATEGIES:
- Focus on companies with blind resume processes (anonymized first round).
- Apply via employee referral when possible (bypasses ATS entirely ~60% of cases).
- Target companies explicitly practicing skills-based hiring.
- Disclose gaps proactively with a one-line explanation in the summary.
"""),

    ("Salary Research and Negotiation Signals for AI/Data Roles (2025–2026)",
     """Salary transparency laws now cover CA, CO, NY, WA, IL, and several other
states/cities — job postings in these states must include salary ranges.

KEY DATA SOURCES (free):
- Levels.fyi: Most accurate for tech/AI/data roles at top companies
- Bureau of Labor Statistics OES: Government benchmarks by occupation code
- LinkedIn Salary Insights: Median salaries by title, location, years of experience
- Glassdoor (free tier): Self-reported, skews optimistic; useful for directional data
- Comprehensive.io: Equity + cash breakdowns for startup/growth-stage roles

AI/DATA ROLE BENCHMARKS (US, 2025–2026, approximate median TC):
- Data Analyst:        $75k–$120k    (NYC/SF: $90k–$150k)
- Data Engineer:       $110k–$165k   (FAANG: $180k–$250k+)
- ML Engineer:         $130k–$200k   (FAANG: $220k–$350k+)
- AI/LLM Engineer:     $150k–$230k   (surging demand 2025–2026)
- AI Product Manager:  $140k–$210k
- Data Scientist:      $110k–$175k

NEGOTIATION TIPS:
- Never give the first number. If forced, give a range with your target at the bottom.
- Use total compensation (TC = base + bonus + equity) as your comparison metric.
- Research the band before the offer call. Quote Levels.fyi data confidently.
- Counter every offer exactly once, in writing, with a specific number.
"""),

    ("Building an AI Agent Portfolio for Job Seekers (GitHub Best Practices)",
     """For candidates applying to AI/ML/data roles, a strong GitHub profile is
increasingly a first-screen signal. Here's how to build a compelling one:

REPO QUALITY SIGNALS:
1. README quality: Every project needs a README with: purpose, architecture
   diagram, demo GIF/screenshot, quickstart (copy-paste commands), and known
   limitations. Reviewers spend ~30 seconds on a README before deciding whether
   to explore further.
2. Code quality: Clean, typed, linted Python (ruff, black, mypy). Avoid
   "notebook soup" — convert notebooks to modular scripts with clear separation
   of concerns.
3. Project structure: Follow standard layouts (src/ layout for packages,
   tests/ directory, pyproject.toml or setup.cfg, .github/workflows/ for CI).
4. CI/CD: A passing GitHub Actions badge signals professional maturity.
   Add a simple test workflow that runs on every push.
5. Docker: Providing a docker-compose.yml makes projects instantly reproducible
   and signals DevOps awareness.

PORTFOLIO STRATEGY FOR AI ROLES:
- 1 flagship project: End-to-end, complex, well-documented (like this app).
- 2–3 supporting projects: Each demonstrating a different skill (RAG, fine-tuning,
  agentic AI, data pipeline, API design).
- Contributions to OSS: Even small PRs to popular repos (LangChain, CrewAI,
  ChromaDB, HuggingFace) are highly valued.
- Pinned repos: Pin your 6 best. Non-pinned repos are rarely explored.

COMMON MISTAKES:
- Forked repos with no original commits (looks like padding).
- Projects with no README or a one-line README.
- "Tutorial" repos that clone a YouTube walkthrough with no original work.
- Private repos for everything (no public signal of capability).
"""),

    ("Small LLM (SLM) Performance in Job-Search AI Applications",
     """Small language models (≤7B parameters) have significant capability trade-offs
when used for reasoning-intensive tasks like resume analysis and career coaching.

CAPABILITY COMPARISON (2025–2026):
Model              Params  RAM Req  ATS Analysis  Resume Recs  Blind Spots
------             ------  -------  ------------  -----------  -----------
GPT-4o (cloud)     ~1T     API      Excellent     Excellent    Excellent
Llama-3 70B (local) 70B   48 GB+   Very Good     Very Good    Very Good
Llama-3 8B         8B     6 GB     Good          Good         Fair
Phi-4-mini         3.8B   3 GB     Fair-Good     Fair         Fair
Phi-3-mini         3.8B   3 GB     Fair          Fair         Poor
Mistral 7B         7B     5 GB     Good          Good         Fair
TinyLlama 1.1B     1.1B   1 GB     Poor          Poor         Poor

SPECIFIC WEAKNESSES OF SMALL MODELS IN THIS APP:
1. Context window: Small models may truncate long job descriptions or resumes.
   Mitigation: Chunk inputs and use RAG to inject only relevant sections.
2. Instruction following: SLMs drift from structured output formats.
   Mitigation: Use strict prompt templates with few-shot examples.
3. Hallucination: SLMs fabricate specific salary numbers, company names, dates.
   Mitigation: Ground all factual claims in ChromaDB query results.
4. Reasoning chains: Complex multi-step reasoning (blind-spot analysis)
   degrades significantly below 7B params.
   Mitigation: Break tasks into smaller sub-tasks; use RAG to provide answers.
5. Consistency: SLMs produce variable output across runs.
   Mitigation: Set temperature=0.1 for structured output tasks.

RECOMMENDATION:
For serious job searching, Llama-3 8B (6 GB VRAM / ~8 GB RAM) is the
minimum practical threshold. Phi-4-mini is excellent for demo/portfolio
purposes and on severely resource-constrained machines, but augment with
ATS RAG (as implemented in this app) to compensate for reasoning gaps.
"""),

]


# ─────────────────────────────────────────────────────────────────────────────
# Initialization and query
# ─────────────────────────────────────────────────────────────────────────────

def _sid(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def _ensure_initialized() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    col = get_or_create_collection(_ATS_COLLECTION)
    if col.count() >= len(_KNOWLEDGE_BASE):
        _INITIALIZED = True
        return
    ids   = [_sid(title) for title, _ in _KNOWLEDGE_BASE]
    docs  = [f"{title}\n\n{body}" for title, body in _KNOWLEDGE_BASE]
    metas = [{"title": title, "source": "ats_knowledge_base"} for title, _ in _KNOWLEDGE_BASE]
    upsert_documents(_ATS_COLLECTION, ids, docs, metas)
    _INITIALIZED = True
    logger.info("ATS knowledge base loaded (%d articles)", len(_KNOWLEDGE_BASE))


def query_ats_knowledge(query: str, n: int = 4) -> List[str]:
    """
    Retrieve the top-n most relevant ATS knowledge articles for the given query.
    Returns a list of article text strings.
    """
    _ensure_initialized()
    from app.chroma.client import query_collection
    results = query_collection(_ATS_COLLECTION, [query], n_results=n)
    docs = results.get("documents", [[]])[0] or []
    return docs
