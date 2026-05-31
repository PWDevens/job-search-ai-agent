"""
CrewAI custom tools.
Each tool wraps a core capability and exposes it to CrewAI agents via the @tool decorator.
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from crewai.tools import tool   # crewai >= 0.61; falls back to langchain_core.tools if needed

from app.config import TOP_BLIND_SPOTS, TOP_JOBS, TOP_RESUME_RECS

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Job-search tool
# ─────────────────────────────────────────────────────────────────────────────

class JobSearchTool:
    name        = "job_search"
    description = (
        "Search the local ChromaDB vector store for job postings that match a "
        "candidate's role description and geographic preference. "
        "Input: JSON string with keys 'role_description' (str), "
        "'geo_preference' (str, optional), 'resume_snippet' (str, optional), "
        "'n' (int, optional, default=25). "
        "Returns: JSON list of top matching jobs."
    )

    def _run(self, tool_input: str) -> str:
        from app.pipeline.matcher import find_top_jobs
        try:
            params = json.loads(tool_input) if tool_input.strip().startswith("{") else {
                "role_description": tool_input
            }
        except json.JSONDecodeError:
            params = {"role_description": tool_input}

        jobs = find_top_jobs(
            role_description=params.get("role_description", ""),
            geo_preference=params.get("geo_preference"),
            resume_text=params.get("resume_snippet"),
            n=int(params.get("n", TOP_JOBS)),
        )
        return json.dumps(jobs, indent=2)

    def run(self, tool_input: str) -> str:
        return self._run(tool_input)

    # Make it callable directly for newer CrewAI
    def __call__(self, tool_input: str) -> str:
        return self._run(tool_input)


# ─────────────────────────────────────────────────────────────────────────────
# Resume-match tool
# ─────────────────────────────────────────────────────────────────────────────

class ResumeMatchTool:
    name        = "resume_match"
    description = (
        "Find job postings that are closest to the candidate's existing resume. "
        "Input: JSON with 'role_description' (str) and 'resume_text' (str, optional). "
        "Returns: JSON list of top resume-relevant job postings."
    )

    def _run(self, tool_input: str) -> str:
        from app.pipeline.matcher import find_resume_recommendations
        try:
            params = json.loads(tool_input) if tool_input.strip().startswith("{") else {
                "role_description": tool_input
            }
        except json.JSONDecodeError:
            params = {"role_description": tool_input}

        recs = find_resume_recommendations(
            role_description=params.get("role_description", ""),
            resume_text=params.get("resume_text"),
            n=int(params.get("n", TOP_RESUME_RECS)),
        )
        return json.dumps(recs, indent=2)

    def run(self, tool_input: str) -> str:
        return self._run(tool_input)

    def __call__(self, tool_input: str) -> str:
        return self._run(tool_input)


# ─────────────────────────────────────────────────────────────────────────────
# Blind-spot tool
# ─────────────────────────────────────────────────────────────────────────────

class BlindSpotTool:
    name        = "blind_spot_analysis"
    description = (
        "Identify skills and keywords present in matched job postings but absent "
        "from the candidate's resume. "
        "Input: JSON with 'role_description' (str) and 'resume_text' (str, optional). "
        "Returns: JSON list of blind-spot terms."
    )

    def _run(self, tool_input: str) -> str:
        from app.pipeline.matcher import find_blind_spots
        try:
            params = json.loads(tool_input) if tool_input.strip().startswith("{") else {
                "role_description": tool_input
            }
        except json.JSONDecodeError:
            params = {"role_description": tool_input}

        spots = find_blind_spots(
            role_description=params.get("role_description", ""),
            resume_text=params.get("resume_text"),
            n=int(params.get("n", TOP_BLIND_SPOTS)),
        )
        return json.dumps(spots)

    def run(self, tool_input: str) -> str:
        return self._run(tool_input)

    def __call__(self, tool_input: str) -> str:
        return self._run(tool_input)


# ─────────────────────────────────────────────────────────────────────────────
# ATS Knowledge RAG tool
# ─────────────────────────────────────────────────────────────────────────────

class ATSKnowledgeTool:
    name        = "ats_knowledge"
    description = (
        "Query the ATS/HR/hiring best-practice knowledge base (RAG over curated "
        "guides about ATS parsers, resume optimisation, and AI hiring systems). "
        "Input: a plain-text question or topic, e.g. 'How do ATS systems parse skills?'. "
        "Returns: relevant excerpts and actionable guidance."
    )

    def _run(self, query: str) -> str:
        from app.agents.rag_knowledge import query_ats_knowledge
        results = query_ats_knowledge(query, n=4)
        if not results:
            return "No relevant ATS knowledge found for that query."
        return "\n\n---\n\n".join(results)

    def run(self, query: str) -> str:
        return self._run(query)

    def __call__(self, query: str) -> str:
        return self._run(query)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline writer tool
# ─────────────────────────────────────────────────────────────────────────────

class PipelineWriterTool:
    name        = "pipeline_writer"
    description = (
        "Append job match results to the job-pipeline Excel spreadsheet. "
        "Input: JSON list of job dicts (same format as job_search output). "
        "Returns: confirmation string with row count appended."
    )

    def _run(self, tool_input: str) -> str:
        from app.pipeline.excel_writer import append_jobs_to_pipeline
        try:
            jobs = json.loads(tool_input)
            if not isinstance(jobs, list):
                return "Error: expected a JSON list of jobs."
            count = append_jobs_to_pipeline(jobs)
            return f"Successfully appended {count} jobs to the pipeline spreadsheet."
        except Exception as exc:
            logger.exception("PipelineWriterTool error")
            return f"Error writing to pipeline: {exc}"

    def run(self, tool_input: str) -> str:
        return self._run(tool_input)

    def __call__(self, tool_input: str) -> str:
        return self._run(tool_input)
