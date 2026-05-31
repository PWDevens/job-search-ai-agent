"""
app/agents/__init__.py — Agents Sub-Package Marker
====================================================

WHY THIS FILE EXISTS:
---------------------
This file makes the `agents/` folder a Python sub-package so that
statements like this work from anywhere in the project:

    from app.agents.crew import run_search_crew
    from app.agents.tools import JobSearchTool

Without this file, Python sees `agents/` as just a folder full of
unrelated files — not as a module you can import from.

WHAT'S IN THIS PACKAGE:
  crew.py          → CrewAI 3-agent orchestration (JobMatcher, ResumeCoach, CareerStrategist)
  llm_provider.py  → Selects and configures the local LLM (Phi-4-mini, Llama-3, etc.)
  rag_knowledge.py → ATS / hiring best-practice knowledge base (RAG over ChromaDB)
  tools.py         → Custom CrewAI tools that agents call during reasoning

JUPYTER ANALOGY:
  In a notebook you'd put all agent code in one giant cell or file.
  Here, each concern gets its own file. This __init__.py is the
  "index card" that tells Python they all belong to the same package.

Nothing needs to be imported here — keeping __init__.py files minimal
is a Python best practice. Import what you need directly from the
specific module (e.g., `from app.agents.crew import ...`).
"""
