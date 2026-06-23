"""
Hardware tier detection and model selection.

Tiers (model picked to FIT the tier's VRAM, smarter model on bigger cards):
  cpu         — no NVIDIA GPU;     phi4-mini:q4_K_M   (~2.5 GB RAM)
  gpu_avg     — GPU <  10 GB VRAM; gemma2:9b          (~5.5 GB VRAM, fits 8 GB)
  gpu_modern  — GPU >= 10 GB VRAM; phi4               (14B, ~9-12 GB VRAM)

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
    "cpu":        "phi4-mini:q4_K_M",
    "gpu_avg":    "gemma2:9b",   # fits an 8 GB card cleanly (no offload)
    "gpu_modern": "phi4",        # 14B; needs ~12 GB, comfortable on 16 GB+
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
