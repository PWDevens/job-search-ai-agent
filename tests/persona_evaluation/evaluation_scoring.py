"""
Quality evaluation and scoring logic for persona evaluation.
Implements the 0-4 scoring rubric for recommendations, blind spots, and job matches.
"""
from typing import List, Dict, Tuple, Any
import re
from dataclasses import dataclass
from app.config import RUBRIC_V2


def targets_for(persona: Any, variant: str = "switching") -> Tuple[List[str], List[str]]:
    """
    Return (target_job_titles, blind_spots) for a persona based on variant.

    variant="switching"   -> use analytics-pivot targets (default behavior)
    variant="stayinfield" -> use same-profession targets if available, else fall back

    ponytail: minimal helper to thread variant through scoring without duplicating scorer.
    """
    titles = getattr(persona, "target_job_titles", [])
    spots = getattr(persona, "expected_blind_spots", [])

    if variant == "stayinfield":
        # Use stay-in-field targets if available
        if hasattr(persona, 'stay_in_field_titles') and persona.stay_in_field_titles:
            titles = persona.stay_in_field_titles
        if hasattr(persona, 'stay_in_field_blind_spots') and persona.stay_in_field_blind_spots:
            spots = persona.stay_in_field_blind_spots

    return titles, spots


def _job_text(job: Dict[str, Any]) -> str:
    """Job body lives under 'document' (matcher) or 'description' (legacy/tests)."""
    return (job.get("document") or job.get("description") or "").lower()


def _skill_from_display(s: str) -> str:
    """Extract skill from a display string like '[HIGH] Python: add ...' -> 'Python'."""
    # Remove [PRIORITY] prefix if present
    s = re.sub(r'^\s*\[[^\]]*\]\s*', '', s)
    # Split on colon and take first part
    return s.split(':', 1)[0].strip()


def _rec_text(r: Dict[str, Any]) -> str:
    """Join grounded fields for company/skill citation visibility."""
    parts = [r.get("title", ""), r.get("fix", ""), r.get("why", ""), r.get("impact", "")]
    return " — ".join(p for p in parts if p).strip()


def _job_skill_ids(job: Dict[str, Any]) -> set:
    """Canonical skill IDs tagged on a job at ingest (comma-joined string in metadata)."""
    raw = job.get("skill_ids")
    if raw is None:
        raw = (job.get("metadata") or {}).get("skill_ids")
    return {s for s in (raw or "").split(",") if s}


def _id_citations(skill: str, top_jobs: List[Dict[str, Any]]):
    """skills: citations via canonical skill-ID match (robust to paraphrase).

    Returns None to signal 'fall back to substring' — when the skills layer isn't
    built, the skill isn't in the taxonomy, or the corpus carries no skill_ids
    (so nothing regresses on legacy/un-normalized data).
    """
    try:
        from app.skills.normalize import normalize_one
    except Exception:
        return None
    sid = normalize_one(skill)
    if not sid:
        return None
    job_sets = [_job_skill_ids(j) for j in top_jobs[:10]]
    if not any(job_sets):
        return None
    return sum(1 for s in job_sets if sid in s)


@dataclass
class RecommendationScore:
    """Score for a single recommendation"""
    text: str
    score: int  # 0-4
    reasoning: str
    is_tangible: bool
    company_citations: int
    skill_mentions: int


@dataclass
class BlindSpotScore:
    """Score for a single blind spot"""
    skill: str
    score: int  # 0-4
    reasoning: str
    is_realistic: bool
    job_citations: int
    has_learning_path: bool


@dataclass
class JobMatchScore:
    """Score for job match relevance"""
    title: str
    company: str
    score: int  # 0-3
    reasoning: str
    matches_persona_field: bool


class EvaluationRubric:
    """Quality scoring rubric for recommendations, blind spots, and job matches"""

    # Skill keywords for detection
    TECH_SKILLS = {
        "python", "sql", "r", "java", "javascript", "c++", "c#", "ruby", "go", "rust",
        "scala", "haskell", "kotlin", "swift", "typescript", "perl", "php", "bash",
        "machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow",
        "keras", "scikit-learn", "pandas", "numpy", "scipy", "matplotlib", "plotly",
        "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform",
        "spark", "hadoop", "kafka", "airflow", "dbt", "etl", "data warehouse",
        "snowflake", "bigquery", "redshift", "postgresql", "mysql", "mongodb", "cassandra",
        "tableau", "power bi", "looker", "grafana", "datadog", "elasticsearch",
        "git", "jenkins", "gitlab", "github", "jira", "confluence", "agile",
        "gis", "arcgis", "geospatial", "mapping", "shapefile",
    }

    SOFT_SKILLS = {
        "leadership", "communication", "teamwork", "collaboration", "mentoring",
        "project management", "stakeholder management", "strategic thinking",
    }

    @staticmethod
    def score_recommendation(text: str, top_jobs: List[Dict[str, Any]]) -> RecommendationScore:
        """Score a single resume recommendation (0-4 scale)"""

        if not text or len(text.strip()) < 10:
            return RecommendationScore(
                text=text,
                score=0,
                reasoning="Empty or too short",
                is_tangible=False,
                company_citations=0,
                skill_mentions=0,
            )

        # Extract companies from jobs
        job_companies = {job.get("company", "").lower() for job in top_jobs[:10] if job.get("company")}

        # Count company citations
        company_citations = sum(
            1 for company in job_companies
            if company.lower() in text.lower()
        )

        # Count specific skill mentions
        text_lower = text.lower()
        skill_mentions = sum(
            1 for skill in EvaluationRubric.TECH_SKILLS
            if skill in text_lower
        )

        # Detect if recommendation is tangible (specific tools, companies, etc.)
        tangibility_signals = [
            bool(re.search(r'\badd\b.*\b(python|sql|aws|docker|kubernetes)\b', text_lower)),
            bool(re.search(r'at\s+[a-z\s]+\(', text_lower)),  # "at Company (..."
            company_citations > 0,
            skill_mentions > 0,
            bool(re.search(r'\d+[\s-]*week|month|hour', text_lower)),  # Time estimates
            bool(re.search(r'\$[\d,]+|salary|compensation', text_lower)),  # $ mentions
        ]
        is_tangible = sum(tangibility_signals) >= 2

        # Generic phrases indicating poor quality
        generic_phrases = [
            "improve your resume",
            "add more details",
            "highlight your",
            "demonstrate your",
            "show your expertise",
            "be more specific",
        ]
        has_generic = any(phrase in text_lower for phrase in generic_phrases)

        # Scoring logic (0-4 scale)
        if has_generic and company_citations == 0:
            score = 0  # Poor: generic, no citations
            reasoning = "Generic advice with no job citations (0/4)"
        elif not is_tangible:
            score = 1  # Fair: weak grounding, vague
            reasoning = f"Weak specificity - {skill_mentions} skills mentioned, {company_citations} companies cited (1/4)"
        elif skill_mentions >= 2 and company_citations >= 1:
            score = 3  # Excellent: specific tools + companies cited
            reasoning = f"Specific with grounding - {skill_mentions} skills, {company_citations} companies, good reasoning (3/4)"
        elif skill_mentions >= 1 or company_citations >= 1:
            score = 2  # Good: some specificity
            reasoning = f"Moderately specific - {skill_mentions} skills, {company_citations} companies (2/4)"
        else:
            score = 1  # Fair
            reasoning = "Some tangibility but weak grounding (1/4)"

        return RecommendationScore(
            text=text,
            score=score,
            reasoning=reasoning,
            is_tangible=is_tangible,
            company_citations=company_citations,
            skill_mentions=skill_mentions,
        )

    @staticmethod
    def score_blind_spot(skill: str, top_jobs: List[Dict[str, Any]],
                         occ_reqs: set | None = None) -> BlindSpotScore:
        """Score a single blind spot (0-4 scale).

        rubric_v2 (R1): if `occ_reqs` (lowercased target-occupation O*NET requirements) is given and
        RUBRIC_V2 is on, a skill that is a real occupation requirement is grounded even when no
        (truncated) posting mentions it — bonus when it's BOTH a requirement and in a posting.
        """

        if not skill or len(skill.strip()) < 2:
            return BlindSpotScore(
                skill=skill,
                score=0,
                reasoning="Empty or invalid skill",
                is_realistic=False,
                job_citations=0,
                has_learning_path=False,
            )

        skill_lower = skill.lower()

        # skills: prefer canonical skill-ID grounding (robust to the prose/paraphrase
        # mismatch that kept Adzuna grounding low); fall back to substring when the
        # skills layer isn't built or the corpus isn't skill-tagged.
        job_citations = _id_citations(skill, top_jobs)
        if job_citations is None:
            job_citations = sum(
                1 for job in top_jobs[:10]
                if skill_lower in _job_text(job)
            )

        # Recognized in the known vocabulary (kept only as a fallback for plausible
        # but ungrounded skills — NOT a gate on grounded ones).
        in_vocab = (
            skill_lower in EvaluationRubric.TECH_SKILLS or
            skill_lower in EvaluationRubric.SOFT_SKILLS or
            any(keyword in skill_lower for keyword in ["learning", "data", "analytics", "design"])
        )
        # C4: a skill that literally appears in the matched jobs is real by definition.
        # The old tech-skill whitelist scored grounded trade/clinical/finance skills
        # (e.g. "ACLS", "conduit", "NEC") as 0 — penalizing correctly-grounded output.
        is_realistic = job_citations > 0 or in_vocab

        # Learning-path signal (the skill string rarely carries it; kept for the record,
        # not used to gate the score).
        has_learning_path = bool(
            re.search(r'course|tutorial|learn|free|udemy|coursera|certification|hours|weeks', skill_lower)
        )

        # C5: full 0-4 scale, grounding-driven. A blind spot grounded in even one real
        # posting is a genuine market gap and must outscore an ungrounded guess — on
        # diverse real (Adzuna) corpora most grounded skills hit exactly one job, so the
        # old "1 citation == 1 point" floor made real-data grounding invisible.
        if not is_realistic:
            score = 0  # made up: absent from every posting and unrecognized
            reasoning = f"'{skill}' not grounded in jobs and not a recognized skill (0/4)"
        elif job_citations == 0:
            score = 1  # plausible/recognized skill, but absent from these postings
            reasoning = "Recognized skill but not found in matched jobs (1/4)"
        elif job_citations >= 3:
            score = 4  # appears across many postings — a clear market-wide gap
            reasoning = f"Strong market-wide gap - {job_citations} job citations (4/4)"
        elif job_citations >= 2:
            score = 3  # grounded in multiple postings
            reasoning = f"Grounded in multiple jobs - {job_citations} citations (3/4)"
        else:  # exactly one citation
            score = 2  # grounded in a real posting
            reasoning = "Grounded in a matched job (2/4)"

        # rubric_v2 (R1): blend occupation-requirement grounding. A skill that is a real target-
        # occupation requirement is a genuine, high-value gap even if a truncated posting omits it.
        if RUBRIC_V2 and occ_reqs:
            auth_grounded = any(skill_lower in r or r in skill_lower for r in occ_reqs)
            if auth_grounded:
                is_realistic = True
                # auth-only -> 3 (authoritative gap); auth + posting -> 4 (demand-confirmed); never lowers.
                score = min(4, max(score, 3) + (1 if job_citations > 0 else 0))
                reasoning = (f"Occupation-grounded gap (O*NET)"
                             f"{' + posting demand' if job_citations > 0 else ''} ({score}/4)")

        return BlindSpotScore(
            skill=skill,
            score=score,
            reasoning=reasoning,
            is_realistic=is_realistic,
            job_citations=job_citations,
            has_learning_path=has_learning_path,
        )

    @staticmethod
    def score_job_match(job: Dict[str, Any], persona_fields: List[str]) -> JobMatchScore:
        """Score a job match for relevance to persona (0-3 scale)"""

        title = job.get("title", "")
        company = job.get("company", "")
        description = _job_text(job)
        score_val = job.get("score", 0) or 0  # matcher cosine similarity (1 = perfect)

        # MJ3: token-based field alignment. The old check tested whether a whole target
        # TITLE string ("Healthcare Data Analyst") appeared verbatim in the description —
        # almost never true, so field_match was ~always False and capped every job at 1.
        # Tokenize the titles and drop ultra-generic words so a match means "this job is
        # in the persona's field", not "contains the word data".
        generic = {"data", "senior", "junior", "manager", "analyst", "specialist",
                   "associate", "lead", "role", "experience", "engineer"}
        field_tokens = {w for f in persona_fields
                        for w in re.findall(r"[a-z]+", f.lower())
                        if len(w) > 3 and w not in generic}
        field_match = any(tok in description for tok in field_tokens)

        # MJ3: score on the matcher's REAL semantic relevance instead of gating on
        # field_match. Observed top-5 retrieval cosine range ~0.61-0.80; thresholds are
        # that distribution's quartiles (p25 0.67 / median 0.70 / p75 0.74) so the job
        # dimension actually differentiates retrieval quality instead of pinning at 1.0.
        if score_val >= 0.74:
            base = 3
        elif score_val >= 0.68:
            base = 2
        elif score_val >= 0.62:
            base = 1
        else:
            base = 0
        # Field alignment lifts a semantically-borderline job by one (capped at 3).
        score = min(3, base + 1) if (field_match and base < 3) else base
        reasoning = f"semantic={score_val:.2f}, field_match={field_match} ({score}/3)"

        return JobMatchScore(
            title=title,
            company=company,
            score=score,
            reasoning=reasoning,
            matches_persona_field=field_match,
        )


class ResultEvaluator:
    """Evaluate full search results against a persona"""

    @staticmethod
    def evaluate_search_result(
        result: Dict[str, Any],
        persona: Any,
        variant: str = "switching",
    ) -> Dict[str, Any]:
        """Comprehensive evaluation of search results for a persona.

        variant="switching" or "stayinfield" determines which targets to use for scoring.
        """

        top_jobs = result.get("top_jobs", [])
        resume_recs = result.get("resume_recs", [])
        blind_spots = result.get("blind_spots", [])

        # Use appropriate targets based on variant
        target_titles, _ = targets_for(persona, variant)

        # Score job matches
        job_scores = [
            EvaluationRubric.score_job_match(job, target_titles)
            for job in top_jobs[:5]
        ]

        # C1: Score structured fields from raw_agent_output, fall back to display strings
        raw = result.get("raw_agent_output", {}) or {}

        # Resume recommendations: prefer structured data
        strat = raw.get("career_strategy") or {}
        struct_spots = strat.get("blind_spots") or []
        spot_inputs = ([b.get("skill", "") for b in struct_spots]
                       if struct_spots else [_skill_from_display(s) for s in blind_spots])

        recs_raw = raw.get("resume_recs") or {}
        struct_recs = recs_raw.get("recommendations") or []
        rec_inputs = ([_rec_text(r) for r in struct_recs]
                      if struct_recs else list(resume_recs))

        # Score recommendations
        rec_scores = [
            EvaluationRubric.score_recommendation(t, top_jobs)
            for t in rec_inputs
        ]

        # Target-occupation requirements (O*NET) — used for both rubric_v2 grounding and the auth% metric.
        occ_reqs = set()
        try:
            from app.skills.onet_requirements import role_requirements
            for t in target_titles[:3]:
                occ_reqs.update(r.lower() for r in role_requirements(t, 25))
        except Exception:
            pass

        # Score blind spots
        spot_scores = [
            EvaluationRubric.score_blind_spot(skill, top_jobs, occ_reqs)
            for skill in spot_inputs
        ]

        # Calculate averages
        avg_job_score = sum(s.score for s in job_scores) / len(job_scores) if job_scores else 0
        avg_rec_score = sum(s.score for s in rec_scores) / len(rec_scores) if rec_scores else 0
        avg_spot_score = sum(s.score for s in spot_scores) / len(spot_scores) if spot_scores else 0

        # JTBD-aligned grounding (iter5): is each blind spot grounded in the TARGET OCCUPATION's
        # real O*NET requirements? Independent of how it was generated — measures advice quality
        # even when the (truncated) posting can't confirm it. None if the O*NET DB is unavailable.
        blind_spot_auth_grounded_pct = None
        if occ_reqs and spot_inputs:
            def _auth(sk):
                sk = (sk or "").lower().strip()
                return bool(sk) and any(sk in r or r in sk for r in occ_reqs)
            blind_spot_auth_grounded_pct = round(
                100.0 * sum(_auth(s) for s in spot_inputs) / len(spot_inputs), 1)

        # Overall quality score (0-4)
        overall_score = (
            avg_job_score * 0.3 +
            avg_rec_score * 0.4 +
            avg_spot_score * 0.3
        )

        # Quality label
        if overall_score >= 3.0:
            quality_label = "Excellent"
        elif overall_score >= 2.5:
            quality_label = "Good"
        elif overall_score >= 1.5:
            quality_label = "Fair"
        else:
            quality_label = "Poor"

        return {
            "job_scores": job_scores,
            "rec_scores": rec_scores,
            "spot_scores": spot_scores,
            "avg_job_score": avg_job_score,
            "avg_rec_score": avg_rec_score,
            "avg_spot_score": avg_spot_score,
            "overall_score": overall_score,
            "quality_label": quality_label,
            "blind_spot_auth_grounded_pct": blind_spot_auth_grounded_pct,
            "rubric_version": "v2" if RUBRIC_V2 else "v1",
        }


if __name__ == "__main__":
    # Test evaluation functions
    test_rec = "Add 'Python' and 'SQL' to Technical Skills. Senior Data Engineer at Accenture and Analytics Engineer at SAIC both require these."
    test_jobs = [
        {"company": "Accenture", "description": "Python SQL analytics"},
        {"company": "SAIC", "description": "Python machine learning"},
    ]

    score = EvaluationRubric.score_recommendation(test_rec, test_jobs)
    print(f"Recommendation score: {score.score}/4 - {score.reasoning}")

    spot_score = EvaluationRubric.score_blind_spot("Python", test_jobs)
    print(f"Blind spot score: {spot_score.score}/4 - {spot_score.reasoning}")
