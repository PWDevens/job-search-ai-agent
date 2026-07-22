"""
Hardware tier detection and model selection.

Tiers (models from the iter16 model bake-off — see reports/IMPROVEMENT_LOG.md):
  cpu         — no NVIDIA GPU (incl. iGPU/Apple);  qwen3:4b    (~3 GB; fast everywhere)
  gpu_avg     — GPU <  10 GB VRAM;                 qwen3:4b    (~3 GB)
  gpu_modern  — GPU >= 10 GB VRAM;                 gemma3:12b  (~8 GB)

The bake-off (2026-06, 13 models, switch+stay cells) found the base model is the DOMINANT eval lever:
+0.76-0.79 overall vs the old llama3.1:8b, which ranked near the BOTTOM. Two robust co-winners that
generalize across both persona cells:
  - qwen3:4b   — best overall AND smallest (4B); fast on CPU/iGPU/Metal -> default for the small +
                 non-NVIDIA tiers, where no US model competes at that size. Origin: Alibaba (CN).
  - gemma3:12b — US (Google), essentially tied with qwen3:4b, for real NVIDIA GPUs (>=10 GB VRAM).
Notable: scaling BACKFIRES (qwen3 4b>8b>14b>30b-a3b); gpt-oss:20b led on switch but dropped BELOW the
old model on stay (why both cells are tested). Requires OLLAMA_NUM_CTX>=8192 (config default) — the
~5.2k-token job_matcher prompt fails at 4096.

US-only deployments: AGENT_MODEL=gemma3:12b everywhere (slower on small hardware), or try the untested
gemma3:4b for the small tier. US is preferred-not-required; qwen3:4b is the performance/size pick.
detect_tier only probes nvidia-smi, so Apple-Silicon Macs fall to 'cpu' -> qwen3:4b (still the best
model, fast on Metal); add a Metal tier if a >=24 GB Mac should run gemma3:12b.

Override via env:
  HARDWARE_TIER=cpu|gpu_avg|gpu_modern   (skips detection)
  AGENT_MODEL=<any Ollama model>          (skips tier → model lookup entirely)

ponytail: single subprocess call, no new deps. Add ROCm/Apple-Silicon tiers
  when those hardware paths need testing.
"""
import logging
import subprocess

logger = logging.getLogger(__name__)

MODELS = {
    "cpu":        "qwen3:4b",
    "gpu_avg":    "qwen3:4b",
    "gpu_modern": "gemma3:12b",
}

_tier: str | None = None  # cached after first detection


def detect_tier() -> str:
    """Probe nvidia-smi for VRAM; fall back to 'cpu' if unavailable."""
    global _tier
    if _tier is not None:
        return _tier

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            vram_mb = int(out.stdout.strip().split("\n")[0])
            _tier = "gpu_modern" if vram_mb >= 10_000 else "gpu_avg"
            logger.info("GPU detected: %d MB VRAM → tier=%s", vram_mb, _tier)
            return _tier
    except Exception:
        pass

    _tier = "cpu"
    logger.info("No GPU detected → tier=cpu")
    return _tier


def select_model(tier: str) -> str:
    """Return Ollama model string for the given tier."""
    return MODELS.get(tier, MODELS["cpu"])


if __name__ == "__main__":
    t = detect_tier()
    m = select_model(t)
    print(f"tier={t}  model={m}")
    assert t in MODELS, f"Unknown tier: {t}"
    assert ":" in m, f"Model should include quantization tag: {m}"
    print("PASS")
