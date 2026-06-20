"""
Unit tests for configuration changes:
1. app/config.py: AGENT_MODEL default changed to "phi4-mini" (not dependent on OLLAMA_MODEL)
2. app/agents/base.py: httpx.Client timeout changed from 600.0 to 120.0

Tests verify:
- AGENT_MODEL defaults to "phi4-mini" without env override
- OLLAMA_MODEL remains independent at "qwen2.5:3b"
- httpx.Client is initialized with 120.0 timeout in base.py
"""
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestConfigAgentModel:
    """Test AGENT_MODEL configuration."""

    def test_agent_model_defaults_to_phi4_mini(self):
        """AGENT_MODEL should default to 'phi4-mini' when no env override."""
        # Clear any existing env vars
        os.environ.pop("AGENT_MODEL", None)
        os.environ.pop("OLLAMA_MODEL", None)

        # Reimport config to get fresh defaults
        import importlib
        if 'app.config' in sys.modules:
            importlib.reload(sys.modules['app.config'])

        from app.config import AGENT_MODEL

        assert AGENT_MODEL == "phi4-mini", f"Expected 'phi4-mini', got '{AGENT_MODEL}'"

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
        """AGENT_MODEL and OLLAMA_MODEL should be independent.

        This is the key fix: previously AGENT_MODEL = os.getenv("AGENT_MODEL", OLLAMA_MODEL)
        made it depend on OLLAMA_MODEL. Now it should default to "phi4-mini" regardless.
        """
        os.environ.pop("AGENT_MODEL", None)
        os.environ["OLLAMA_MODEL"] = "some-other-model"

        # Reimport config
        import importlib
        if 'app.config' in sys.modules:
            importlib.reload(sys.modules['app.config'])

        from app.config import AGENT_MODEL, OLLAMA_MODEL

        assert AGENT_MODEL == "phi4-mini", "AGENT_MODEL should be phi4-mini"
        assert OLLAMA_MODEL == "some-other-model", "OLLAMA_MODEL should be some-other-model"
        assert AGENT_MODEL != OLLAMA_MODEL, "AGENT_MODEL and OLLAMA_MODEL should be independent"

        # Clean up
        os.environ.pop("OLLAMA_MODEL", None)

    def test_config_file_has_correct_comment(self):
        """Verify that config.py line 18 has the correct comment."""
        from pathlib import Path
        config_path = Path(__file__).resolve().parent.parent / "app" / "config.py"
        config_text = config_path.read_text()

        # The line should contain "agents default to phi4-mini"
        assert 'agents default to phi4-mini' in config_text, \
            "config.py should have comment about phi4-mini default"
        # The line should contain AGENT_MODEL and phi4-mini default (allowing for whitespace variations)
        assert 'AGENT_MODEL' in config_text and 'phi4-mini' in config_text, \
            "config.py should have AGENT_MODEL with phi4-mini as default"
        # Verify it's using os.getenv with phi4-mini
        import re
        agent_model_pattern = r'AGENT_MODEL\s*=\s*os\.getenv\s*\(\s*"AGENT_MODEL"\s*,\s*"phi4-mini"\s*\)'
        assert re.search(agent_model_pattern, config_text), \
            "config.py should have AGENT_MODEL = os.getenv(\"AGENT_MODEL\", \"phi4-mini\")"


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
