# Spec — Nesta "Mapping Career Causeways" as a switcher-pivot engine

Status: PROPOSED (for consideration). Source: GraphRAG architecture review, 2026-06-28.

## Why (JTBD fit)
North-star JTBD = "prioritize what to apply to + improve my chances." Today we serve the
**stay-in-field** path well (O*NET authoritative requirements ground blind spots + recs) but the
**switcher** path weakly: we match the user's *stated* target role, we don't *recommend viable
adjacent roles*. Nesta Causeways fills exactly that gap — it answers "given where I am, where can I
realistically go?" with math, not vibes.

## What it provides (don't rebuild — import)
Nesta's *Mapping Career Causeways* (open dataset, 2020) pre-computes, for ~1600 ESCO occupations:
- **Transition feasibility** between occupation pairs from skills/work-context overlap (a 0-1 score).
- **"Safe and desirable" transitions** — feasible AND not a pay/quality downgrade.
- **Automation/displacement risk** per occupation.
So the agent can query: *"top-K adjacent occupations to X with high feasibility, low displacement
risk"* — a recommendation engine, not a lookup. This is the piece the proposal is right about.

## The one hard problem: taxonomy crosswalk
Causeways is **ESCO-based and UK-labour-market-calibrated**; our anchor is **O*NET-SOC (US)**.
- Need an ESCO↔O*NET-SOC crosswalk (BLS/ESCO publish partial mappings; or embed-match occupation
  titles with `embed_texts`, same trick as `occupation_for`, with a confidence floor).
- Feasibility scores are UK-derived → treat as **directional**, not US-precise. Surface as
  "adjacent roles to explore," never as a hard ranking.

## Integration design (small, additive — touches nothing we retired)
1. **Data**: download Causeways transition table → `data/causeways/transitions.parquet`
   (occ_a, occ_b, feasibility, is_safe_desirable, risk). One-time ingest script.
2. **Module** `app/skills/causeways.py`:
   - `adjacent_occupations(title, k=3, min_feasibility=0.5, max_risk=...) -> list[{title, soc, feasibility, risk}]`
   - reuses `occupation_for(title)` to resolve the user's current occupation → SOC → ESCO via crosswalk.
3. **Surface in `career_strategist`** (switch mode only): inject a "Adjacent roles worth considering
   (feasibility-ranked)" block, parallel to the existing authoritative-gaps block. For each suggested
   pivot, the existing O*NET layer already gives its requirements → instant gap list per pivot.
4. **Gate**: `CAUSEWAYS=1`, default off, A/B like every other lever.

## Eval (must clear the ESCO bar — don't repeat that mistake)
- New metric: **pivot relevance** — do recommended adjacent occupations match the persona's
  `target_job_titles` / expected pivots? (switch personas already encode intended targets.)
- New switch personas where the *interesting* answer is a non-obvious adjacency (e.g. claims-adjuster
  → underwriting), so the metric can distinguish "real recommendation engine" from "returns synonyms."
- Decision gate: ship only if it lifts the switch cell's job/spot dimensions *and* generalizes — the
  exact gate ESCO failed (+0.026 noise). No generalizing lift → shelve, same as ESCO.

## Effort / risk
- Effort: **medium** — ingest + crosswalk (the crosswalk is the real work) + a query fn + one
  strategist block + an eval metric + personas. ~1-2 focused sessions.
- Risk: crosswalk precision (UK ESCO → US SOC) and UK-calibrated feasibility transferring to US.
  Mitigate by labelling output "explore," and validating the crosswalk on the known persona set first.

## Relation to the rest
- Complements, doesn't replace, the O*NET authoritative-requirements anchor (the +0.49 win).
- Independent of the verification-pass work (the current A/B's leading lever) — they compose:
  Causeways picks *which* occupations, the O*NET layer + verification ground the gaps *within* each.
- Does NOT bring back ESCO-as-prompt-vocabulary (the retired, ungroundable path). Causeways uses ESCO
  only as occupation *node IDs* for the transition math, never as skill labels fed to the LLM.
