# Job-Search AI Agent — v2 specs (draft)

Short capture of the v2 direction. Detailed GitHub-facing notes will land in `v2.md` later.
Builds on v1 (`v1.md`) and the validated levers: full posting text (+0.41) and base-model quality (+0.76).

## Theme
v1 proved the **grounding** levers. v2's job is to (a) confirm they generalize on a new domain, and
(b) ship the product leap that **sidesteps v1's one weakness — corpus-bound discovery** — by letting
users bring their own target jobs.

---

## Phase 1 — USAJobs validation (cheap, confirms the foundation)
- **Goal:** prove v1's findings (full text + model) hold on a third, independent corpus beyond
  ATS-tech and synthetic. Cross-domain confirmation, **not** a production source (federal jobs are a
  narrow slice of user targets).
- **Work:** add a 4th adapter to `app/pipeline/ats_sources.py` for the USAJobs API (free API key;
  idiosyncratic schema — series/grade codes). Postings are rigidly structured (explicit
  "Qualifications") → high requirements-coverage → a clean stress test of the resume coach.
- **Done when:** an A/B on USAJobs personas shows the full-text + model lifts reproduce (directionally)
  the v1 magnitudes. If they hold, the foundation is trusted; if not, investigate before building on it.

## Phase 2 — "Bring your own jobs" (the product leap)
A second UI tab: the user uploads a CSV of jobs they're interested in; the tool **prioritizes that
list** and tailors resume + career-strategy output to those specific targets.

**Why it's strategically right:** discovery/retrieval was the one dimension v1 never improved
(corpus-limited, noise-floor on every tweak). This sidesteps it — the user supplies real, current,
relevant targets — and **maximizes the proven grounding lever**: uploaded postings are exactly the
full-text requirements the agents ground in. It's "the +0.41 full-text win, but the user brings the text."

**Reuses v1 plumbing:** CSV ingest (`scripts/ingest_jobs.py`), section parser (`app/pipeline/sections.py`),
the 3 agents (already consume `requirements_text`).

**New work:**
- Upload tab + robust **column-mapping** (LinkedIn/Indeed/tracker exports have wildly varying headers).
- A **"user-jobs mode"** in the pipeline where the uploaded set *is* the candidate pool — the matcher
  *ranks* it against the resume instead of retrieving from the corpus.
- **Full-text fallback:** if a row has only a URL, fetch the JD (clean for ATS URLs; LinkedIn/Indeed
  are bot-walled → prompt the user to paste the description).
- **Per-job output** (not aggregate): for each posting, its own gap analysis + recs.
- Local-first (uploaded jobs + resume are sensitive — keep on-device, matches the v1 ethos).

**Headline output — Apply-priority scoring:** per uploaded job, a 2-axis score —
*fit* (resume ↔ requirements) × *gap-effort* (how much to close) — rendered as **apply now / stretch /
skip.** This is the core JTBD ("prioritize what to apply to") as a concrete deliverable.

## Phase 3 — follow-on features (ride the upload feature)
- **Gap-closing roadmap:** aggregate blind spots across the uploaded list → "the 3 skills that unlock
  the most of your target jobs" → one prioritized learning plan.
- **Per-job resume tailoring:** tailored bullet suggestions + the ATS keywords *that* posting screens for.
- **(Stretch) Outreach / cover-letter drafts** grounded in the specific JD. Watch scope.

---

## Sequencing
USAJobs validation → upload feature (with apply-priority scoring as the headline) → gap-closing roadmap.
Embedding/reranker tuning stays **shelved** (v1 assessment: little juice for the squeeze) unless the
upload feature surfaces a concrete retrieval need.

## Open items
- Front-end: mockup to come from the user; align tab/UX to it.
- README.md still cites the retired models (Phi-4-mini/Llama-3.1) — refresh to qwen3:4b/gemma3:12b.
