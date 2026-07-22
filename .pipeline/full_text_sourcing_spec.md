# Spec — Full posting text (un-truncation) sourcing

Status: PROPOSED (path a). Grounded by direct probes, 2026-06-29.

## Problem (confirmed, not assumed)
- **100% of Adzuna descriptions are truncated at exactly 500 chars** (median=max=500 across 429 cached
  postings). The requirements section lives in the cut-off tail — see [adzuna jobs](data/adzuna/jobs_pre.csv).
- The Adzuna `url` is a **redirect landing page**, and it returns **HTTP 403** to a plain fetch
  (bot-protected) — so "just follow the link" does not work.

## The honest prior question (test BEFORE building sourcing)
We already *mitigated* truncation: `AUTHORITATIVE_GAPS` injects the target occupation's real O*NET
requirements as the grounding source, and evidence-depth (iter12) made that the standing win. So the
real question is **does full posting text beat the O*NET fallback?** If O*NET already grounds blind
spots/recs well, full text may add nothing — the same noise-floor outcome as ESCO/sampling/Causeways.
**Gate the whole investment on a cheap Phase-0 test (below). Do not build sourcing first.**

## Sourcing options (ranked by signal-to-effort)
| Option | Full text? | Cost | Coverage | Notes |
|---|---|---|---|---|
| **ATS public APIs** (Greenhouse/Lever/Ashby) | YES (probed: Greenhouse stripe = 3667 chars, 489 jobs) | **free, no auth, no bot-wall, structured** | only companies on that ATS; need board token | **best path** |
| **USAJOBS API** | YES | free (needs free API key; probed 401 without) | US federal only | narrow but clean |
| **BrightData scrape** of Adzuna redirect -> original posting | YES | per-fetch $ + fragile + ToS | broad | use only if breadth is essential; skill available |
| **Paid Adzuna tier** | maybe | $ | broad | verify whether their paid plan lifts the 500 cap |

Recommendation: **ATS APIs for the test and the first real source** (free, reliable, full, structured).
Treat BrightData as a later breadth lever, not the starting point.

## Architecture (most of it already exists)
1. **Ingest-time enrichment**: when a posting has a known ATS source, fetch full `content` and use it as
   `description`. The section parser ([sections.py](app/pipeline/sections.py)) already extracts
   `requirements_text` from full text -> feeds the coach/strategist (the A1 path).
2. **Cache** full text by job id (avoid refetch; ATS content is stable). Local SQLite/JSON, like audit.
3. No agent changes — the pipeline already prefers `requirements_text` when present and falls back to
   O*NET when absent. Full text simply makes `requirements_text` real on more postings.

## Phase 0 — the decisive cheap test (do this first)
1. Pull a full-text corpus from **Greenhouse boards** for a few queries matching existing personas
   (e.g. software developer, accountant, sales) — free, ~an afternoon, no pod.
2. Ingest into a `chroma_fulltext` collection; confirm `requirements_text` is now populated (vs empty on
   truncated Adzuna).
3. Run the eval on those personas: **full-text arm vs the O*NET-fallback baseline**, measuring
   `blind_spot_auth_grounded_pct`, `avg_spot_score`, `rec_gap_closing_pct`, overall. ~$0.3 pod.
4. **Decision gate:** full text lifts grounding/spot meaningfully over the O*NET fallback -> build the
   ATS sourcing pipeline. Flat (O*NET already covers it) -> un-truncation is noise-floor too; stop and
   conclude the model/data is the ceiling, not the evidence plumbing.

## Risks
- **Redundancy with O*NET** (the main risk) — Phase 0 exists to catch this cheaply.
- ATS coverage is partial (not every employer) — fine for a test, a real limit for production breadth.
- Scraping path (if ever used): ToS, rate limits, per-fetch cost, bot-walls (Adzuna 403, LinkedIn, etc.).
- Ingest latency: fetch full text async / at ingest, never in the user's request path.

## Effort
- Phase 0: ~0.5 session + ~$0.3 pod. **Recommended next step.**
- Full ATS sourcing (if Phase 0 passes): ~1-2 sessions (board discovery, fetch+cache, ingest wiring,
  source-coverage metric).
