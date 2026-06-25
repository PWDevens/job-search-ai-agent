"""
Shared primitives for agent communication with Ollama.
- load_skill: reads .md skill files and appends grounding
- chat: calls Ollama /api/chat with JSON schema validation
- transport: a local/pod Ollama server, or (if RUNPOD_ENDPOINT_ID is set) a
  RunPod serverless endpoint that wraps the same /api/chat payload.
"""
import logging
import time
from pathlib import Path
import httpx
from pydantic import BaseModel, ValidationError
import app.config as cfg
from app.config import JOB_CONTEXT_CHARS

logger = logging.getLogger(__name__)

SKILLS = Path(__file__).parent / "agent_skills"

# Perf telemetry from the most recent Ollama call (read by the eval harness).
# Updated on every successful chat(); tokens_per_sec = eval_count / eval_duration.
LAST_TIMING: dict = {}


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

    Reads agent_skills/<name>.md and agent_skills/_grounding.md.
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


def _call_runpod_serverless(request_body: dict) -> dict:
    """Run the Ollama /api/chat payload on a RunPod serverless endpoint.

    Wraps the body as {"input": <payload>}, submits to /run, polls /status until the
    job finishes, and returns the worker's "output" (which is the raw Ollama /api/chat
    response — same shape the direct path returns). Polling (not runsync) so the
    ~60-90s job_matcher generations that exceed runsync's 90s window still work.
    """
    base = f"https://api.runpod.ai/v2/{cfg.RUNPOD_ENDPOINT_ID}"
    headers = {"Authorization": f"Bearer {cfg.RUNPOD_API_KEY}"}
    with httpx.Client(timeout=cfg.OLLAMA_TIMEOUT) as client:
        sub = client.post(f"{base}/run", json={"input": request_body}, headers=headers)
        sub.raise_for_status()
        job_id = sub.json()["id"]

        deadline = time.monotonic() + cfg.RUNPOD_POLL_TIMEOUT
        while time.monotonic() < deadline:
            st = client.get(f"{base}/status/{job_id}", headers=headers)
            st.raise_for_status()
            data = st.json()
            status = data.get("status")
            if status == "COMPLETED":
                return data.get("output") or {}
            if status in ("FAILED", "CANCELLED", "TIMED_OUT"):
                raise ValueError(f"RunPod job {job_id} {status}: {data.get('error') or data}")
            time.sleep(cfg.RUNPOD_POLL_INTERVAL)
        raise TimeoutError(f"RunPod job {job_id} did not complete in {cfg.RUNPOD_POLL_TIMEOUT}s")


def _call_ollama(request_body: dict) -> dict:
    """Return the Ollama /api/chat response dict — via a RunPod serverless endpoint
    if configured (RUNPOD_ENDPOINT_ID + RUNPOD_API_KEY), else the direct server."""
    if cfg.RUNPOD_ENDPOINT_ID and cfg.RUNPOD_API_KEY:
        return _call_runpod_serverless(request_body)
    with httpx.Client(timeout=cfg.OLLAMA_TIMEOUT) as client:
        response = client.post(f"{cfg.OLLAMA_BASE_URL}/api/chat", json=request_body)
        response.raise_for_status()
        return response.json()


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
    # Read config dynamically so the eval harness can vary model / GPU / temp per run.
    options = {
        "temperature": cfg.OLLAMA_TEMPERATURE,
        "num_ctx": cfg.OLLAMA_NUM_CTX,
    }
    if cfg.OLLAMA_NUM_GPU is not None:      # 0 = force CPU; N = cap GPU layers (simulate smaller VRAM)
        options["num_gpu"] = cfg.OLLAMA_NUM_GPU
    if cfg.OLLAMA_NUM_THREAD:               # cap CPU threads to mimic an average CPU
        options["num_thread"] = cfg.OLLAMA_NUM_THREAD

    request_body = {
        "model": cfg.AGENT_MODEL,
        "stream": False,
        "format": schema.model_json_schema(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "options": options,
    }

    transport = "runpod" if (cfg.RUNPOD_ENDPOINT_ID and cfg.RUNPOD_API_KEY) else "ollama"
    logger.debug(f"chat via {transport} | model {cfg.AGENT_MODEL} options={options}")

    try:
        response_json = _call_ollama(request_body)
        content = response_json.get("message", {}).get("content", "")

        # Capture inference perf (Ollama returns nanosecond durations).
        eval_count = response_json.get("eval_count")
        eval_dur   = response_json.get("eval_duration")
        LAST_TIMING.clear()
        LAST_TIMING.update({
            "eval_count": eval_count,
            "eval_duration_ns": eval_dur,
            "total_duration_ns": response_json.get("total_duration"),
            "tokens_per_sec": (eval_count / (eval_dur / 1e9)) if eval_count and eval_dur else None,
        })

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
