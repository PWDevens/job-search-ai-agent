"""
Quality evaluation and scoring logic for persona evaluation.
Implements the 0-4 scoring rubric for recommendations, blind spots, and job matches.
"""
from typing import List, Dict, Tuple, Any
import re
from dataclasses import dataclass


def _extract_skill(text: str) -> str:
    """Pull the skill phrase out of a rendered blind spot.

    The pipeline renders blind spots as "[PRIORITY] skill: remediation". Scoring
    must match on the skill ("Python"), not the whole string — otherwise nothing
    grounds. Accepts already-clean skills too.
    """
    if not text:
        return ""
    s = re.sub(r"^\s*\[[^\]]*\]\s*", "", text)   # strip "[HIGH] "
    s = s.split(":", 1)[0]                         # drop "...: remediation"
    return s.strip()


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

        # Count GROUNDED skill mentions: a recognized skill that appears in BOTH the
        # recommendation AND a retrieved job description. This de-games the rubric —
        # naming skills the market doesn't actually want no longer earns points.
        text_lower = text.lower()
        job_text = " ".join(j.get("description", "").lower() for j in top_jobs[:10])
        skill_mentions = sum(
            1 for skill in EvaluationRubric.TECH_SKILLS
            if skill in text_lower and skill in job_text
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
    def score_blind_spot(skill: str, top_jobs: List[Dict[str, Any]]) -> BlindSpotScore:
        """Score a single blind spot (0-4 scale)"""

        if not skill or len(skill.strip()) < 2:
            return BlindSpotScore(
                skill=skill,
                score=0,
                reasoning="Empty or invalid skill",
                is_realistic=False,
                job_citations=0,
                has_learning_path=False,
            )

        # Extract the actual skill phrase from "[PRIORITY] skill: remediation"
        # so we match THAT against jobs, not the whole rendered string.
        skill_clean = _extract_skill(skill)
        skill_lower = skill_clean.lower()

        # Ground at word level: a multi-word skill ("AWS Cloud Practitioner")
        # counts if the phrase OR a distinctive token appears in a job description.
        _GENERIC = {"the", "and", "for", "with", "your", "skills", "skill",
                    "experience", "knowledge", "ability", "strong", "certification"}
        tokens = [t for t in re.split(r"[^a-z0-9+#.]+", skill_lower)
                  if len(t) > 2 and t not in _GENERIC]
        job_citations = sum(
            1 for job in top_jobs[:10]
            if (desc := job.get("description", "").lower())
            and (skill_lower in desc or any(t in desc for t in tokens))
        )

        # Real/recognized skill — OR grounded in the actual job market. A skill that
        # appears in retrieved postings IS a real market skill by definition (works
        # cross-industry: nursing/trades/finance, not just the tech vocabulary).
        is_realistic = (
            job_citations > 0 or
            skill_lower in EvaluationRubric.TECH_SKILLS or
            skill_lower in EvaluationRubric.SOFT_SKILLS or
            any(keyword in skill_lower for keyword in ["learning", "data", "analytics", "design"])
        )

        # Check for learning path indicators (course, time, resource mention)
        has_learning_path = bool(
            re.search(r'course|tutorial|learn|free|udemy|coursera|certification|hours|weeks', skill_lower)
        )

        # Scoring logic (0-4 scale)
        if not is_realistic:
            score = 0  # Poor: not a real skill
            reasoning = f"'{skill}' not recognized as real skill (0/4)"
        elif job_citations == 0:
            score = 1  # Fair: real skill, no job relevance
            reasoning = f"Real skill but not found in top jobs (1/4)"
        elif job_citations >= 3 and has_learning_path:
            score = 3  # Excellent: realistic + cited + has learning path
            reasoning = f"Strong blind spot - {job_citations} job citations, learning path provided (3/4)"
        elif job_citations >= 2:
            score = 2  # Good: cited in multiple jobs
            reasoning = f"Good blind spot - {job_citations} job citations (2/4)"
        else:
            score = 1  # Fair: minimal job relevance
            reasoning = f"Minimal job relevance - {job_citations} citations (1/4)"

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
        description = job.get("description", "").lower()
        score_val = job.get("score", 0)

        # Check if job matches persona's target fields
        field_match = any(field in description for field in persona_fields)

        # Check for experience level alignment
        experience_level = ""
        if "senior" in title.lower() or "lead" in title.lower() or "manager" in title.lower():
            experience_level = "senior"
        elif "junior" in title.lower() or "associate" in title.lower():
            experience_level = "junior"
        else:
            experience_level = "mid"

        # Scoring (0-3 scale)
        if not field_match and score_val < 0.5:
            score = 0  # Not relevant
            reasoning = f"Not relevant to persona field ({score_val:.2f} semantic match)"
        elif not field_match and score_val < 0.7:
            score = 1  # Tangential match
            reasoning = f"Tangentially relevant, weak semantic match ({score_val:.2f})"
        elif field_match and score_val >= 0.75:
            score = 3  # Excellent match
            reasoning = f"Strong match - field aligned, semantic match {score_val:.2f}"
        elif field_match:
            score = 2  # Good match
            reasoning = f"Good match - field aligned, semantic match {score_val:.2f}"
        else:
            score = 1  # Fair
            reasoning = f"Fair match, experience level: {experience_level}"

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
    ) -> Dict[str, Any]:
        """Comprehensive evaluation of search results for a persona"""

        top_jobs = result.get("top_jobs", [])
        resume_recs = result.get("resume_recs", [])
        blind_spots = result.get("blind_spots", [])

        # Score job matches
        job_scores = [
            EvaluationRubric.score_job_match(job, persona.target_job_titles)
            for job in top_jobs[:5]
        ]

        # Score recommendations
        rec_scores = [
            EvaluationRubric.score_recommendation(rec, top_jobs)
            for rec in resume_recs
        ]

        # Score blind spots
        spot_scores = [
            EvaluationRubric.score_blind_spot(spot, top_jobs)
            for spot in blind_spots
        ]

        # Calculate averages
        avg_job_score = sum(s.score for s in job_scores) / len(job_scores) if job_scores else 0
        avg_rec_score = sum(s.score for s in rec_scores) / len(rec_scores) if rec_scores else 0
        avg_spot_score = sum(s.score for s in spot_scores) / len(spot_scores) if spot_scores else 0

        # Overall quality score (0-4). Job match is a 0-3 rubric while rec/spot are
        # 0-4, so normalize job to the 0-4 scale before weighting — otherwise the
        # job dimension is structurally under-weighted (max 3 vs 4).
        job_norm = avg_job_score * (4.0 / 3.0)
        overall_score = (
            job_norm * 0.3 +
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
