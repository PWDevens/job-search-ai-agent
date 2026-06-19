"""
Pipeline orchestrator: replaces crew.py
Coordinates three agents with grounding checks and fallback to matcher.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict

from app.agents.agent_job_matcher import run as run_job_matcher
from app.agents.agent_resume_coach import run as run_resume_coach
from app.agents.agent_career_strategist import run as run_career_strategist
from app.agents.grounding import check_grounding, extract_citations
from app.pipeline.matcher import find_top_jobs, find_resume_recommendations, find_blind_spots
from app.pipeline.audit import log_search_run

logger = logging.getLogger(__name__)


@dataclass
class SearchRequest:
    """User search request."""
    role_description: str
    geo_preference: str | None = None
    resume_text: str | None = None
    extra_context: str | None = None


@dataclass
class SearchResult:
    """Pipeline result: same shape as old crew.SearchResult."""
    top_jobs: list[dict] = field(default_factory=list)
    resume_recs: list[str] = field(default_factory=list)
    blind_spots: list[str] = field(default_factory=list)
    raw_agent_output: Dict[str, Any] = field(default_factory=dict)
    agent_validation: Dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Convert to dict for template compatibility."""
        return {
            "top_jobs": self.top_jobs,
            "resume_recs": self.resume_recs,
            "blind_spots": self.blind_spots,
            "raw_agent_output": self.raw_agent_output,
            "agent_validation": self.agent_validation,
        }


def run(req: SearchRequest) -> SearchResult:
    """Orchestrate the three-agent pipeline.

    Steps:
    1. Matcher retrieves top jobs (ground truth)
    2. Job matcher agent reorders + explains
    3. Resume coach agent recommends improvements
    4. Career strategist agent identifies blind spots + strategy
    5. Grounding check + single re-ask per agent
    6. Audit log
    7. Return SearchResult

    On ANY agent failure: log warning, set agent_validation[agent]=False, fall back to matcher.
    """
    result = SearchResult()
    result.agent_validation = {
        "job_matcher": False,
        "resume_coach": False,
        "career_strategist": False,
    }

    try:
        # Step 1: Matcher is ground truth
        logger.info(f"Finding top jobs for: {req.role_description}")
        jobs = find_top_jobs(
            req.role_description,
            req.geo_preference,
            req.resume_text
        )
        result.top_jobs = jobs
        logger.info(f"Matcher returned {len(jobs)} jobs")

    except Exception as e:
        logger.error(f"Matcher failed: {e}")
        return result

    # Step 2: Job matcher agent
    try:
        logger.info("Running job_matcher agent...")
        job_matches = run_job_matcher(
            req.role_description,
            req.geo_preference or "",
            req.resume_text or "",
            jobs
        )

        # Grounding check for job_matcher
        ungrounded = check_grounding(
            [m.company for m in job_matches.matches],
            jobs
        )
        if ungrounded:
            logger.warning(f"Job matcher has ungrounded companies: {ungrounded}. Re-asking once...")
            # Re-ask once with ungrounded citations appended
            try:
                retrieved_companies = sorted(set(j['company'] for j in jobs[:10]))
                reask_user_msg = (
                    f"Your previous response cited companies not in the retrieved jobs: {ungrounded}.\n\n"
                    f"Available companies in the job market: {retrieved_companies}\n\n"
                    f"Please provide your top {len(job_matches.matches)} job recommendations using ONLY companies from the retrieved list."
                )
                logger.debug(f"Re-asking job_matcher with ungrounded context")
                job_matches = run_job_matcher(
                    req.role_description,
                    req.geo_preference or "",
                    req.resume_text or "",
                    jobs,
                    extra_context=reask_user_msg
                )
                # Check again after re-ask
                ungrounded_after = check_grounding(
                    [m.company for m in job_matches.matches],
                    jobs
                )
                if ungrounded_after:
                    logger.warning(f"Job matcher still has ungrounded companies after re-ask: {ungrounded_after}. Flagging.")
                    result.agent_validation["job_matcher"] = False
                else:
                    result.agent_validation["job_matcher"] = True
            except Exception as e:
                logger.error(f"Re-ask failed for job_matcher: {e}")
                result.agent_validation["job_matcher"] = False
        else:
            result.agent_validation["job_matcher"] = True

        result.raw_agent_output["job_matches"] = job_matches.model_dump()

        # Merge agent output back onto matcher dicts
        merged_top_jobs = []
        for match in job_matches.matches:
            # Find corresponding job in matcher output (case-insensitive match)
            found = False
            for original_job in jobs:
                orig_title = original_job.get("title", "").lower()
                match_title = match.title.lower()
                title_ok = (
                    orig_title == match_title
                    or orig_title in match_title
                    or match_title in orig_title
                )
                company_ok = (
                    original_job.get("company", "").lower() == match.company.lower()
                )
                if title_ok and company_ok:
                    # Enrich with agent explanation
                    enriched = dict(original_job)
                    enriched["why_it_fits"] = match.why_it_fits
                    enriched["agent_rank"] = match.rank
                    merged_top_jobs.append(enriched)
                    found = True
                    break
            if not found:
                # Fallback: create a minimal dict with agent data
                logger.warning(
                    f"Could not match agent output {match.title} @ {match.company} "
                    f"back to matcher results"
                )
        result.top_jobs = merged_top_jobs

    except Exception as e:
        logger.warning(f"Job matcher agent failed: {e}. Falling back to matcher.")
        result.agent_validation["job_matcher"] = False
        # top_jobs already populated from matcher

    # Step 3: Resume coach agent
    try:
        logger.info("Running resume_coach agent...")
        resume_recs = run_resume_coach(req.resume_text or "", result.top_jobs)

        # Grounding check for resume_coach (check 'why' field for citations)
        cited_companies = extract_citations(resume_recs.recommendations, "why")
        ungrounded = check_grounding(cited_companies, result.top_jobs)
        if ungrounded:
            logger.warning(f"Resume coach has ungrounded companies in 'why' field: {ungrounded}. Re-asking once...")
            try:
                retrieved_companies = sorted(set(j['company'] for j in result.top_jobs[:10]))
                reask_user_msg = (
                    f"Your previous response cited companies not in the target jobs: {ungrounded}.\n\n"
                    f"Target companies: {retrieved_companies}\n\n"
                    f"Please provide your recommendations again, citing only from the target job list."
                )
                logger.debug("Re-asking resume_coach with grounding context")
                resume_recs = run_resume_coach(req.resume_text or "", result.top_jobs, extra_context=reask_user_msg)
                # Check again after re-ask
                cited_companies_after = extract_citations(resume_recs.recommendations, "why")
                ungrounded_after = check_grounding(cited_companies_after, result.top_jobs)
                if ungrounded_after:
                    logger.warning(f"Resume coach still has ungrounded citations after re-ask: {ungrounded_after}. Flagging.")
                    result.agent_validation["resume_coach"] = False
                else:
                    result.agent_validation["resume_coach"] = True
            except Exception as e:
                logger.error(f"Re-ask failed for resume_coach: {e}")
                result.agent_validation["resume_coach"] = False
        else:
            result.agent_validation["resume_coach"] = True

        result.raw_agent_output["resume_recs"] = resume_recs.model_dump()

        # Render to list[str]
        rendered_recs = [
            f"[{r.priority}] {r.title} — {r.fix}"
            for r in resume_recs.recommendations
        ]
        result.resume_recs = rendered_recs

    except Exception as e:
        logger.warning(f"Resume coach agent failed: {e}. Falling back to matcher.")
        result.agent_validation["resume_coach"] = False
        # Fallback to matcher
        fallback_recs = find_resume_recommendations(
            req.role_description,
            resume_text=req.resume_text or None,
        )
        result.resume_recs = [f"{r['title']} at {r['company']}" for r in fallback_recs]

    # Step 4: Career strategist agent
    try:
        logger.info("Running career_strategist agent...")
        strategy = run_career_strategist(
            req.role_description,
            req.resume_text or "",
            result.top_jobs,
            result.resume_recs
        )

        # Grounding check for career_strategist (check both blind_spots and strategy 'why'/'evidence')
        blind_spot_citations = extract_citations(strategy.blind_spots, "why")
        strategy_citations = extract_citations(strategy.strategy, "evidence")
        all_citations = blind_spot_citations + strategy_citations
        ungrounded = check_grounding(all_citations, result.top_jobs)

        if ungrounded:
            logger.warning(f"Career strategist has ungrounded citations: {ungrounded}. Re-asking once...")
            try:
                retrieved_companies = sorted(set(j['company'] for j in result.top_jobs[:10]))
                reask_user_msg = (
                    f"Your previous response cited companies not in the target jobs: {ungrounded}.\n\n"
                    f"Target companies: {retrieved_companies}\n\n"
                    f"Please provide your blind spots and strategy again, citing only from the target jobs."
                )
                logger.debug("Re-asking career_strategist with grounding context")
                strategy = run_career_strategist(
                    req.role_description,
                    req.resume_text or "",
                    result.top_jobs,
                    result.resume_recs,
                    extra_context=reask_user_msg
                )
                # Check again after re-ask
                blind_spot_citations_after = extract_citations(strategy.blind_spots, "why")
                strategy_citations_after = extract_citations(strategy.strategy, "evidence")
                all_citations_after = blind_spot_citations_after + strategy_citations_after
                ungrounded_after = check_grounding(all_citations_after, result.top_jobs)
                if ungrounded_after:
                    logger.warning(f"Career strategist still has ungrounded citations after re-ask: {ungrounded_after}. Flagging.")
                    result.agent_validation["career_strategist"] = False
                else:
                    result.agent_validation["career_strategist"] = True
            except Exception as e:
                logger.error(f"Re-ask failed for career_strategist: {e}")
                result.agent_validation["career_strategist"] = False
        else:
            result.agent_validation["career_strategist"] = True

        result.raw_agent_output["career_strategy"] = strategy.model_dump()

        # Render blind spots to list[str]
        rendered_spots = [
            f"[{b.priority}] {b.skill}: {b.remediation}"
            for b in strategy.blind_spots
        ]
        result.blind_spots = rendered_spots

    except Exception as e:
        logger.warning(f"Career strategist agent failed: {e}. Falling back to matcher.")
        result.agent_validation["career_strategist"] = False
        # Fallback to matcher
        fallback_spots = find_blind_spots(req.role_description, resume_text=req.resume_text or None)
        result.blind_spots = fallback_spots

    # Step 7: Audit log
    try:
        log_search_run(
            req.role_description,
            req.geo_preference or "",
            req.resume_text or "",
            result.top_jobs,
            result.resume_recs,
            result.blind_spots,
            {k: json.dumps(v) if isinstance(v, dict) else v for k, v in result.raw_agent_output.items()},
            result.agent_validation
        )
    except Exception as e:
        logger.error(f"Audit log failed: {e}")

    return result
