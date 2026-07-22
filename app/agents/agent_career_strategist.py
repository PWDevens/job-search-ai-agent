"""
Career Strategist Agent: blind spot identification and career strategy.
Enhanced with ATS knowledge from RAG.
"""
import logging
import os
from app.agents.base import load_skill, chat, fmt_resume, fmt_jobs
from app.agents import intent
from app.agents.models import CareerStrategy
from app.agents.rag_knowledge import query_ats_knowledge
from app.config import TOP_BLIND_SPOTS, RESUME_MID_CHARS, PROMPT_FEWSHOT, AUTHORITATIVE_GAPS

logger = logging.getLogger(__name__)


def run(role_description: str, resume_text: str, matched_jobs: list[dict],
        resume_recs: list[str], n_blind: int = TOP_BLIND_SPOTS, extra_context: str | None = None,
        mode: str = "stay", stay_reason: str = "") -> CareerStrategy:
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

    # Authoritative gaps (iter5): the target occupation's REAL O*NET requirements missing from the
    # resume. Grounds blind spots in authoritative data, not in truncated postings. See onet_requirements.
    auth_gaps = []
    if AUTHORITATIVE_GAPS:
        try:
            from app.skills.onet_requirements import missing_requirements
            # A2: derive the TARGET occupation from the matched jobs' clean titles, NOT the
            # role_description sentence — for a switcher the sentence leads with the CURRENT
            # role ("home health aide ... seeking CNA"), which mis-injects current-role reqs.
            # Evidence depth ADOPTED (iter12 A/B, arm C): aggregate authoritative requirements across
            # the top-K matched occupations for a more complete gap set. +0.052 mean overall, positive
            # in BOTH realistic cells (+0.034 switch, +0.069 stay), biggest grounding lift (stay auth
            # 61.5->70.8), and FREE (no extra LLM). Default K=5; AGG_REQS=1 restores top-job-only.
            K = int(os.getenv("AGG_REQS", "5"))
            titles = [j.get("title", "") for j in matched_jobs[:K]] if matched_jobs else []
            titles = [t for t in titles if t] or [role_description]
            seen: list[str] = []
            for t in titles:
                for g in missing_requirements(t, resume_text, n=12):
                    if g.lower() not in {s.lower() for s in seen}:
                        seen.append(g)
            auth_gaps = seen[:12]
        except Exception as e:
            logger.debug("authoritative gaps unavailable: %s", e)
    auth_block = (
        "Authoritative requirements for this target occupation (US O*NET) that are MISSING from the "
        "resume — these are the highest-value, real gaps regardless of whether a (truncated) posting "
        "happens to mention them:\n" + ", ".join(auth_gaps) + "\n\n"
    ) if auth_gaps else ""

    # Causeways (switcher-pivot engine): adjacent occupations the candidate could realistically move
    # into, from O*NET relatedness. Switch mode only; gated CAUSEWAYS for A/B. See causeways.py.
    adj_block = ""
    if os.getenv("CAUSEWAYS", "").lower() in ("1", "true", "yes") and mode == "switch":
        try:
            from app.skills.causeways import adjacent_occupations
            adj = adjacent_occupations(role_description, k=4)
            if adj:
                adj_block = ("Adjacent occupations this candidate could realistically pivot into "
                             "(O*NET relatedness) — use these to ground the strategic recommendations "
                             "about where to aim:\n" + ", ".join(o["title"] for o in adj) + "\n\n")
        except Exception as e:
            logger.debug("causeways adjacency unavailable: %s", e)

    user_message = (
        f"Candidate Profile:\nRole: {role_description}\n"
        f"Resume: {fmt_resume(resume_text, RESUME_MID_CHARS)}\n\n"
        f"{jobs_block}\n\n"
        f"{auth_block}"
        f"{adj_block}"
        f"Resume improvements identified:\n{recs_summary}\n\n"
        f"{ats_block}\n\n"
        f"Please identify {n_blind} critical blind spots (skill gaps, missing experience, ATS blindspots) "
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
            f"and do NOT default to data/analytics skills unless the postings name them.\n"
        ))
        +
        f"For each: skill name, why it matters (cite 2-3 target roles), remediation path, "
        f"time-to-proficiency, and priority.\n"
        f"Then provide 3-4 strategic recommendations with evidence and concrete actions."
    )
    user_message += intent.note("career_strategist", mode, stay_reason)
    if extra_context:
        user_message += f"\n\n{extra_context}"

    if PROMPT_FEWSHOT:
        from app.agents.fewshot import FEWSHOT_CAREER_STRATEGIST
        user_message += "\n\nExamples of strong, grounded outputs:\n" + FEWSHOT_CAREER_STRATEGIST

    strategy = chat(load_skill("career_strategist"), user_message, CareerStrategy)

    # arm B (verification pass): a 2nd grounding-enforcement pass — drop blind spots NOT in the
    # authoritative requirements, add the highest-value missing ones. Deterministic, not a lottery.
    if os.getenv("VERIFY_PASS", "").lower() in ("1", "true", "yes") and auth_gaps:
        try:
            current = "; ".join(b.skill for b in strategy.blind_spots)
            verify_msg = (
                f"\n\nVERIFICATION PASS. The blind spots you produced were: {current}\n"
                f"The target occupation's REAL authoritative requirements are: {', '.join(auth_gaps)}\n"
                f"Return a CORRECTED list of exactly {n_blind} blind spots: drop any whose `skill` is NOT "
                f"among the authoritative requirements, and add the highest-value authoritative requirements "
                f"that are missing from the candidate's resume and not already listed. Same JSON schema."
            )
            strategy = chat(load_skill("career_strategist"), user_message + verify_msg, CareerStrategy)
        except Exception as e:
            logger.debug("verify pass skipped: %s", e)
    return strategy
