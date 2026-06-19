"""
Career Strategist Agent: blind spot identification and career strategy.
Enhanced with ATS knowledge from RAG.
"""
import logging
from app.agents.base import load_skill, chat
from app.agents.models import CareerStrategy
from app.agents.rag_knowledge import query_ats_knowledge
from app.config import TOP_BLIND_SPOTS

logger = logging.getLogger(__name__)


def run(role_description: str, resume_text: str, matched_jobs: list[dict],
        resume_recs: list[str], n_blind: int = TOP_BLIND_SPOTS, extra_context: str | None = None) -> CareerStrategy:
    """Identify blind spots and generate career strategy.

    Args:
        role_description: target role/title
        resume_text: candidate resume
        matched_jobs: final top_jobs dicts as grounding
        resume_recs: rendered resume recommendations (list[str])
        n_blind: number of blind spots to identify
        extra_context: optional corrective context for re-asks

    Returns:
        CareerStrategy with blind_spots and strategy recommendations
    """
    # Truncate resume
    resume_snippet = resume_text[:1500] if resume_text else "(no resume)"

    # Retrieve ATS knowledge
    try:
        ats_knowledge = query_ats_knowledge(role_description, n=4)
        ats_block = f"ATS/Applicant Tracking System best practices for {role_description}:\n{ats_knowledge}"
    except Exception as e:
        logger.warning(f"Failed to retrieve ATS knowledge: {e}")
        ats_block = "(ATS knowledge unavailable)"

    # Build matched jobs context
    jobs_context_lines = []
    for i, job in enumerate(matched_jobs[:8], 1):
        title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        jobs_context_lines.append(f"{i}. {title} at {company}")

    jobs_context_block = "Target opportunities:\n" + "\n".join(jobs_context_lines)

    # Build resume recs summary
    recs_summary = "\n".join(resume_recs[:5]) if resume_recs else "(no resume recs)"

    # Build user message
    user_message = f"""Candidate Profile:
Role: {role_description}
Resume: {resume_snippet}

{jobs_context_block}

Resume improvements identified:
{recs_summary}

{ats_block}

Please identify {n_blind} critical blind spots (skill gaps, missing experience, ATS/process blindspots) that limit this candidate's competitiveness.
For each, include: skill name, why it matters (cite 2-3 target roles), remediation path, time-to-proficiency, and priority.
Then provide 3-4 strategic recommendations with evidence and concrete actions."""

    # Append extra context if provided (re-ask with corrective grounding)
    if extra_context:
        user_message += f"\n\n{extra_context}"

    # Load skill and call agent
    system_prompt = load_skill("career_strategist")

    return chat(system_prompt, user_message, CareerStrategy)
