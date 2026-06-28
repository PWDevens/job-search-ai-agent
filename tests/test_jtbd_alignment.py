"""
JTBD-alignment behavioral tests (iter6-8). Guards the alignment work so it can't
silently regress: section parsing (A0), occupation matching (A2), authoritative
requirements (A1/C5), rubric_v2 + B5 scoring, and mode-aware agent context.

These are behavioral, not mechanical — each asserts a property the JTBD depends on
("blind spots are occupation-grounded", "career-changers get switch framing").
"""
from app.pipeline.sections import requirements_text, responsibilities_text
from app.skills.onet_requirements import occupation_for, role_requirements, MIN_CONF
from tests.persona_evaluation.evaluation_scoring import EvaluationRubric as R


def test_section_parser_targets_requirements():
    """A0: requirements section is extracted and kept separate from responsibilities."""
    posting = ("Acme is hiring a widget maker.\n\n"
               "Responsibilities:\n- Assemble widgets\n\n"
               "Required qualifications:\n- Proficiency with AWS and Docker\n")
    req = requirements_text(posting)
    assert "AWS" in req and "Docker" in req
    assert "Assemble widgets" not in req                 # responsibilities excluded from requirements
    assert "Assemble widgets" in responsibilities_text(posting)
    assert requirements_text("a short headerless blurb") == ""  # honest empty on no headers


def test_occupation_matching_clear_cases():
    """A2 substrate: clean titles map to the right O*NET occupation above the confidence gate."""
    for q, expect in [("Registered Nurse", "Registered Nurses"),
                      ("Data Scientist", "Data Scientists"),
                      ("Electrician", "Electricians")]:
        code, title, conf = occupation_for(q)
        assert title == expect and conf >= MIN_CONF, (q, title, conf)


def test_authoritative_requirements_cover_nontech():
    """A1/C5: authoritative requirements exist for non-tech trades/healthcare, not just tech."""
    assert role_requirements("Electrician"), "trades role should yield crisp requirements"
    assert role_requirements("Registered Nurse"), "healthcare role should yield crisp requirements"


def test_rubric_v2_blind_spot_occupation_grounded():
    """rubric_v2: a real occupation requirement is a grounded blind spot even if no posting cites it."""
    jobs = [{"company": "X", "description": "unrelated posting text"}]
    s = R.score_blind_spot("Epic Systems", jobs, {"epic systems"})  # RUBRIC_V2 default on
    assert s.score >= 3, s


def test_rubric_v2_rec_gap_closing():
    """B5: a rec that adds a real occupation requirement scores as gap-closing (not tech-keyword)."""
    jobs = [{"company": "X", "description": ""}]
    s = R.score_recommendation("Add Epic Systems experience to your clinical resume.", jobs, {"epic systems"})
    assert s.gap_closing and s.score >= 3, s


def test_mode_switch_framing(monkeypatch):
    """mode: career-changers get the constructive transition framing; stayers do not."""
    import app.agents.agent_career_strategist as cs
    from app.agents.models import CareerStrategy, BlindSpot, StrategyRec
    cap = {}

    def fake_chat(system, user, schema):
        cap["user"] = user
        return CareerStrategy(
            blind_spots=[BlindSpot(skill="s", why="w", remediation="r", time_to_proficiency="t", priority="HIGH")],
            strategy=[StrategyRec(title="t", evidence="e", action="a")])

    monkeypatch.setattr(cs, "chat", fake_chat)
    monkeypatch.setattr(cs, "query_ats_knowledge", lambda *a, **k: "")
    jobs = [{"title": "Nursing Assistant", "company": "X"}]
    cs.run("nurse aide", "resume text", jobs, [], mode="switch")
    assert "CHANGING CAREERS" in cap["user"]
    cs.run("nurse aide", "resume text", jobs, [], mode="stay")
    assert "CHANGING CAREERS" not in cap["user"]
