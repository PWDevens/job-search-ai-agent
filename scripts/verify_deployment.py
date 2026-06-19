#!/usr/bin/env python
"""
Stage 1: Deployment Verification Script

Checks all three services (Weaviate, Ollama, Flask app) and confirms
the canonical LLM model is available.

Exit codes:
  0 = all checks passed
  1 = one or more checks failed
"""

import sys
import os
import requests
from typing import Tuple


def check_weaviate() -> Tuple[bool, str]:
    """Check Weaviate meta endpoint"""
    try:
        response = requests.get("http://localhost:8080/v1/meta", timeout=5)
        if response.status_code == 200:
            return True, "[OK] Weaviate meta endpoint"
        else:
            return False, f"[FAIL] Weaviate returned {response.status_code}"
    except Exception as e:
        return False, f"[FAIL] Weaviate: {e}"


def check_ollama_version() -> Tuple[bool, str]:
    """Check Ollama version endpoint"""
    try:
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        if response.status_code == 200:
            return True, "[OK] Ollama version endpoint"
        else:
            return False, f"[FAIL] Ollama returned {response.status_code}"
    except Exception as e:
        return False, f"[FAIL] Ollama: {e}"


def check_ollama_model() -> Tuple[bool, str]:
    """Check that the configured LLM model is available"""
    try:
        # Read model name from environment (default: phi4-mini)
        model_name = os.environ.get("OLLAMA_MODEL", "phi4-mini")

        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            return False, f"[FAIL] Ollama tags endpoint returned {response.status_code}"

        data = response.json()
        models = data.get("models", [])
        model_names = [m.get("name", "") for m in models]

        # Check for exact match or base name match (handles tags like "model:latest")
        base_model_name = model_name.split(":")[0]
        matched = any(m == model_name or m.startswith(base_model_name + ":") for m in model_names)

        if matched:
            return True, f"[OK] Model '{model_name}' is available"
        else:
            available = ", ".join(model_names) if model_names else "none"
            return False, f"[FAIL] Model '{model_name}' not found. Available: {available}"
    except Exception as e:
        return False, f"[FAIL] Ollama models: {e}"


def check_flask_health() -> Tuple[bool, str]:
    """Check Flask app health endpoint"""
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                return True, "[OK] Flask app health"
            else:
                return False, f"[FAIL] Flask status != 'ok': {data.get('status')}"
        else:
            return False, f"[FAIL] Flask returned {response.status_code}"
    except Exception as e:
        return False, f"[FAIL] Flask health: {e}"


def main() -> int:
    """Run all deployment checks"""
    print("\n" + "=" * 60)
    print("STAGE 1: DEPLOYMENT VERIFICATION")
    print("=" * 60 + "\n")

    checks = [
        ("Weaviate", check_weaviate),
        ("Ollama Version", check_ollama_version),
        ("Ollama Model", check_ollama_model),
        ("Flask Health", check_flask_health),
    ]

    results = []
    for name, check_func in checks:
        passed, message = check_func()
        results.append((name, passed, message))
        print(message)

    print("\n" + "=" * 60)

    # Count results
    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)

    if passed_count == total_count:
        print(f"[PASS] All {total_count} checks passed")
        print("=" * 60 + "\n")
        return 0
    else:
        print(f"[FAIL] {total_count - passed_count}/{total_count} checks failed")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
