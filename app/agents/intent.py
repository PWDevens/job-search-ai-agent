"""
Intent-aware context engineering for the agents.

A job seeker's *intent* changes what good advice looks like. We model two axes:
  - mode: "stay" (advance/move within the field) vs "switch" (career change)
  - stay_reason (only when mode=="stay"): why they're moving —
      "advancement"  : more responsibility / next level
      "comp_culture" : better company, pay, or feeling undervalued
      "displaced"    : laid off / fired, re-landing quickly
      "lateral"/""   : generic same-field move (default — no extra framing)

`note(agent, mode, stay_reason)` returns a short framing block to append to that agent's
user message. Centralized here so the three agents stay clean and the framing is consistent.
"""

_SWITCH = {
    "job_matcher": (
        "NOTE: this candidate is CHANGING CAREERS into this field. Rank by TRANSFERABLE skills and "
        "growth potential, not by how many target-role requirements they already meet — a career-changer "
        "will be missing several. Favor roles their background plausibly bridges into."),
    "resume_coach": (
        "NOTE: this candidate is CHANGING CAREERS. Frame every recommendation CONSTRUCTIVELY as a "
        "transition: (1) surface and reframe TRANSFERABLE experience for the target field, (2) recommend "
        "the highest-priority bridge skills/credentials to add. Do not present the resume as deficient — "
        "present a path."),
    "career_strategist": (
        "NOTE: this candidate is CHANGING CAREERS into the target field. Produce a constructive TRANSITION "
        "ROADMAP, not a deficiency list: lead with their transferable strengths, then for each gap give the "
        "bridge (course/cert/project) and a realistic time-to-proficiency."),
}

# stay_reason -> agent -> framing
_STAY = {
    "advancement": {
        "job_matcher": ("NOTE: this candidate is ADVANCING in their field — favor roles with greater scope "
                        "or seniority than their current one, not lateral copies."),
        "resume_coach": ("NOTE: the candidate seeks MORE RESPONSIBILITY. Recommend quantifying SCOPE and "
                         "IMPACT (team size, budget, outcomes) and foregrounding leadership/ownership — the "
                         "evidence a promotion committee looks for."),
        "career_strategist": ("NOTE: the candidate is moving UP a level. Focus blind spots on what the NEXT "
                              "level requires — people/budget/strategy leadership, broader scope, specialized "
                              "certifications — not entry-level basics they already have."),
    },
    "comp_culture": {
        "job_matcher": ("NOTE: the candidate is well-qualified but seeking a BETTER EMPLOYER / PAY. Favor "
                        "reputable employers and roles likely to offer stronger compensation or culture."),
        "resume_coach": ("NOTE: the candidate feels UNDERVALUED and wants better comp/title. Sharpen "
                         "high-impact, QUANTIFIED achievements that justify a higher band; lead with results, "
                         "not duties."),
        "career_strategist": ("NOTE: the candidate is qualified but UNDERVALUED (pay/culture). Focus on "
                              "positioning for a higher comp/title and identifying stronger employers; note "
                              "where their evidence supports a market-rate step up rather than skill gaps."),
    },
    "displaced": {
        "job_matcher": ("NOTE: the candidate was recently LAID OFF/let go and needs to re-land quickly. Favor "
                        "a BROAD set of same-role openings to maximize fast, realistic re-employment."),
        "resume_coach": ("NOTE: the candidate is RE-LANDING after displacement. Foreground a strong, PROVEN "
                         "track record; handle any employment gap matter-of-factly (emphasize achievements "
                         "over a strict timeline). Keep the tone confident, not apologetic."),
        "career_strategist": ("NOTE: the candidate was DISPLACED and needs a fast re-land. Prioritize a "
                              "confidence-building, near-term plan that leverages PROVEN strengths; keep any "
                              "upskilling lightweight and immediately applicable."),
    },
}


def note(agent: str, mode: str = "stay", stay_reason: str = "") -> str:
    """Return the framing block (prefixed with two newlines) for this agent + intent, or ''."""
    if mode == "switch":
        block = _SWITCH.get(agent, "")
    else:
        block = _STAY.get((stay_reason or "").lower(), {}).get(agent, "")
    return f"\n\n{block}" if block else ""
