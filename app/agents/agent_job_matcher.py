"""
Job Matcher Agent: semantic reranking and explanation of job matches.
"""
import logging
from app.agents.base import load_skill, chat
from app.agents.models import JobMatchList
from app.config import TOP_JOBS

logger = logging.getLogger(__name__)


def run(role_description: str, geo_preference: str, resume_text: str,
        jobs: list[dict], n: int = TOP_JOBS, extra_context: str | None = None) -> JobMatchList:
    """Reorder and explain top job matches.

    Args:
        role_description: target role/title
        geo_preference: preferred location(s)
        resume_text: candidate resume (truncated)
        jobs: list of dicts from matcher (find_top_jobs output)
        n: number of top results to return
        extra_context: optional corrective context for re-asks

    Returns:
        JobMatchList with ranked, explained matches
    """
    # Build candidate block
    resume_snippet = resume_text[:600] if resume_text else "(no resume)"
    geo_line = f"\nPreferred location: {geo_preference}" if geo_preference else ""

    candidate_block = f"""Candidate:
Role: {role_description}{geo_line}
Resume snippet: {resume_snippet}"""

    # Build context block: numbered list of jobs
    context_lines = []
    for i, job in enumerate(jobs[:25], 1):  # Limit context to 25 jobs
        title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        location = job.get("location", "N/A")
        salary = job.get("salary", "")
        url = job.get("url", "")
        doc = job.get("document", "")[:500]  # Truncate document

        salary_line = f" | Salary: {salary}" if salary else ""
        url_line = f" | URL: {url}" if url else ""
        doc_line = f" | Details: {doc}" if doc else ""

        context_lines.append(
            f"{i}. {title} at {company} ({location}){salary_line}{url_line}{doc_line}"
        )

    context_block = "Retrieved job listings:\n" + "\n".join(context_lines)

    # Build user message
    user_message = f"""{candidate_block}

{context_block}

Please select and reorder the top {n} jobs that best match this candidate.
For each, provide a brief explanation of why it fits."""

    # Append extra context if provided (re-ask with corrective grounding)
    if extra_context:
        user_message += f"\n\n{extra_context}"

    # Load skill and call agent
    system_prompt = load_skill("job_matcher")

    return chat(system_prompt, user_message, JobMatchList)
