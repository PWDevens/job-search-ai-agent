#!/usr/bin/env python3
"""
Self-check tests for C1/C2/C3 spec implementations.

Run with: python -m pytest tests/test_spec_fixes.py -v
  or:     python tests/test_spec_fixes.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.pipeline.geolocation import location_matches, _city_state
from tests.persona_evaluation.evaluation_scoring import (
    _job_text, _skill_from_display, _rec_text, EvaluationRubric
)


def test_c1_job_text_document_key():
    """C1: _job_text reads 'document' key (not 'description')."""
    job = {"document": "Python SQL analytics skills required"}
    assert "python" in _job_text(job)
    print("[PASS] C1 _job_text reads document key")


def test_c1_job_text_fallback_description():
    """C1: _job_text falls back to 'description' if 'document' missing."""
    job = {"description": "Python SQL analytics skills"}
    assert "python" in _job_text(job)
    print("[PASS] C1 _job_text falls back to description key")


def test_c1_skill_from_display():
    """C1: _skill_from_display tolerates missing [priority] and colon."""
    # With brackets and colon
    s1 = "[HIGH] Python: add to resume"
    assert _skill_from_display(s1) == "Python"

    # Without bracket
    s2 = "Python: add to resume"
    assert _skill_from_display(s2) == "Python"

    # Without colon
    s3 = "[HIGH] Python"
    assert _skill_from_display(s3) == "Python"

    # Just the skill
    s4 = "Python"
    assert _skill_from_display(s4) == "Python"

    print("[PASS] C1 _skill_from_display tolerates missing brackets/colons")


def test_c1_rec_text():
    """C1: _rec_text joins structured fields for citation visibility."""
    rec = {
        "title": "Add Python",
        "fix": "Take DataCamp course",
        "why": "Data Engineer at Accenture",
        "impact": "Opens mid-level roles",
    }
    text = _rec_text(rec)
    assert "Python" in text and "Accenture" in text
    print("[PASS] C1 _rec_text joins fields for grounding")


def test_c1_blind_spot_scoring():
    """C1: score_blind_spot uses _job_text and finds real citations."""
    job = {"company": "Accenture", "document": "python sql machine learning"}
    score = EvaluationRubric.score_blind_spot("python", [job])
    assert score.job_citations > 0, "Should find 'python' in document"
    assert score.score >= 1, "Should score >= 1 with citation"
    print("[PASS] C1 blind_spot_scoring uses _job_text and counts citations")


def test_c1_recommendation_scoring():
    """C1: score_recommendation scores joined rec fields."""
    jobs = [{"company": "Accenture", "document": "python sql"}]
    rec_text = "Add Python — at Accenture — for analytics"
    score = EvaluationRubric.score_recommendation(rec_text, jobs)
    assert score.company_citations > 0, "Should find Accenture citation"
    print("[PASS] C1 recommendation_scoring finds company citations")


def test_c4_grounded_nontech_skill_scores():
    """C4: a grounded non-tech skill (not in the tech whitelist) must score, not 0.

    'ACLS' is not in TECH_SKILLS/SOFT_SKILLS; under the old is_realistic gate it
    scored 0 even when present in the matched jobs. Now grounding => real => scores.
    """
    nursing_jobs = [
        {"company": "Mercy", "document": "registered nurse with acls certification and epic ehr"},
        {"company": "Kaiser", "document": "charge nurse, acls required, bls preferred"},
    ]
    s = EvaluationRubric.score_blind_spot("acls", nursing_jobs)
    assert s.job_citations >= 2, f"ACLS should be cited in both jobs, got {s.job_citations}"
    assert s.is_realistic, "Grounded skill must be treated as realistic (C4)"
    assert s.score >= 3, f"Grounded-in-2 non-tech skill should score >=3, got {s.score}"
    # An invented skill absent from postings still scores 0.
    bogus = EvaluationRubric.score_blind_spot("quantum welding telepathy", nursing_jobs)
    assert bogus.score == 0, "Ungrounded, unrecognized skill must score 0"
    print("[PASS] C4/C5 grounded non-tech skill scores; invented skill scores 0")


def test_mj3_job_score_reflects_semantic_relevance():
    """MJ3: job score uses the matcher's real cosine score, not the broken whole-title
    gate that capped every job at 1."""
    fields = ["Charge Nurse", "ICU Nurse"]
    strong = {"title": "ICU Charge Nurse", "company": "Mercy",
              "document": "icu charge nurse, acls", "score": 0.78}
    weak = {"title": "Barista", "company": "Cafe", "document": "make coffee", "score": 0.55}
    s_strong = EvaluationRubric.score_job_match(strong, fields)
    s_weak = EvaluationRubric.score_job_match(weak, fields)
    assert s_strong.score == 3, f"strong+field job should score 3, got {s_strong.score}"
    assert s_weak.score == 0, f"low-relevance off-field job should score 0, got {s_weak.score}"
    # A relevant retrieved job with NO title-token match still scores on semantics (not capped at 1).
    semantic_only = {"title": "Clinical Care Coordinator", "company": "X",
                     "document": "patient care unit", "score": 0.72}
    assert EvaluationRubric.score_job_match(semantic_only, fields).score >= 2, \
        "semantically strong job must not be pinned at 1 without a title-token match"
    print("[PASS] MJ3 job score reflects semantic relevance, not the whole-title gate")


def test_c5_grounding_drives_full_scale():
    """C5: grounding drives the 0-4 scale; 1 citation beats 0, 3+ reaches 4."""
    one = [{"company": "A", "document": "needs conduit bending"}]
    three = [{"company": "A", "document": "conduit"}, {"company": "B", "document": "conduit work"},
             {"company": "C", "document": "conduit bending"}]
    s1 = EvaluationRubric.score_blind_spot("conduit", one)
    s3 = EvaluationRubric.score_blind_spot("conduit", three)
    assert s1.score == 2, f"1 citation should score 2, got {s1.score}"
    assert s3.score == 4, f"3 citations should score 4, got {s3.score}"
    print("[PASS] C5 grounding drives full 0-4 scale (1->2, 3+->4)")


def test_c2_city_state_extraction():
    """C2: _city_state extracts city and state from normalized location."""
    city, state = _city_state("Chicago, IL")
    assert city == "chicago" and state == "il"
    print("[PASS] C2 _city_state extracts tokens correctly")


def test_c2_remote_matches_all():
    """C2 Rule 3: User prefers Remote → match all jobs (nationwide)."""
    assert location_matches("Chicago, IL", "Remote") is True
    assert location_matches("New York, NY", "Remote") is True
    assert location_matches("Remote", "Remote") is True
    print("[PASS] C2 Remote user matches all jobs (nationwide)")


def test_c2_remote_job_matches_specific_city():
    """C2 Rule 4: Remote job matches user's specific city preference."""
    assert location_matches("Remote", "Chicago, IL") is True
    assert location_matches("Fully Remote", "San Francisco, CA") is True
    print("[PASS] C2 Remote job matches any city preference")


def test_c2_city_token_overlap():
    """C2 Rule 5: Relaxed city/state match via token overlap."""
    # City overlap
    assert location_matches("Chicago, Cook County", "Chicago, IL") is True
    # State match
    assert location_matches("Austin, TX", "Dallas, TX") is True
    print("[PASS] C2 City token/state overlap matching works")


def test_c2_exact_match():
    """C2 Rule 2: Exact normalized match."""
    assert location_matches("New York, NY", "New York, NY") is True
    assert location_matches("NYC", "New York, NY") is True
    print("[PASS] C2 Exact normalized match works")


def test_n1_blank_location_no_false_match():
    """N1: a blank/missing job location must NOT match a specific-city preference."""
    assert location_matches("", "Chicago, IL") is False
    assert location_matches("", "San Francisco, CA") is False
    # Rule 1 unaffected: no user preference still accepts a blank location.
    assert location_matches("", "") is True
    print("[PASS] N1 blank job location does not false-match a city preference")


def test_c3_grounding_ratio():
    """C3: GROUNDING_PASS_RATIO is configured."""
    from app.config import GROUNDING_PASS_RATIO
    assert 0 <= GROUNDING_PASS_RATIO <= 1
    assert GROUNDING_PASS_RATIO == 0.5  # [DEFAULT]
    print(f"[PASS] C3 GROUNDING_PASS_RATIO configured: {GROUNDING_PASS_RATIO}")


def test_config_constants():
    """Verify all new config constants are present."""
    from app.config import GROUNDING_PASS_RATIO, RETRIEVAL_BOOST, PROMPT_FEWSHOT, RERANK_MODEL
    assert GROUNDING_PASS_RATIO == 0.5
    assert RETRIEVAL_BOOST is False
    assert PROMPT_FEWSHOT is False  # opt-in (iter4: gain within measurement noise)
    assert RERANK_MODEL == "bge-reranker-v2-m3"
    print("[PASS] All config constants present with correct defaults")


def test_fewshot_constants():
    """Verify few-shot exemplars are defined."""
    from app.agents.fewshot import (
        FEWSHOT_RESUME_COACH, FEWSHOT_CAREER_STRATEGIST, FEWSHOT_JOB_MATCHER
    )
    assert len(FEWSHOT_RESUME_COACH) > 100
    assert len(FEWSHOT_CAREER_STRATEGIST) > 100
    assert len(FEWSHOT_JOB_MATCHER) > 100
    print("[PASS] Few-shot exemplars defined")


if __name__ == "__main__":
    print("Running C1/C2/C3 spec implementation checks...\n")
    tests = [
        test_c1_job_text_document_key,
        test_c1_job_text_fallback_description,
        test_c1_skill_from_display,
        test_c1_rec_text,
        test_c1_blind_spot_scoring,
        test_c1_recommendation_scoring,
        test_c4_grounded_nontech_skill_scores,
        test_mj3_job_score_reflects_semantic_relevance,
        test_c5_grounding_drives_full_scale,
        test_c2_city_state_extraction,
        test_c2_remote_matches_all,
        test_c2_remote_job_matches_specific_city,
        test_c2_city_token_overlap,
        test_c2_exact_match,
        test_n1_blank_location_no_false_match,
        test_c3_grounding_ratio,
        test_config_constants,
        test_fewshot_constants,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


