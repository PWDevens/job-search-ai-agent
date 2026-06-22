"""
Unit tests for configuration:
1. app/config.py: AGENT_MODEL selected by hardware tier (env override wins)
2. app/hardware.py: tier detection + model selection
3. app/agents/base.py: httpx.Client timeout is 120.0

Tests verify:
- HARDWARE_TIER maps to the right quantized model
- AGENT_MODEL env override wins over tier selection
- OLLAMA_MODEL remains independent at "qwen2.5:3b"
- httpx.Client is initialized with 120.0 timeout in base.py
"""
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _reload_config():
    import importlib
    if 'app.config' in sys.modules:
        importlib.reload(sys.modules['app.config'])
    import app.config
    return app.config


class TestHardwareTier:
    """Test hardware tier detection and model selection."""

    def test_tier_to_model_mapping(self):
        from app.hardware import select_model
        assert select_model("cpu") == "phi4-mini:q4_K_M"
        assert select_model("gpu_avg") == "phi4:q4_K_M"
        assert select_model("gpu_modern") == "gemma4:27b-q4_K_M"

    def test_detect_tier_returns_valid_tier(self):
        from app.hardware import detect_tier, MODELS
        assert detect_tier() in MODELS

    def test_cpu_tier_selects_phi4_mini(self):
        """HARDWARE_TIER=cpu should select phi4-mini quantized model."""
        os.environ.pop("AGENT_MODEL", None)
        os.environ["HARDWARE_TIER"] = "cpu"
        try:
            assert _reload_config().AGENT_MODEL == "phi4-mini:q4_K_M"
        finally:
            os.environ.pop("HARDWARE_TIER", None)

    def test_gpu_modern_tier_selects_gemma(self):
        os.environ.pop("AGENT_MODEL", None)
        os.environ["HARDWARE_TIER"] = "gpu_modern"
        try:
            assert _reload_config().AGENT_MODEL == "gemma4:27b-q4_K_M"
        finally:
            os.environ.pop("HARDWARE_TIER", None)


class TestConfigAgentModel:
    """Test AGENT_MODEL configuration."""

    def test_agent_model_respects_env_override(self):
        """AGENT_MODEL should use environment variable if set."""
        os.environ["AGENT_MODEL"] = "test-model-override"

        # Reimport config to get fresh value
        import importlib
        if 'app.config' in sys.modules:
            importlib.reload(sys.modules['app.config'])

        from app.config import AGENT_MODEL

        assert AGENT_MODEL == "test-model-override", f"Expected 'test-model-override', got '{AGENT_MODEL}'"

        # Clean up
        os.environ.pop("AGENT_MODEL", None)

    def test_ollama_model_unchanged(self):
        """OLLAMA_MODEL should still default to 'qwen2.5:3b'."""
        os.environ.pop("OLLAMA_MODEL", None)

        # Reimport config to get fresh defaults
        import importlib
        if 'app.config' in sys.modules:
            importlib.reload(sys.modules['app.config'])

        from app.config import OLLAMA_MODEL

        assert OLLAMA_MODEL == "qwen2.5:3b", f"Expected 'qwen2.5:3b', got '{OLLAMA_MODEL}'"

    def test_agent_model_independent_of_ollama_model(self):
        """AGENT_MODEL (tier-selected) and OLLAMA_MODEL should be independent."""
        os.environ.pop("AGENT_MODEL", None)
        os.environ["HARDWARE_TIER"] = "cpu"
        os.environ["OLLAMA_MODEL"] = "some-other-model"
        try:
            cfg = _reload_config()
            assert cfg.AGENT_MODEL == "phi4-mini:q4_K_M", "AGENT_MODEL should follow cpu tier"
            assert cfg.OLLAMA_MODEL == "some-other-model"
            assert cfg.AGENT_MODEL != cfg.OLLAMA_MODEL
        finally:
            os.environ.pop("OLLAMA_MODEL", None)
            os.environ.pop("HARDWARE_TIER", None)


class TestBaseHttpxTimeout:
    """Test httpx.Client timeout configuration in base.py."""

    def test_base_py_has_120_timeout(self):
        """Verify base.py line 83 has timeout=120.0."""
        from pathlib import Path
        base_path = Path(__file__).resolve().parent.parent / "app" / "agents" / "base.py"
        base_text = base_path.read_text()

        # The line should contain "timeout=120.0"
        assert 'timeout=120.0' in base_text, \
            "base.py should have timeout=120.0 in httpx.Client"
        # Should not have the old 600.0 timeout
        assert 'timeout=600.0' not in base_text, \
            "base.py should NOT have old timeout=600.0"

    def test_chat_function_uses_correct_timeout(self):
        """Verify the chat() function in base.py uses 120.0 timeout."""
        from pathlib import Path
        base_path = Path(__file__).resolve().parent.parent / "app" / "agents" / "base.py"
        base_lines = base_path.read_text().split('\n')

        # Find the line with httpx.Client
        found_correct_timeout = False
        for i, line in enumerate(base_lines):
            if 'with httpx.Client(timeout=' in line:
                if 'timeout=120.0' in line:
                    found_correct_timeout = True
                    break

        assert found_correct_timeout, \
            "chat() function should use httpx.Client(timeout=120.0)"

    def test_timeout_is_reasonable_value(self):
        """Verify timeout is a reasonable value (120 seconds = 2 minutes)."""
        from pathlib import Path
        base_path = Path(__file__).resolve().parent.parent / "app" / "agents" / "base.py"
        base_text = base_path.read_text()

        # Extract the timeout value
        import re
        match = re.search(r'timeout=(\d+(?:\.\d+)?)', base_text)
        assert match, "Should find timeout value in base.py"

        timeout_val = float(match.group(1))
        assert 60 <= timeout_val <= 300, \
            f"Timeout should be reasonable (60-300s), got {timeout_val}"
        assert timeout_val == 120.0, f"Expected timeout=120.0, got {timeout_val}"

    def test_base_py_imports_httpx(self):
        """Verify base.py imports httpx."""
        from pathlib import Path
        base_path = Path(__file__).resolve().parent.parent / "app" / "agents" / "base.py"
        base_text = base_path.read_text()

        assert 'import httpx' in base_text, "base.py should import httpx"

    def test_base_py_chat_function_exists(self):
        """Verify the chat() function exists in base.py."""
        from pathlib import Path
        base_path = Path(__file__).resolve().parent.parent / "app" / "agents" / "base.py"
        base_text = base_path.read_text()

        assert 'def chat(' in base_text, "base.py should have chat() function"
