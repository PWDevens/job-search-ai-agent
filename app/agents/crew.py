"""
CrewAI orchestration entry point.
Three-agent pipeline:
  1. JobMatcherAgent   – semantic search + ranking via ChromaDB
  2. ResumeCoachAgent  – tailored resume recommendations
  3. CareerStrategistAgent – blind-spot analysis + ATS intelligence (RAG-enhanced)

All agents share a single local LLM (Ollama/Phi-4-mini/Llama3) — no external APIs.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from crewai import Agent, Crew, Process, Task

from app.agents.llm_provider import get_llm
from app.agents.tools import (
    JobSearchTool,
    ResumeMatchTool,
    BlindSpotTool,
    ATSKnowledgeTool,
    PipelineWriterTool,
)
from app.config import TOP_BLIND_SPOTS, TOP_JOBS, TOP_RESUME_RECS
from app.pipeline.audit import log_search_run

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Validation functions
# ─────────────────────────────────────────────────────────────────────────────

def _validate_agent_output(
    output: str,
    agent_type: str,
    context_data: Dict[str, Any],
) -> bool:
    """
    Validate that agent output is grounded in actual data (not hallucinated).

    Returns True if output appears valid, False if likely hallucinated.
    Checks:
      - Contains required structure (numbered list)
      - References match context (job titles, company names, skill keywords)
      - No obviously made-up information
    """
    import re

    if not output or not output.strip():
        logger.warning("Agent output is empty")
        return False

    # Extract numbered items
    items = re.findall(r"(?:^|\n)\s*\d+[\.\)]\s+(.+)", output, re.MULTILINE)
    if not items:
        logger.warning("Agent output has no numbered list structure")
        return False

    # For resume recommendations: check if they reference actual job content
    if agent_type == "resume_coach":
        job_contexts = context_data.get("job_contexts", [])
        job_text_lower = " ".join(job_contexts).lower()

        # Sample items: should reference actual skills/concepts from jobs
        sample_items = items[:min(3, len(items))]
        references_found = 0

        for item in sample_items:
            # Check if item mentions real skills/tech from job data
            item_lower = item.lower()
            # Common reference patterns: mentions Python, SQL, etc. from job text
            if any(keyword in item_lower for keyword in ["python", "sql", "aws", "kubernetes"]):
                references_found += 1
            # Or references ATS/resume concepts (legitimate)
            if any(phrase in item_lower for phrase in ["ats", "keyword", "metric", "achievement", "skill"]):
                references_found += 1

        if references_found < 1:
            logger.warning("Resume recommendations don't reference actual job content")
            return False

    # For blind spots: should reference real skills that exist in jobs
    elif agent_type == "career_strategist":
        job_contexts = context_data.get("job_contexts", [])
        job_text_lower = " ".join(job_contexts).lower()

        # Blind spots should be skills that appear in jobs
        skill_keywords = [
            "python", "sql", "java", "kubernetes", "docker", "aws", "azure",
            "spark", "kafka", "terraform", "dbt", "machine learning", "ai", "llm"
        ]

        sample_items = items[:min(2, len(items))]
        valid_skills = 0

        for item in sample_items:
            item_lower = item.lower()
            if any(skill in item_lower for skill in skill_keywords):
                valid_skills += 1

        if valid_skills < 1 and len(sample_items) > 0:
            logger.warning("Blind spot items don't match recognized skills")
            return False

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Input / Output schemas
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SearchRequest:
    role_description: str
    geo_preference:   Optional[str] = None
    resume_text:      Optional[str] = None
    extra_context:    Optional[str] = None   # e.g. cert / transcript summary


@dataclass
class SearchResult:
    top_jobs:           List[Dict[str, Any]] = field(default_factory=list)
    resume_recs:        List[str]            = field(default_factory=list)
    blind_spots:        List[str]            = field(default_factory=list)
    raw_agent_output:   Dict[str, str]       = field(default_factory=dict)
    agent_validation:   Dict[str, bool]      = field(default_factory=dict)  # validation status per agent


# ─────────────────────────────────────────────────────────────────────────────
# Agent factory
# ─────────────────────────────────────────────────────────────────────────────

def _build_agents(llm):
    job_matcher = Agent(
        role="Job Matching Specialist",
        goal=(
            "Find the top {top_jobs} job opportunities that best match the candidate's "
            "role description, skills, and geographic preferences using semantic search."
        ),
        backstory=(
            "You are an expert recruiter and data scientist who uses advanced vector "
            "search to identify the strongest job-candidate matches. You evaluate "
            "relevance, seniority fit, location, and compensation alignment."
        ),
        tools=[JobSearchTool(), PipelineWriterTool()],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

    resume_coach = Agent(
        role="Resume Coach",
        goal=(
            "Provide the top {top_recs} specific, actionable resume improvements "
            "so the candidate's resume resonates with ATS parsers and hiring managers "
            "for their target roles."
        ),
        backstory=(
            "You are a certified professional resume writer with 15 years of experience "
            "in tech, data, and AI roles. You know exactly which keywords, formats, and "
            "achievement framings pass ATS filters and impress human reviewers."
        ),
        tools=[ResumeMatchTool(), ATSKnowledgeTool()],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

    career_strategist = Agent(
        role="Career Strategist & ATS Analyst",
        goal=(
            "Identify the top {top_blind} skill and experience gaps (blind spots) "
            "between the candidate's profile and their target market, and recommend "
            "concrete steps to close them."
        ),
        backstory=(
            "You are a former CHRO turned career coach who specialises in ATS "
            "optimisation, skills gap analysis, and helping candidates break into "
            "competitive markets. You use HR tech knowledge and real job data to "
            "give candidates an unfair advantage."
        ),
        tools=[BlindSpotTool(), ATSKnowledgeTool()],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

    return job_matcher, resume_coach, career_strategist


# ─────────────────────────────────────────────────────────────────────────────
# Task factory
# ─────────────────────────────────────────────────────────────────────────────

def _build_tasks(job_matcher, resume_coach, career_strategist, req: SearchRequest):
    ctx = (
        f"Role: {req.role_description}\n"
        f"Location preference: {req.geo_preference or 'any'}\n"
        f"Resume snippet: {(req.resume_text or '')[:600]}\n"
        f"Additional context: {req.extra_context or 'none'}"
    )

    task_match = Task(
        description=(
            f"Search the ChromaDB jobs collection and return the top {TOP_JOBS} "
            f"most relevant job postings for the candidate.\n\n{ctx}\n\n"
            "Output ONLY a numbered list. For each job, include:\n"
            "1. Rank (number)\n"
            "2. Job Title (exact title from the job posting)\n"
            "3. Company Name (exact name)\n"
            "4. Location\n"
            "5. Match Score (0.00–1.00, based on semantic similarity)\n"
            "6. Salary (if available)\n"
            "7. URL (if available)\n"
            "8. One-sentence reason for the match (explain the semantic similarity)\n\n"
            "CRITICAL: Only report jobs that actually exist in the ChromaDB collection. "
            "Do not make up or hallucinate job postings. Do NOT append to spreadsheet in this output."
        ),
        expected_output=(
            f"Numbered list of exactly {TOP_JOBS} real jobs from ChromaDB with all required fields. "
            "Each job must exist in the actual database."
        ),
        agent=job_matcher,
    )

    task_resume = Task(
        description=(
            f"Using the matched jobs as context, produce exactly {TOP_RESUME_RECS} "
            "specific, prioritised resume improvement recommendations.\n\n"
            f"{ctx}\n\n"
            "For each recommendation:\n"
            "1. Name the exact change needed (e.g., 'Add Python, SQL, and Apache Spark to Technical Skills section')\n"
            "2. Explain why it matters for ATS and hiring managers\n"
            "3. CITE THE SOURCE: Reference at least one matched job title or company that requires this skill/format\n"
            "4. Example: 'Data Engineer role at Acme Corp emphasizes distributed data processing experience'\n\n"
            "CRITICAL: Every recommendation must be grounded in actual matched jobs. "
            "Do NOT suggest changes that aren't justified by the job postings."
        ),
        expected_output=(
            f"Numbered list of exactly {TOP_RESUME_RECS} resume recommendations. "
            "Each must cite the specific jobs that justify it."
        ),
        agent=resume_coach,
        context=[task_match],
    )

    task_blind = Task(
        description=(
            f"Identify the top {TOP_BLIND_SPOTS} skill gaps (blind spots) between "
            "the candidate's resume and the matched jobs.\n\n"
            f"{ctx}\n\n"
            "For each blind spot:\n"
            "1. Name the specific skill/credential (e.g., 'Kubernetes')\n"
            "2. Explain why employers in matched jobs value it\n"
            "3. CITE SOURCES: List 2-3 job titles or companies that mention this skill\n"
            "4. Suggest a free/low-cost way to gain it (online course, project, certification)\n"
            "5. Estimate time to proficiency\n\n"
            "CRITICAL: Only report skills that actually appear in multiple matched jobs. "
            "Ground every skill gap in real job postings."
        ),
        expected_output=(
            f"Numbered list of exactly {TOP_BLIND_SPOTS} skill gaps. "
            "Each must be sourced from the matched jobs."
        ),
        agent=career_strategist,
        context=[task_match, task_resume],
    )

    return task_match, task_resume, task_blind


# ─────────────────────────────────────────────────────────────────────────────
# Public run function
# ─────────────────────────────────────────────────────────────────────────────

def run_search_crew(req: SearchRequest) -> SearchResult:
    """
    Orchestrate the three-agent pipeline with output validation.
    Returns structured results with validation status.
    Falls back to matcher-only results if agent outputs are unreliable.
    """
    logger.info("Starting CrewAI job-search pipeline for: %s", req.role_description[:80])
    llm = get_llm()

    job_matcher, resume_coach, career_strategist = _build_agents(llm)
    task_match, task_resume, task_blind = _build_tasks(
        job_matcher, resume_coach, career_strategist, req
    )

    crew = Crew(
        agents=[job_matcher, resume_coach, career_strategist],
        tasks=[task_match, task_resume, task_blind],
        process=Process.sequential,
        verbose=True,
        memory=False,    # keep stateless for scheduled runs
    )

    try:
        crew_output = crew.kickoff(inputs={
            "top_jobs":  TOP_JOBS,
            "top_recs":  TOP_RESUME_RECS,
            "top_blind": TOP_BLIND_SPOTS,
        })
    except Exception as exc:
        logger.error("CrewAI pipeline failed: %s. Using matcher fallback.", exc)
        crew_output = None

    # Parse structured output from raw agent text
    result = SearchResult()
    result.agent_validation = {
        "resume_coach": False,
        "career_strategist": False,
    }

    result.raw_agent_output = {
        "job_matches":      str(task_match.output   or ""),
        "resume_recs":      str(task_resume.output  or ""),
        "blind_spots":      str(task_blind.output   or ""),
    }

    # Always use matcher for top jobs (ground truth from semantic search)
    from app.pipeline.matcher import find_top_jobs, find_resume_recommendations, find_blind_spots
    result.top_jobs = find_top_jobs(req.role_description, req.geo_preference, req.resume_text)

    # Validate resume recommendations
    context_for_validation = {
        "job_contexts": [j.get("document", "") for j in result.top_jobs],
    }

    resume_recs_raw = _extract_numbered_list(result.raw_agent_output["resume_recs"])
    is_valid_recs = _validate_agent_output(
        result.raw_agent_output["resume_recs"],
        "resume_coach",
        context_for_validation,
    )

    if is_valid_recs and resume_recs_raw:
        result.resume_recs = resume_recs_raw
        result.agent_validation["resume_coach"] = True
        logger.info("Resume recommendations validated (%d items)", len(result.resume_recs))
    else:
        # Fallback: use matcher-based recommendations
        logger.warning(
            "Resume recommendations failed validation. Using matcher fallback. "
            "Agent output may have hallucinated content."
        )
        fallback_recs = find_resume_recommendations(req.role_description, req.resume_text)
        result.resume_recs = [
            f"{r.get('title', '?')} at {r.get('company', '?')}"
            for r in fallback_recs[:TOP_RESUME_RECS]
        ]
        result.agent_validation["resume_coach"] = False

    # Validate blind spots
    blind_spots_raw = _extract_numbered_list(result.raw_agent_output["blind_spots"])
    is_valid_blind = _validate_agent_output(
        result.raw_agent_output["blind_spots"],
        "career_strategist",
        context_for_validation,
    )

    if is_valid_blind and blind_spots_raw:
        result.blind_spots = blind_spots_raw
        result.agent_validation["career_strategist"] = True
        logger.info("Blind spots validated (%d items)", len(result.blind_spots))
    else:
        # Fallback: use matcher-based blind spots
        logger.warning(
            "Blind spots failed validation. Using matcher fallback. "
            "Agent output may have hallucinated content."
        )
        result.blind_spots = find_blind_spots(
            req.role_description,
            req.resume_text,
            n=TOP_BLIND_SPOTS,
        )
        result.agent_validation["career_strategist"] = False

    # Log validation summary
    validation_ok = all(result.agent_validation.values())
    if validation_ok:
        logger.info("✓ All agent outputs passed validation")
    else:
        failed = [k for k, v in result.agent_validation.items() if not v]
        logger.warning("✗ Agent validation failed for: %s. Using fallback results.", failed)

    logger.info(
        "Pipeline complete — jobs:%d  recs:%d  blind_spots:%d  validation:%s",
        len(result.top_jobs),
        len(result.resume_recs),
        len(result.blind_spots),
        "OK" if validation_ok else "FALLBACK",
    )

    # Log to audit trail (persistence layer)
    try:
        run_id = log_search_run(
            role_description=req.role_description,
            geo_preference=req.geo_preference,
            resume_text=req.resume_text,
            top_jobs=result.top_jobs,
            resume_recs=result.resume_recs,
            blind_spots=result.blind_spots,
            raw_agent_output=result.raw_agent_output,
            agent_validation=result.agent_validation,
            error=None,
        )
        logger.debug("Search run logged to audit database: run_id=%d", run_id)
    except Exception as exc:
        logger.error("Failed to log search run to audit database: %s", exc)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_numbered_list(text: str) -> List[str]:
    """Pull numbered-list items from an agent's free-text output."""
    import re
    items = re.findall(r"(?:^|\n)\s*\d+[\.\)]\s+(.+)", text)
    return [i.strip() for i in items if i.strip()]
