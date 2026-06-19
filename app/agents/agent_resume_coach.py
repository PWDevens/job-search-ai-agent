"""
Resume Coach Agent: actionable resume improvement recommendations.
"""
import logging
from app.agents.base import load_skill, chat
from app.agents.models import ResumeRecList
from app.config import TOP_RESUME_RECS

logger = logging.getLogger(__name__)


def run(resume_text: str, matched_jobs: list[dict],
        n: int = TOP_RESUME_RECS, extra_context: str | None = None) -> ResumeRecList:
    """Generate prioritized resume improvement recommendations.

    Args:
        resume_text: candidate resume (truncated to ~3000 chars)
        matched_jobs: final top_jobs dicts as grounding
        n: number of recommendations to return
        extra_context: optional corrective context for re-asks

    Returns:
        ResumeRecList with prioritized recommendations
    """
    # Truncate resume to fit context
    resume_snippet = resume_text[:3000] if resume_text else "(no resume)"

    # Build matched jobs context block
    jobs_context_lines = []
    for i, job in enumerate(matched_jobs[:10], 1):  # Show top 10 matched jobs
        title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        jobs_context_lines.append(f"{i}. {title} at {company}")

    jobs_context_block = "Target job opportunities:\n" + "\n".join(jobs_context_lines)

    # Build user message
    user_message = f"""Resume to review:
{resume_snippet}

{jobs_context_block}

Please provide {n} prioritized recommendations to strengthen this resume for these target roles.
For each recommendation, specify the priority (HIGH/MEDIUM/LOW), current state, fix, impact, and which role(s) it aligns with."""

    # Append extra context if provided (re-ask with corrective grounding)
    if extra_context:
        user_message += f"\n\n{extra_context}"

    # Load skill and call agent
    system_prompt = load_skill("resume_coach")

    return chat(system_prompt, user_message, ResumeRecList)
