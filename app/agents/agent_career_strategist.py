"""
Career Strategist Agent: blind spot identification and career strategy.
Enhanced with ATS knowledge from RAG.
"""
import logging
from app.agents.base import load_skill, chat, fmt_resume, fmt_jobs
from app.agents.models import CareerStrategy
from app.agents.rag_knowledge import query_ats_knowledge
from app.config import TOP_BLIND_SPOTS, RESUME_MID_CHARS

logger = logging.getLogger(__name__)


def run(role_description: str, resume_text: str, matched_jobs: list[dict],
        resume_recs: list[str], n_blind: int = TOP_BLIND_SPOTS, extra_context: str | None = None) -> CareerStrategy:
    """Identify blind spots and generate career strategy."""
    try:
        ats_knowledge = query_ats_knowledge(role_description, n=4)
        ats_block = f"ATS best practices for {role_description}:\n{ats_knowledge}"
    except Exception as e:
        logger.warning("Failed to retrieve ATS knowledge: %s", e)
        ats_block = "(ATS knowledge unavailable)"

    jobs_block  = "Target opportunities:\n" + fmt_jobs(matched_jobs, max_count=8)
    recs_summary = "\n".join(resume_recs[:5]) if resume_recs else "(no resume recs)"

    user_message = (
        f"Candidate Profile:\nRole: {role_description}\n"
        f"Resume: {fmt_resume(resume_text, RESUME_MID_CHARS)}\n\n"
        f"{jobs_block}\n\n"
        f"Resume improvements identified:\n{recs_summary}\n\n"
        f"{ats_block}\n\n"
        f"Please identify {n_blind} critical blind spots (skill gaps, missing experience, ATS blindspots) "
        f"that limit this candidate's competitiveness.\n"
        f"For each: skill name, why it matters (cite 2-3 target roles), remediation path, "
        f"time-to-proficiency, and priority.\n"
        f"Then provide 3-4 strategic recommendations with evidence and concrete actions."
    )
    if extra_context:
        user_message += f"\n\n{extra_context}"

    return chat(load_skill("career_strategist"), user_message, CareerStrategy)
