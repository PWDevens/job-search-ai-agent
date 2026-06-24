"""
Regression tests for the eval-harness fixes (no fixtures, so they always run).

C1 — blind-spot scoring grounds on the extracted skill, not the rendered
     "[PRIORITY] skill: remediation" string (which never matched -> 0% grounding).
C2 — geo filter treats Remote as location-flexible instead of zeroing the job pool.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.persona_evaluation.evaluation_scoring import EvaluationRubric as R, _extract_skill
from app.pipeline.geolocation import location_matches as lm


# ── C1 ────────────────────────────────────────────────────────────────────────
JOBS = [{"description": "Seeking RN with Python and AWS cloud experience, ACLS required"}]

def test_c1_extract_skill_from_rendered():
    assert _extract_skill("[HIGH] Python: take a course") == "Python"
    assert _extract_skill("Python") == "Python"

def test_c1_blind_spot_grounds_on_skill():
    # the old bug: whole "[HIGH] Python: ..." string searched in desc -> 0 citations
    s = R.score_blind_spot("[HIGH] Python: take a 4-week course", JOBS)
    assert s.job_citations > 0, "skill present in a job description must ground"

def test_c1_multiword_skill_grounds_via_token():
    s = R.score_blind_spot("[CRITICAL] AWS Cloud Practitioner: get certified", JOBS)
    assert s.job_citations > 0, "distinctive token (aws/cloud) must ground"

def test_c1_nonsense_does_not_ground():
    s = R.score_blind_spot("[HIGH] Underwater Basket Weaving: n/a", JOBS)
    assert s.job_citations == 0


# ── C2 ────────────────────────────────────────────────────────────────────────
def test_c2_remote_pref_does_not_zero_city_jobs():
    assert lm("Chicago, Cook County", "Remote") is True
    assert lm("Washington DC", "Remote") is True

def test_c2_remote_job_matches_any_pref():
    assert lm("Remote", "Washington DC") is True

def test_c2_city_filtering_still_works():
    assert lm("Chicago IL", "Washington DC") is False
    assert lm("Washington, DC", "Washington DC") is True


# ── C3: majority-grounded gate ──────────────────────────────────────────────────
from app.pipeline.pipeline import _grounded_enough

def test_c3_majority_grounded_passes():
    jobs = [{"company": "Acme", "title": "X"}, {"company": "Globex", "title": "Y"}]
    # 2 of 3 grounded -> passes (old code required ALL grounded -> failed)
    ok, _ = _grounded_enough(["Acme", "Globex", "Initech"], jobs)
    assert ok is True

def test_c3_mostly_ungrounded_fails():
    jobs = [{"company": "Acme", "title": "X"}]
    ok, _ = _grounded_enough(["Foo", "Bar", "Acme"], jobs)
    assert ok is False

def test_c3_no_citations_is_not_a_hallucination():
    assert _grounded_enough([], [{"company": "Acme"}])[0] is True


# ── C4: de-gamed rec scoring (skills must be grounded in jobs) ───────────────────
def test_c4_skill_not_in_jobs_does_not_count():
    jobs = [{"company": "Acme", "description": "We need SQL and Tableau"}]
    grounded = R.score_recommendation("Add Python and Docker and Kubernetes to your resume", jobs)
    gamed    = R.score_recommendation("Add SQL and Tableau (skills Acme wants)", jobs)
    # naming skills the jobs DON'T want should not out-score grounded skills
    assert gamed.skill_mentions >= grounded.skill_mentions
    assert grounded.skill_mentions == 0  # python/docker/k8s absent from jobs

def test_c4_blind_spot_grounded_is_realistic():
    jobs = [{"description": "RN role requiring ACLS and patient assessment"}]
    s = R.score_blind_spot("[HIGH] ACLS: get certified", jobs)
    assert s.is_realistic is True and s.score >= 1


# ── C5: job 0-3 normalized to 0-4 in overall ────────────────────────────────────
def test_c5_job_scale_normalized():
    from tests.persona_evaluation.evaluation_scoring import ResultEvaluator
    class P: target_job_titles = ["data"]
    # perfect job match (score 3) should contribute as 4*0.3, not 3*0.3
    result = {"top_jobs": [{"title": "Data Engineer", "company": "Acme",
                            "description": "data", "score": 0.9}],
              "resume_recs": [], "blind_spots": []}
    out = ResultEvaluator.evaluate_search_result(result, P())
    # job=3 -> normalized 4 -> overall = 4*0.3 = 1.2 (was 3*0.3=0.9)
    assert out["overall_score"] > 1.1


# ── MJ3: grounded agent rationale lifts the job-match score ─────────────────────
def test_mj3_grounded_rationale_lifts_score():
    fields = ["data"]
    base_job = {"title": "Data Engineer", "company": "Acme",
                "description": "build python sql data pipelines on aws", "score": 0.8}
    plain = R.score_job_match(base_job, fields)
    with_why = R.score_job_match(
        {**base_job, "score": 0.7,
         "why_it_fits": "Your python and sql pipeline experience fits these aws data roles"},
        fields)
    assert with_why.score >= plain.score
    assert "grounded agent rationale" in with_why.reasoning


# ── MJ5: personas now carry native-field targets ────────────────────────────────
def test_mj5_native_field_targets_present():
    from tests.persona_evaluation.personas import get_persona_by_name
    nurse = get_persona_by_name("Nurse")
    elec = get_persona_by_name("Electrician")
    assert any("nurse" in t.lower() for t in nurse.target_job_titles)
    assert any("electric" in t.lower() for t in elec.target_job_titles)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
