"""
Job Matcher Agent: semantic reranking and explanation of job matches.
"""
import logging
from app.agents.base import load_skill, chat, fmt_resume, fmt_jobs
from app.agents.models import JobMatchList
from app.config import TOP_JOBS, RESUME_SNIPPET_CHARS, PROMPT_FEWSHOT

logger = logging.getLogger(__name__)


def run(role_description: str, geo_preference: str, resume_text: str,
        jobs: list[dict], n: int = TOP_JOBS, extra_context: str | None = None,
        mode: str = "stay") -> JobMatchList:
    """Reorder and explain top job matches."""
    geo_line = f"\nPreferred location: {geo_preference}" if geo_preference else ""
    candidate_block = (
        f"Candidate:\nRole: {role_description}{geo_line}\n"
        f"Resume snippet: {fmt_resume(resume_text, RESUME_SNIPPET_CHARS)}"
    )
    context_block = "Retrieved job listings:\n" + fmt_jobs(jobs, max_count=25, detail=True)

    user_message = (
        f"{candidate_block}\n\n{context_block}\n\n"
        f"Please select and reorder the top {n} jobs that best match this candidate.\n"
        f"For each, provide a brief explanation of why it fits."
    )
    if mode == "switch":
        user_message += (
            "\n\nNOTE: this candidate is CHANGING CAREERS into this field. Rank by TRANSFERABLE skills "
            "and growth potential, not by how many target-role requirements they already meet — a "
            "career-changer will be missing several. Favor roles their background plausibly bridges into."
        )
    if extra_context:
        user_message += f"\n\n{extra_context}"

    if PROMPT_FEWSHOT:
        from app.agents.fewshot import FEWSHOT_JOB_MATCHER
        user_message += "\n\nExamples of strong, grounded outputs:\n" + FEWSHOT_JOB_MATCHER

    return chat(load_skill("job_matcher"), user_message, JobMatchList)
