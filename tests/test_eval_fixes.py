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


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
