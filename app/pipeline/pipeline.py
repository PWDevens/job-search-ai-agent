"""
Pipeline orchestrator: coordinates three agents with grounding checks and fallback.
Moved from app/agents/pipeline.py for cleaner module boundaries.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict

from app.agents.agent_job_matcher import run as run_job_matcher
from app.agents.agent_resume_coach import run as run_resume_coach
from app.agents.agent_career_strategist import run as run_career_strategist
from app.agents.grounding import check_grounding, extract_citations
from app.pipeline.matcher import find_top_jobs, find_resume_recommendations, find_blind_spots
from app.pipeline.audit import log_search_run
from app.retrieval.rerank import rerank
from app.config import RERANK_PASSES
import app.config as cfg

logger = logging.getLogger(__name__)


@dataclass
class SearchRequest:
    role_description: str
    geo_preference: str | None = None
    resume_text: str | None = None
    extra_context: str | None = None
    mode: str = "stay"   # "stay" (advance in field) | "switch" (career change) — alters context engineering
    stay_reason: str = ""  # when mode=stay: "advancement" | "comp_culture" | "displaced" | "" (lateral)
    effort: str = "balanced"  # "quick" | "balanced" | "thorough" | "max" — compute/thoroughness dial


@dataclass
class SearchResult:
    top_jobs: list[dict] = field(default_factory=list)
    resume_recs: list[str] = field(default_factory=list)
    blind_spots: list[str] = field(default_factory=list)
    raw_agent_output: Dict[str, Any] = field(default_factory=dict)
    agent_validation: Dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "top_jobs": self.top_jobs,
            "resume_recs": self.resume_recs,
            "blind_spots": self.blind_spots,
            "raw_agent_output": self.raw_agent_output,
            "agent_validation": self.agent_validation,
        }


def _run_with_grounding(run_fn, run_kwargs, get_citations, retrieved_jobs, agent_name,
                        best_of=1, select_fn=None):
    """Run agent, check grounding using ratio threshold. Returns (result, passed: bool).

    Always keeps the best result, never discards agent output.

    best_of>1: draw N samples (temp>0 for diversity). select_fn (arm A re-aim) scores each sample on
    a JTBD metric (e.g. occupation-grounding) and keeps the best — the iter11 A/B showed selecting on
    the citation grounding-ratio was the WRONG objective for the generative agents. Without select_fn,
    falls back to highest grounding ratio.
    """
    from app.config import GROUNDING_PASS_RATIO

    def _sample():
        r = run_fn(**run_kwargs)
        cited = get_citations(r)
        ung = check_grounding(cited, retrieved_jobs)
        return r, ((len(cited) - len(ung)) / len(cited) if cited else 1.0)

    if best_of and best_of > 1:
        samples = [_sample() for _ in range(best_of)]
        if select_fn is not None:
            best_result, best_ratio = max(samples, key=lambda s: (select_fn(s[0]), s[1]))  # JTBD metric, tie-break ratio
        else:
            best_result, best_ratio = max(samples, key=lambda s: s[1])  # highest grounding ratio
        return best_result, best_ratio >= GROUNDING_PASS_RATIO

    # Run agent once
    result = run_fn(**run_kwargs)
    cited = get_citations(result)
    ungrounded = check_grounding(cited, retrieved_jobs)

    # Compute grounding ratio
    total = len(cited)
    grounded = total - len(ungrounded)
    ratio = grounded / total if total else 1.0

    best_result = result
    best_ratio = ratio

    # If ratio passes, return immediately (no re-ask)
    if ratio >= GROUNDING_PASS_RATIO:
        logger.debug("%s grounding ratio %.1f%% >= %.1f%% (pass, no re-ask)",
                     agent_name, 100*ratio, 100*GROUNDING_PASS_RATIO)
        return best_result, True

    # Else attempt re-ask
    logger.warning("%s grounding ratio %.1f%% < %.1f%% — re-asking once",
                   agent_name, 100*ratio, 100*GROUNDING_PASS_RATIO)
    available = sorted(set(j["company"] for j in retrieved_jobs[:10]))
    reask = (
        f"Your response cited companies not in the retrieved jobs: {ungrounded}.\n"
        f"Use ONLY companies from this list: {available}"
    )
    reask_result = run_fn(**{**run_kwargs, "extra_context": reask})
    reask_cited = get_citations(reask_result)
    reask_ungrounded = check_grounding(reask_cited, retrieved_jobs)

    # Compute ratio for re-asked result
    reask_total = len(reask_cited)
    reask_grounded = reask_total - len(reask_ungrounded)
    reask_ratio = reask_grounded / reask_total if reask_total else 1.0

    # Keep whichever has the higher ratio
    if reask_ratio > best_ratio:
        best_result = reask_result
        best_ratio = reask_ratio
        logger.debug("%s re-ask improved ratio to %.1f%%", agent_name, 100*reask_ratio)
    else:
        logger.debug("%s keeping original result (ratio %.1f%% >= re-ask %.1f%%)",
                     agent_name, 100*best_ratio, 100*reask_ratio)

    # Return best result; passed=True only if best_ratio meets threshold
    passed = best_ratio >= GROUNDING_PASS_RATIO
    if not passed:
        logger.warning("%s best ratio %.1f%% still below threshold; output will be scored but validation=False",
                       agent_name, 100*best_ratio)

    return best_result, passed


def run(req: SearchRequest) -> SearchResult:
    """Orchestrate the three-agent pipeline.

    Pass 1 rerank: inside find_top_jobs (role description query).
    Pass 2 rerank: after job_matcher, reorders top_jobs with role+resume signal.
    Pass 3 rerank: after resume_coach, reorders recs by resume relevance (if RERANK_PASSES >= 3).

    On any agent failure: log warning, set agent_validation=False, fall back to matcher.
    """
    result = SearchResult()
    result.agent_validation = {"job_matcher": False, "resume_coach": False, "career_strategist": False}

    # Effort dial (#2): bundle the compute levers. temp>0 enables best-of-N diversity.
    eb = cfg.effort_bundle(req.effort)
    cfg.OLLAMA_TEMPERATURE = eb["temp"]   # per-request; next run() re-derives (pipeline is sequential)
    rerank_passes = eb["rerank_passes"]

    # Step 1: Matcher (ground truth; Pass 1 rerank happens inside find_top_jobs)
    try:
        search_query = req.role_description
        logger.info("Finding top jobs for: %s", req.role_description)
        jobs = find_top_jobs(search_query, req.geo_preference, req.resume_text,
                             n=eb["top_jobs"], fetch=eb["fetch"])
        result.top_jobs = jobs
        logger.info("Matcher returned %d jobs", len(jobs))
    except Exception as e:
        logger.error("Matcher failed: %s", e)
        return result

    # Step 2: Job matcher agent
    try:
        logger.info("Running job_matcher agent...")
        job_matches, passed = _run_with_grounding(
            run_job_matcher,
            dict(role_description=req.role_description, geo_preference=req.geo_preference or "",
                 resume_text=req.resume_text or "", jobs=jobs, mode=req.mode, stay_reason=req.stay_reason),
            lambda r: [m.company for m in r.matches],
            jobs, "job_matcher", best_of=eb["best_of"],
        )
        result.agent_validation["job_matcher"] = passed
        result.raw_agent_output["job_matches"] = job_matches.model_dump()

        # Merge agent explanations back onto original matcher dicts
        merged = []
        for match in job_matches.matches:
            for orig in jobs:
                ot = orig.get("title", "").lower()
                mt = match.title.lower()
                if (ot == mt or ot in mt or mt in ot) and \
                   orig.get("company", "").lower() == match.company.lower():
                    merged.append({**orig, "why_it_fits": match.why_it_fits, "agent_rank": match.rank})
                    break
            else:
                logger.warning("Could not match agent output '%s @ %s' to matcher results",
                               match.title, match.company)
        result.top_jobs = merged

        # Pass 2: rerank with combined role+resume signal so coach+strategist see best order
        if rerank_passes >= 2 and result.top_jobs:
            p2_query = req.role_description + (" " + req.resume_text[:400] if req.resume_text else "")
            result.top_jobs = rerank(p2_query, result.top_jobs, top_n=len(result.top_jobs))
            logger.info("Pass 2 rerank: reordered %d jobs (role+resume query)", len(result.top_jobs))

    except Exception as e:
        logger.warning("Job matcher agent failed: %s — falling back to matcher", e)
        result.agent_validation["job_matcher"] = False

    # Re-aimed best-of-N (arm A): when sampling, score generative samples by OCCUPATION-grounding
    # (the JTBD metric), not the citation ratio. occ_reqs = the target occupation's requirements,
    # aggregated across the top-K matched jobs (arm C: AGG_REQS=K).
    occ_reqs: set = set()
    if eb["best_of"] > 1:
        try:
            from app.skills.onet_requirements import role_requirements
            K = int(os.getenv("AGG_REQS", "1"))
            titles = [j.get("title", "") for j in result.top_jobs[:K]] or [req.role_description]
            for t in titles:
                occ_reqs.update(r.lower() for r in role_requirements(t, 20))
        except Exception as e:
            logger.debug("occ_reqs for re-aim unavailable: %s", e)

    def _occ_score(items):
        return sum(1 for x in items if any((x.lower() in r or r in x.lower()) for r in occ_reqs))

    coach_select = (lambda rr: _occ_score([f"{x.title} {x.fix}" for x in rr.recommendations])) if occ_reqs else None
    strat_select = (lambda s: _occ_score([b.skill for b in s.blind_spots])) if occ_reqs else None

    # Step 3: Resume coach agent
    try:
        logger.info("Running resume_coach agent...")
        resume_recs, passed = _run_with_grounding(
            run_resume_coach,
            dict(resume_text=req.resume_text or "", matched_jobs=result.top_jobs,
                 role_description=req.role_description, mode=req.mode, stay_reason=req.stay_reason),
            lambda r: extract_citations(r.recommendations, "why"),
            result.top_jobs, "resume_coach", best_of=eb["best_of"], select_fn=coach_select,
        )
        result.agent_validation["resume_coach"] = passed
        result.raw_agent_output["resume_recs"] = resume_recs.model_dump()
        # display string only; scoring reads raw_agent_output (see evaluation_scoring)
        result.resume_recs = [f"[{r.priority}] {r.title} — {r.fix}" for r in resume_recs.recommendations]

        # Pass 3: rerank resume recs by relevance to the full resume text
        if rerank_passes >= 3 and req.resume_text and result.resume_recs:
            wrapped = [{"document": r} for r in result.resume_recs]
            reranked = rerank(req.resume_text, wrapped, top_n=len(wrapped))
            result.resume_recs = [r["document"] for r in reranked]
            logger.info("Pass 3 rerank: reordered %d resume recs (resume query)", len(result.resume_recs))

    except Exception as e:
        logger.warning("Resume coach agent failed: %s — falling back to matcher", e)
        result.agent_validation["resume_coach"] = False
        fallback = find_resume_recommendations(req.role_description, resume_text=req.resume_text or None)
        result.resume_recs = [f"{r['title']} at {r['company']}" for r in fallback]

    # Step 4: Career strategist agent
    try:
        logger.info("Running career_strategist agent...")
        strategy, passed = _run_with_grounding(
            run_career_strategist,
            dict(role_description=req.role_description, resume_text=req.resume_text or "",
                 matched_jobs=result.top_jobs, resume_recs=result.resume_recs, mode=req.mode, stay_reason=req.stay_reason),
            lambda r: extract_citations(r.blind_spots, "why") + extract_citations(r.strategy, "evidence"),
            result.top_jobs, "career_strategist", best_of=eb["best_of"], select_fn=strat_select,
        )
        result.agent_validation["career_strategist"] = passed
        result.raw_agent_output["career_strategy"] = strategy.model_dump()
        # display string only; scoring reads raw_agent_output (see evaluation_scoring)
        result.blind_spots = [f"[{b.priority}] {b.skill}: {b.remediation}" for b in strategy.blind_spots]

    except Exception as e:
        logger.warning("Career strategist agent failed: %s — falling back to matcher", e)
        result.agent_validation["career_strategist"] = False
        result.blind_spots = find_blind_spots(req.role_description, resume_text=req.resume_text or None)

    # Audit log
    try:
        log_search_run(
            req.role_description, req.geo_preference or "", req.resume_text or "",
            result.top_jobs, result.resume_recs, result.blind_spots,
            {k: json.dumps(v) if isinstance(v, dict) else v for k, v in result.raw_agent_output.items()},
            result.agent_validation,
        )
    except Exception as e:
        logger.error("Audit log failed: %s", e)

    return result
