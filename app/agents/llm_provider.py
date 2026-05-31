"""
LLM provider abstraction layer.
Selects the best available local LLM at runtime and returns a CrewAI-compatible LLM object.

Priority order (controlled by LLM_BACKEND env var):
  1. "phi4_mini"   → Microsoft Phi-4-mini via Ollama  (best quality on <8 GB RAM, no GPU)
  2. "llama3"      → Meta Llama-3 8B via Ollama        (default, good balance)
  3. "mistral"     → Mistral 7B via Ollama             (alternative)
  4. "tinyllama"   → TinyLlama 1.1B via Ollama         (extreme resource constraint)
  5. "mock"        → DeterministicMock                 (unit tests / CI only)

Ollama runs the inference server; CrewAI talks to it via its OpenAI-compatible endpoint.
No external API keys required.
"""
from __future__ import annotations
import logging
import os
from typing import Any

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)

LLM_BACKEND = os.getenv("LLM_BACKEND", "llama3")   # override in .env

# Map friendly names → Ollama model tags
_OLLAMA_MODEL_MAP = {
    "phi4_mini":  "phi4-mini",         # Microsoft Phi-4-mini  (~2.7 GB, CPU-friendly)
    "phi3_mini":  "phi3:mini",         # Microsoft Phi-3-mini  (~2.2 GB)
    "llama3":     "llama3",            # Meta Llama-3 8B       (~4.7 GB)
    "llama3_1b":  "llama3.2:1b",       # Meta Llama-3.2 1B     (~1.3 GB)
    "mistral":    "mistral",           # Mistral 7B            (~4.1 GB)
    "tinyllama":  "tinyllama",         # TinyLlama 1.1B        (~0.6 GB)
    "gemma2_2b":  "gemma2:2b",         # Google Gemma-2 2B     (~1.6 GB)
    "qwen2_5_3b": "qwen2.5:3b",        # Alibaba Qwen-2.5 3B   (~1.9 GB)
}


def get_llm() -> Any:
    """
    Return a CrewAI / LiteLLM-compatible LLM object for the configured backend.
    Falls back gracefully if the primary model isn't available.
    """
    if LLM_BACKEND == "mock":
        return _MockLLM()

    model_tag = _OLLAMA_MODEL_MAP.get(LLM_BACKEND, LLM_BACKEND)
    return _build_ollama_llm(model_tag)


def _build_ollama_llm(model_tag: str) -> Any:
    """
    Build an Ollama-backed LLM via LiteLLM (used internally by CrewAI).
    The base_url points to the Ollama container's OpenAI-compatible endpoint.
    """
    try:
        from crewai import LLM   # CrewAI ≥ 0.61 ships its own LLM wrapper
        llm = LLM(
            model=f"ollama/{model_tag}",
            base_url=f"{OLLAMA_BASE_URL}",
            temperature=0.3,
            max_tokens=2048,
        )
        logger.info("LLM ready: ollama/%s  (base_url=%s)", model_tag, OLLAMA_BASE_URL)
        return llm
    except ImportError:
        # Older CrewAI versions — use LiteLLM directly
        import litellm
        litellm.set_verbose = False

        class _LiteLLMWrapper:
            def __init__(self, model, base_url):
                self.model    = model
                self.base_url = base_url

            def call(self, messages, **kwargs):
                resp = litellm.completion(
                    model=f"ollama/{self.model}",
                    messages=messages,
                    api_base=self.base_url,
                    temperature=0.3,
                    max_tokens=2048,
                )
                return resp.choices[0].message.content

        return _LiteLLMWrapper(model_tag, OLLAMA_BASE_URL)


class _MockLLM:
    """Deterministic mock — used only in unit tests (LLM_BACKEND=mock)."""
    model = "mock"

    def call(self, messages, **kwargs):   # noqa: ARG002
        return "MOCK_LLM_RESPONSE"

    def __call__(self, messages, **kwargs):
        return self.call(messages, **kwargs)
