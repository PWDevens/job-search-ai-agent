"""
Resume Coach Agent: actionable resume improvement recommendations.
"""
import logging
from app.agents.base import load_skill, chat, fmt_resume, fmt_jobs
from app.agents.models import ResumeRecList
from app.config import (TOP_RESUME_RECS, RESUME_FULL_CHARS, PROMPT_FEWSHOT,
                        GRAPH_RESUME_CONTEXT, AUTHORITATIVE_GAPS)

logger = logging.getLogger(__name__)


def run(resume_text: str, matched_jobs: list[dict], role_description: str = "",
        n: int = TOP_RESUME_RECS, extra_context: str | None = None) -> ResumeRecList:
    """Generate prioritized resume improvement recommendations."""
    # A1: show each target job's REQUIREMENTS (parsed section, from ingest), not just
    # "title at company" — so recommendations can close real gaps. Falls back to
    # title+company when a posting had no parseable requirements (e.g. truncated Adzuna).
    job_lines = []
    for i, j in enumerate(matched_jobs[:10], 1):
        head = f"{i}. {j.get('title', '')} at {j.get('company', '')}"
        req = (j.get("requirements_text") or "").strip().replace("\n", " ")
        job_lines.append(head + (f"\n   Requires: {req[:400]}" if req else ""))
    jobs_block = "Target job opportunities (with their requirements):\n" + "\n".join(job_lines)

    # A1: authoritative occupation requirements the resume lacks. Replaces the dead ESCO
    # GRAPH_RESUME_CONTEXT path (verbose labels that didn't match postings) with O*NET.
    skills_block = ""
    if (AUTHORITATIVE_GAPS or GRAPH_RESUME_CONTEXT) and (role_description or matched_jobs):
        try:
            from app.skills.onet_requirements import missing_requirements
            # A2: target occupation from the matched jobs' clean titles, not the role sentence.
            target = (matched_jobs[0].get("title") if matched_jobs else "") or role_description
            gaps = missing_requirements(target, resume_text, n=10)
            if gaps:
                skills_block = (
                    "\n\nAuthoritative requirements for the target occupation (US O*NET) missing "
                    "from this resume — prioritize adding any that are genuine gaps: " + ", ".join(gaps)
                )
        except Exception as e:
            logger.debug("resume-coach authoritative reqs unavailable: %s", e)

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
