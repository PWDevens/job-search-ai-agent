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

logger = logging.getLogger(__name__)


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
    top_jobs:       List[Dict[str, Any]] = field(default_factory=list)
    resume_recs:    List[str]            = field(default_factory=list)
    blind_spots:    List[str]            = field(default_factory=list)
    raw_agent_output: Dict[str, str]     = field(default_factory=dict)


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
            "Output a numbered list with: Rank, Title, Company, Location, "
            "Match Score (0–1), Salary, URL, and a one-sentence reason for the match. "
            "Then append the results to the job pipeline spreadsheet."
        ),
        expected_output=(
            f"Numbered list of top {TOP_JOBS} jobs with all required fields, "
            "followed by confirmation that the pipeline spreadsheet was updated."
        ),
        agent=job_matcher,
    )

    task_resume = Task(
        description=(
            f"Using the job matches as context, produce exactly {TOP_RESUME_RECS} "
            "specific, prioritised resume improvement recommendations for the candidate.\n\n"
            f"{ctx}\n\n"
            "Each recommendation must: name the exact change (e.g., 'Add a Skills section "
            "with Python, SQL, LLMs'), explain why it matters for ATS and humans, and "
            "reference at least one of the matched job postings."
        ),
        expected_output=(
            f"Numbered list of {TOP_RESUME_RECS} specific, actionable resume "
            "recommendations grounded in the job data."
        ),
        agent=resume_coach,
        context=[task_match],
    )

    task_blind = Task(
        description=(
            f"Identify the top {TOP_BLIND_SPOTS} blind spots — skills, credentials, or "
            "experience signals present in the top matched jobs but absent from the "
            "candidate's resume.\n\n"
            f"{ctx}\n\n"
            "For each blind spot: name the gap, explain why employers value it, "
            "give a free/low-cost way to close it (course, project, certification), "
            "and estimate how long it would take. Use ATS best-practice knowledge where relevant."
        ),
        expected_output=(
            f"Numbered list of top {TOP_BLIND_SPOTS} blind spots with actionable "
            "closure plans."
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
    Orchestrate the three-agent pipeline and return structured results.
    This is called by both the Flask UI and the weekly scheduler.
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

    crew_output = crew.kickoff(inputs={
        "top_jobs":  TOP_JOBS,
        "top_recs":  TOP_RESUME_RECS,
        "top_blind": TOP_BLIND_SPOTS,
    })

    # Parse structured output from raw agent text
    result = SearchResult()
    result.raw_agent_output = {
        "job_matches":      str(task_match.output   or ""),
        "resume_recs":      str(task_resume.output  or ""),
        "blind_spots":      str(task_blind.output   or ""),
    }

    # Hydrate structured fields from the matching tool (ground truth)
    from app.pipeline.matcher import find_top_jobs, find_resume_recommendations, find_blind_spots
    result.top_jobs    = find_top_jobs(req.role_description, req.geo_preference, req.resume_text)
    result.resume_recs = _extract_numbered_list(result.raw_agent_output["resume_recs"])
    result.blind_spots = _extract_numbered_list(result.raw_agent_output["blind_spots"])
    if not result.blind_spots:
        result.blind_spots = find_blind_spots(req.role_description, req.resume_text)

    logger.info("Pipeline complete — jobs:%d  recs:%d  blind_spots:%d",
                len(result.top_jobs), len(result.resume_recs), len(result.blind_spots))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_numbered_list(text: str) -> List[str]:
    """Pull numbered-list items from an agent's free-text output."""
    import re
    items = re.findall(r"(?:^|\n)\s*\d+[\.\)]\s+(.+)", text)
    return [i.strip() for i in items if i.strip()]
