"""
Job-posting section parser — the "data dictionary" (PathForward A0).

Job postings are formulaic: about-company -> role summary -> responsibilities ->
required qualifications -> preferred qualifications -> compensation/benefits. This
splits raw posting text into those sections so downstream code can TARGET the part
it needs (retrieval + grounding want *requirements*, not the company blurb), instead
of embedding/truncating the whole blob.

Deterministic: regex over the canonical header set (~70-80% of real postings have
recognizable headers) with a positional fallback for headerless text. No LLM.

    python -m app.pipeline.sections   # self-check
"""
import re

# Canonical section keys, in posting order.
SECTIONS = ["company_overview", "role_summary", "responsibilities",
            "required_qualifications", "preferred_qualifications",
            "compensation", "benefits", "other"]

# header regex -> section key (first match wins; order matters — specific before generic).
_HEADERS = [
    (r"about (the company|us|the team)|company overview|who we are", "company_overview"),
    (r"responsibilities|what you'?ll do|what you will do|duties|day[- ]?to[- ]?day|essential functions|the role|key duties", "responsibilities"),
    (r"preferred qualifications|nice[- ]to[- ]have|preferred skills|bonus|desired|a plus|preferred", "preferred_qualifications"),
    (r"required qualifications|requirements|qualifications|what you'?ll need|what you will need|minimum qualifications|basic qualifications|required skills|must[- ]have|you have", "required_qualifications"),
    (r"compensation|salary|pay range|what we pay", "compensation"),
    (r"benefits|perks|what we offer|why join", "benefits"),
    (r"role summary|position summary|job summary|overview|about (this|the) role|summary", "role_summary"),
]
_HEADER_RE = re.compile(r"^\s*[-*•]?\s*(" + "|".join(p for p, _ in _HEADERS) + r")\s*:?\s*$",
                        re.IGNORECASE)


def _classify(line: str) -> str | None:
    """Return the section key if `line` is a recognized header, else None."""
    if not _HEADER_RE.match(line.strip()):
        return None
    low = line.lower()
    for pat, key in _HEADERS:
        if re.search(pat, low):
            return key
    return None


def parse_sections(text: str) -> dict[str, str]:
    """Split posting text into {section_key: text}. Text before the first recognized
    header goes to role_summary (the typical lead = company/role intro)."""
    out: dict[str, list[str]] = {}
    current = "role_summary"
    for line in (text or "").splitlines():
        key = _classify(line)
        if key:
            current = key
            continue
        if line.strip():
            out.setdefault(current, []).append(line.strip())
    return {k: "\n".join(v).strip() for k, v in out.items()}


def requirements_text(text: str) -> str:
    """The requirements portion = required + preferred qualifications (what a candidate
    must close to be hireable). Empty string if no qualifications section was found
    (e.g. a truncated Adzuna snippet) — callers then fall back to authoritative O*NET reqs."""
    s = parse_sections(text)
    parts = [s.get("required_qualifications", ""), s.get("preferred_qualifications", "")]
    return "\n".join(p for p in parts if p).strip()


def responsibilities_text(text: str) -> str:
    return parse_sections(text).get("responsibilities", "")


if __name__ == "__main__":
    sample = (
        "Onyx Technologies is hiring a Software Developer in Austin, TX. Build web apps.\n\n"
        "Responsibilities:\n- Design and ship backend services\n- Write tests\n\n"
        "Required qualifications:\n- Bachelor's degree; 2-4 years experience\n"
        "- Proficiency with AWS, Apache Kafka, Docker\n\n"
        "Preferred qualifications:\n- Experience with Kubernetes, Terraform\n"
    )
    s = parse_sections(sample)
    assert "Design and ship backend services" in s["responsibilities"], s
    req = requirements_text(sample)
    assert "AWS" in req and "Kubernetes" in req, req
    assert "Design and ship" not in req, "requirements must not include responsibilities"
    # headerless fallback -> everything in role_summary, requirements empty
    assert requirements_text("Just a short truncated blurb with no headers...") == ""
    print("sections:", {k: v[:40] for k, v in s.items()})
    print("requirements_text:", req.replace("\n", " | "))
    print("self-check OK")
