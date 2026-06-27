"""
Career Strategist Agent: blind spot identification and career strategy.
Enhanced with ATS knowledge from RAG.
"""
import logging
from app.agents.base import load_skill, chat, fmt_resume, fmt_jobs
from app.agents.models import CareerStrategy
from app.agents.rag_knowledge import query_ats_knowledge
from app.config import (TOP_BLIND_SPOTS, RESUME_MID_CHARS, PROMPT_FEWSHOT,
                        STRATEGIST_USE_OCCUPATION_SKILLS, GRAPH_PROMPT_CONTEXT, GRAPH_VALIDATE,
                        AUTHORITATIVE_GAPS)

logger = logging.getLogger(__name__)


def run(role_description: str, resume_text: str, matched_jobs: list[dict],
        resume_recs: list[str], n_blind: int = TOP_BLIND_SPOTS, extra_context: str | None = None,
        mode: str = "stay") -> CareerStrategy:
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

    # occupation-graph skills, used two independent ways:
    #  - prompt injection (STRATEGIST_USE_OCCUPATION_SKILLS / GRAPH_PROMPT_CONTEXT) — A/B-shown to HURT.
    #  - post-hoc validation (GRAPH_VALIDATE) — over-generate then cross-encoder-select; never touches the prompt.
    inject = STRATEGIST_USE_OCCUPATION_SKILLS or GRAPH_PROMPT_CONTEXT
    essential, adjacent = [], []
    if inject or GRAPH_VALIDATE:
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
    ) if (essential and inject) else ""

    # Authoritative gaps (iter5): the target occupation's REAL O*NET requirements missing from the
    # resume. Grounds blind spots in authoritative data, not in truncated postings. See onet_requirements.
    auth_gaps = []
    if AUTHORITATIVE_GAPS:
        try:
            from app.skills.onet_requirements import missing_requirements
            # A2: derive the TARGET occupation from the matched jobs' clean titles, NOT the
            # role_description sentence — for a switcher the sentence leads with the CURRENT
            # role ("home health aide ... seeking CNA"), which mis-injects current-role reqs.
            target = (matched_jobs[0].get("title") if matched_jobs else "") or role_description
            auth_gaps = missing_requirements(target, resume_text, n=12)
        except Exception as e:
            logger.debug("authoritative gaps unavailable: %s", e)
    auth_block = (
        "Authoritative requirements for this target occupation (US O*NET) that are MISSING from the "
        "resume — these are the highest-value, real gaps regardless of whether a (truncated) posting "
        "happens to mention them:\n" + ", ".join(auth_gaps) + "\n\n"
    ) if auth_gaps else ""

    # validate over-generates so there's a pool to select the most occupation-relevant from.
    gen_n = n_blind + 3 if (GRAPH_VALIDATE and essential) else n_blind

    user_message = (
        f"Candidate Profile:\nRole: {role_description}\n"
        f"Resume: {fmt_resume(resume_text, RESUME_MID_CHARS)}\n\n"
        f"{jobs_block}\n\n"
        f"{essential_block}"
        f"{auth_block}"
        f"Resume improvements identified:\n{recs_summary}\n\n"
        f"{ats_block}\n\n"
        f"Please identify {gen_n} critical blind spots (skill gaps, missing experience, ATS blindspots) "
        f"that limit this candidate's competitiveness.\n"
        + ((
            f"GROUNDING RULE (critical): each blind spot's `skill` MUST come from the Authoritative "
            f"requirements list above — copy a tool/technology exactly as written. These are the target "
            f"occupation's real requirements; cite which target roles need them. Do NOT invent skills "
            f"outside that list, and do NOT default to generic data/analytics skills.\n"
        ) if auth_gaps else (
            f"GROUNDING RULE (critical): each blind spot's `skill` MUST be a specific term that literally "
            f"appears in the Target opportunity descriptions above — copy a tool, certification, technology, "
            f"or named skill exactly as written in the postings. Do NOT list a skill the postings don't mention, "
            f"and do NOT default to data/analytics skills unless the postings name them. "
            f"Prefer skills that are BOTH in the postings AND in the Essential-skills list above (when provided) "
            f"and are missing from the resume — those are the highest-value, best-grounded gaps.\n"
        ))
        +
        f"For each: skill name, why it matters (cite 2-3 target roles), remediation path, "
        f"time-to-proficiency, and priority.\n"
        f"Then provide 3-4 strategic recommendations with evidence and concrete actions."
    )
    if mode == "switch":
        user_message += (
            "\n\nNOTE: this candidate is CHANGING CAREERS into the target field. Produce a constructive "
            "TRANSITION ROADMAP, not a deficiency list: lead with their transferable strengths, then for each "
            "gap give the bridge (course/cert/project) and a realistic time-to-proficiency."
        )
    if extra_context:
        user_message += f"\n\n{extra_context}"

    if PROMPT_FEWSHOT:
        from app.agents.fewshot import FEWSHOT_CAREER_STRATEGIST
        user_message += "\n\nExamples of strong, grounded outputs:\n" + FEWSHOT_CAREER_STRATEGIST

    strategy = chat(load_skill("career_strategist"), user_message, CareerStrategy)

    # Graph validate (A/B): keep the n_blind blind spots most semantically relevant to the
    # occupation's essential skills (cross-encoder) — graph as a post-hoc filter, not a prompt.
    if GRAPH_VALIDATE and essential and len(strategy.blind_spots) > n_blind:
        try:
            from app.retrieval.rerank import rerank
            docs = [{"id": str(i), "document": bs.skill} for i, bs in enumerate(strategy.blind_spots)]
            ranked = rerank(", ".join(essential), docs, top_n=n_blind)
            strategy.blind_spots = [strategy.blind_spots[int(d["id"])] for d in ranked]
        except Exception as e:
            logger.debug("graph validate skipped: %s", e)
            strategy.blind_spots = strategy.blind_spots[:n_blind]
    return strategy
