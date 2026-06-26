"""
Career Strategist Agent: blind spot identification and career strategy.
Enhanced with ATS knowledge from RAG.
"""
import logging
from app.agents.base import load_skill, chat, fmt_resume, fmt_jobs
from app.agents.models import CareerStrategy
from app.agents.rag_knowledge import query_ats_knowledge
from app.config import (TOP_BLIND_SPOTS, RESUME_MID_CHARS, PROMPT_FEWSHOT,
                        STRATEGIST_USE_OCCUPATION_SKILLS, GRAPH_PROMPT_CONTEXT)

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

    # detail=True so the strategist actually SEES each posting's skills/keywords —
    # without it the agent only got "Title at Company" and could not ground blind spots.
    jobs_block  = ("Target opportunities (read the required skills/keywords in each):\n"
                   + fmt_jobs(matched_jobs, max_count=8, detail=True))
    recs_summary = "\n".join(resume_recs[:5]) if resume_recs else "(no resume recs)"

    # skills: optional candidate pool from the ESCO occupation graph. OFF by default
    # — an A/B showed ESCO's verbose competence labels HURT grounding on real postings
    # (see config.STRATEGIST_USE_OCCUPATION_SKILLS). Enable only with a posting-style
    # vocabulary whose labels match how postings actually name skills.
    essential, adjacent = [], []
    if STRATEGIST_USE_OCCUPATION_SKILLS or GRAPH_PROMPT_CONTEXT:
        try:
            from app.skills.graph import role_skill_context
            essential, adjacent = role_skill_context(role_description, n_essential=12, n_adjacent=8)
        except Exception as e:
            logger.debug("occupation-skill lookup unavailable: %s", e)
    essential_block = (
        "Essential skills for this target role (occupation taxonomy):\n"
        + ", ".join(essential)
        + (("\nRelated skills: " + ", ".join(adjacent)) if adjacent else "")
        + "\n\n"
    ) if essential else ""

    user_message = (
        f"Candidate Profile:\nRole: {role_description}\n"
        f"Resume: {fmt_resume(resume_text, RESUME_MID_CHARS)}\n\n"
        f"{jobs_block}\n\n"
        f"{essential_block}"
        f"Resume improvements identified:\n{recs_summary}\n\n"
        f"{ats_block}\n\n"
        f"Please identify {n_blind} critical blind spots (skill gaps, missing experience, ATS blindspots) "
        f"that limit this candidate's competitiveness.\n"
        f"GROUNDING RULE (critical): each blind spot's `skill` MUST be a specific term that literally "
        f"appears in the Target opportunity descriptions above — copy a tool, certification, technology, "
        f"or named skill exactly as written in the postings. Do NOT list a skill the postings don't mention, "
        f"and do NOT default to data/analytics skills unless the postings name them. "
        f"Prefer skills that are BOTH in the postings AND in the Essential-skills list above (when provided) "
        f"and are missing from the resume — those are the highest-value, best-grounded gaps.\n"
        f"For each: skill name, why it matters (cite 2-3 target roles), remediation path, "
        f"time-to-proficiency, and priority.\n"
        f"Then provide 3-4 strategic recommendations with evidence and concrete actions."
    )
    if extra_context:
        user_message += f"\n\n{extra_context}"

    if PROMPT_FEWSHOT:
        from app.agents.fewshot import FEWSHOT_CAREER_STRATEGIST
        user_message += "\n\nExamples of strong, grounded outputs:\n" + FEWSHOT_CAREER_STRATEGIST

    return chat(load_skill("career_strategist"), user_message, CareerStrategy)
