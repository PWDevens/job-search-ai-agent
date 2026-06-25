"""
Offline checks for the RunPod-serverless transport in app/agents/base.py.
Mocks httpx so no network/Ollama/endpoint is needed.

Run: python tests/test_serverless_adapter.py
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.config as cfg
from app.agents import base


class _Resp:
    def __init__(self, data): self._d = data
    def raise_for_status(self): pass
    def json(self): return self._d


class _FakeClient:
    """Records requests; serves canned /run + /status (serverless) or /api/chat (direct)."""
    calls = []

    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False

    def post(self, url, json=None, headers=None):
        _FakeClient.calls.append(("POST", url, json))
        if url.endswith("/run"):
            return _Resp({"id": "job123"})
        return _Resp({"message": {"content": '{"ok": true}'}})  # direct /api/chat

    def get(self, url, headers=None):
        _FakeClient.calls.append(("GET", url, None))
        return _Resp({"status": "COMPLETED",
                      "output": {"message": {"content": '{"ok": true}'},
                                 "eval_count": 4, "eval_duration": 1_000_000}})


def test_serverless_wraps_input_polls_status_unwraps_output():
    _FakeClient.calls = []
    with patch("httpx.Client", _FakeClient), \
         patch.object(cfg, "RUNPOD_ENDPOINT_ID", "ep1"), \
         patch.object(cfg, "RUNPOD_API_KEY", "key1"):
        out = base._call_ollama({"messages": [{"role": "user", "content": "hi"}]})
    run = [c for c in _FakeClient.calls if c[0] == "POST" and c[1].endswith("/run")][0]
    assert run[2] == {"input": {"messages": [{"role": "user", "content": "hi"}]}}, "must wrap body in input"
    assert any(c[1].endswith("/status/job123") for c in _FakeClient.calls), "must poll /status"
    assert out["message"]["content"] == '{"ok": true}', "must unwrap output"
    print("[PASS] serverless: wraps input -> /run -> poll /status -> unwraps output")


def test_direct_path_when_unconfigured():
    _FakeClient.calls = []
    with patch("httpx.Client", _FakeClient), \
         patch.object(cfg, "RUNPOD_ENDPOINT_ID", ""), \
         patch.object(cfg, "RUNPOD_API_KEY", ""):
        base._call_ollama({"messages": []})
    assert any(c[1].endswith("/api/chat") for c in _FakeClient.calls), "direct path hits /api/chat"
    assert not any("/run" in c[1] for c in _FakeClient.calls), "must not use serverless when unconfigured"
    print("[PASS] direct ollama path when serverless not configured")


if __name__ == "__main__":
    tests = [test_serverless_wraps_input_polls_status_unwraps_output,
             test_direct_path_when_unconfigured]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {type(e).__name__}: {e}"); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
