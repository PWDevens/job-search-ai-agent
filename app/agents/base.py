"""
Shared primitives for agent communication with Ollama.
- load_skill: reads .md skill files and appends grounding
- chat: calls Ollama /api/chat with JSON schema validation
"""
import logging
from pathlib import Path
import httpx
from pydantic import BaseModel, ValidationError
from app.config import OLLAMA_BASE_URL, AGENT_MODEL, JOB_CONTEXT_CHARS

logger = logging.getLogger(__name__)

SKILLS = Path(__file__).parent / "skills"


def fmt_resume(text: str | None, chars: int) -> str:
    """Truncate resume to `chars`; returns '(no resume)' if empty."""
    return text[:chars] if text else "(no resume)"


def fmt_jobs(jobs: list[dict], max_count: int = 10, detail: bool = False) -> str:
    """Numbered job list for agent context. Replaces inline loops in each agent.

    detail=True: includes location, salary, url, doc excerpt (job_matcher context)
    detail=False: title + company only (resume_coach / career_strategist context)
    """
    lines = []
    for i, job in enumerate(jobs[:max_count], 1):
        title   = job.get("title",   "N/A")
        company = job.get("company", "N/A")
        if detail:
            loc = job.get("location", "")
            sal = job.get("salary",   "")
            url = job.get("url",      "")
            doc = job.get("document", "")[:JOB_CONTEXT_CHARS]
            extras = (
                (f" | {loc}" if loc else "")
                + (f" | {sal}" if sal else "")
                + (f" | {url}" if url else "")
                + (f" | {doc}" if doc else "")
            )
            lines.append(f"{i}. {title} at {company}{extras}")
        else:
            lines.append(f"{i}. {title} at {company}")
    return "\n".join(lines)


def load_skill(name: str) -> str:
    """Load a skill file and append grounding.

    Reads skills/<name>.md and skills/_grounding.md.
    Strips YAML frontmatter (lines from --- to second ---).
    Returns: skill_body + "\n\n---\n" + grounding_body
    """
    skill_path = SKILLS / f"{name}.md"
    grounding_path = SKILLS / "_grounding.md"

    if not skill_path.exists():
        raise FileNotFoundError(f"Skill file not found: {skill_path}")
    if not grounding_path.exists():
        raise FileNotFoundError(f"Grounding file not found: {grounding_path}")

    def strip_frontmatter(text: str) -> str:
        """Strip YAML frontmatter (--- to ---)."""
        lines = text.split('\n')
        if not lines[0].strip().startswith('---'):
            return text
        # Find the closing ---
        for i in range(1, len(lines)):
            if lines[i].strip().startswith('---'):
                return '\n'.join(lines[i+1:])
        return text

    skill_body = strip_frontmatter(skill_path.read_text(encoding='utf-8'))
    grounding_body = strip_frontmatter(grounding_path.read_text(encoding='utf-8'))

    return f"{skill_body}\n\n---\n{grounding_body}"


def chat(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """Call Ollama /api/chat with JSON schema validation.

    Args:
        system: system prompt (skill text)
        user: user message (context + request)
        schema: Pydantic model class for output validation

    Returns:
        Validated model instance

    Raises:
        httpx.ConnectError, httpx.TimeoutException: Ollama unavailable
        ValidationError: Response doesn't match schema
        ValueError: JSON parsing failed
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"
    request_body = {
        "model": AGENT_MODEL,
        "stream": False,
        "format": schema.model_json_schema(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "options": {
            "temperature": 0.2,
            "num_ctx": 4096
        }
    }

    logger.debug(f"Calling Ollama {url} with model {AGENT_MODEL}")

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=request_body)
            response.raise_for_status()

        response_json = response.json()
        content = response_json.get("message", {}).get("content", "")

        if not content:
            raise ValueError("Empty response from Ollama")

        # Validate against schema
        return schema.model_validate_json(content)

    except httpx.HTTPError as e:
        logger.error(f"HTTP error calling Ollama: {e}")
        raise
    except ValidationError as e:
        logger.error(f"Validation error: response does not match schema: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat: {e}")
        raise
