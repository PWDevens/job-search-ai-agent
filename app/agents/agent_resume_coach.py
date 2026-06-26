"""
Resume Coach Agent: actionable resume improvement recommendations.
"""
import logging
from app.agents.base import load_skill, chat, fmt_resume, fmt_jobs
from app.agents.models import ResumeRecList
from app.config import TOP_RESUME_RECS, RESUME_FULL_CHARS, PROMPT_FEWSHOT, GRAPH_RESUME_CONTEXT

logger = logging.getLogger(__name__)


def run(resume_text: str, matched_jobs: list[dict], role_description: str = "",
        n: int = TOP_RESUME_RECS, extra_context: str | None = None) -> ResumeRecList:
    """Generate prioritized resume improvement recommendations."""
    jobs_block = "Target job opportunities:\n" + fmt_jobs(matched_jobs, max_count=10)

    # graph context (A/B): occupation-essential + adjacent skills the resume may lack.
    skills_block = ""
    if GRAPH_RESUME_CONTEXT and role_description:
        try:
            from app.skills.graph import role_skill_context
            ess, adj = role_skill_context(role_description, n_essential=12, n_adjacent=8)
            if ess:
                skills_block = (
                    f"\n\nSkills commonly expected for a {role_description} (occupation taxonomy) "
                    f"— recommend adding any the resume lacks: {', '.join(ess + adj)}"
                )
        except Exception as e:
            logger.debug("resume-coach graph context unavailable: %s", e)

    user_message = (
        f"Resume to review:\n{fmt_resume(resume_text, RESUME_FULL_CHARS)}\n\n"
        f"{jobs_block}{skills_block}\n\n"
        f"Please provide {n} prioritized recommendations to strengthen this resume for these target roles.\n"
        f"For each recommendation, specify the priority (HIGH/MEDIUM/LOW), current state, fix, impact, "
        f"and which role(s) it aligns with."
    )
    if extra_context:
        user_message += f"\n\n{extra_context}"

    if PROMPT_FEWSHOT:
        from app.agents.fewshot import FEWSHOT_RESUME_COACH
        user_message += "\n\nExamples of strong, grounded outputs:\n" + FEWSHOT_RESUME_COACH

    return chat(load_skill("resume_coach"), user_message, ResumeRecList)
