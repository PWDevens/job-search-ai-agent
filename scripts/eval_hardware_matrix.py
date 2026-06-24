"""
Hardware-matrix eval: run the 3-agent pipeline across 5 simulated hardware configs
on the synthetic personas + demo data, scored by the existing rubric, into one CSV.

This is a PRE-finetuning baseline (run with --label pre). After finetuning, re-run with
--label post and diff per-scenario — greedy decoding (temp=0) makes the comparison valid.

Prereqs:
  - Jobs ingested into local ChromaDB (synthetic + demo): see scripts/ingest_jobs.py
  - Ollama reachable at --ollama-url (e.g. an SSH tunnel to the RunPod pod) with
    gemma2:9b, phi4, and phi4-mini pulled.

Usage:
  python scripts/eval_hardware_matrix.py --smoke              # fast sanity (3 personas+demo, scenario 5)
  python scripts/eval_hardware_matrix.py --label pre          # full baseline -> reports/hardware_eval_matrix_pre.csv
  python scripts/eval_hardware_matrix.py --scenarios 1,2,4    # subset of scenarios
"""
import argparse, csv, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import app.config as cfg
from app.pipeline.pipeline import run, SearchRequest
import app.agents.base as base
from tests.persona_evaluation.personas import ALL_PERSONAS, STAY_IN_FIELD_QUERIES
from tests.persona_evaluation.evaluation_scoring import ResultEvaluator
from tests.persona_evaluation.metrics_collector import SearchMetrics

# ── scenario matrix ───────────────────────────────────────────────────────────
# num_gpu: None = let Ollama use all layers; 0 = force CPU; N = cap GPU layers (~8GB).
# Scenario 4's cap is calibrated on the pod (see --phi4-8gb-layers).
def scenarios(phi4_8gb_layers: int):
    return [
        {"id": 1, "gpu": "RTX 5060 (16GB)",   "model": "gemma2:9b", "num_gpu": None,            "num_thread": None, "vram_mode": "full"},
        {"id": 2, "gpu": "RTX 5060 (16GB)",   "model": "phi4",      "num_gpu": None,            "num_thread": None, "vram_mode": "full"},
        {"id": 3, "gpu": "RTX 4070 (8GB)",    "model": "gemma2:9b", "num_gpu": None,            "num_thread": None, "vram_mode": "fits-8gb"},
        {"id": 4, "gpu": "RTX 4070 (8GB)",    "model": "phi4",      "num_gpu": phi4_8gb_layers, "num_thread": None, "vram_mode": f"partial-offload~8gb (num_gpu={phi4_8gb_layers})"},
        {"id": 5, "gpu": "Avg CPU (16GB RAM)","model": "phi4-mini", "num_gpu": 0,               "num_thread": 6,    "vram_mode": "cpu"},
    ]

CSV_FIELDS = [
    "timestamp", "label", "repeat", "scenario_id", "gpu_simulated", "llm_used", "vram_mode",
    "dataset", "persona", "variant_name", "role_description", "geo_preference", "used_resume",
    "execution_time_sec", "tokens_per_sec",
    "jobs_returned", "recommendations_returned", "blind_spots_returned",
    "avg_job_score", "avg_rec_score", "avg_spot_score", "overall_score", "quality_label",
    "tangible_rec_pct", "avg_company_citations_per_rec", "blind_spot_grounded_pct",
    "validation_resume_coach", "validation_career_strategist", "fallback_used", "usable_output",
    "error_message",
]


class _DemoPersona:
    """Minimal persona stand-in so ResultEvaluator can score the demo run."""
    name = "demo"
    target_job_titles = ["data", "engineer", "python", "machine learning", "ai", "analytics"]


def _read_resume(path):
    p = Path(path) if path else None
    return p.read_text(errors="replace") if (p and p.exists()) else None


def build_rows(smoke: bool, variant: str = "switching", all_variants: bool = False):
    """(persona, dataset, variant_name, role, geo, resume_text) tuples.

    variant="switching"  -> persona pivots to analytics (search_variants)
    variant="stayinfield"-> persona searches its own profession (geo=None, nationwide)
    all_variants=True (switching only) -> exercise ALL search_variants per persona
        (MJ1: the personas define 3 each — no-resume + alternate roles — previously unused).
    """
    rows = []
    personas = ALL_PERSONAS[:3] if smoke else ALL_PERSONAS
    for p in personas:
        if variant == "stayinfield":
            rows.append((p, "synthetic", "stayinfield", STAY_IN_FIELD_QUERIES[p.name], None,
                         _read_resume(p.resume_path)))
        else:
            variants = p.search_variants if all_variants else p.search_variants[:1]
            for v in variants:
                resume = _read_resume(p.resume_path) if v.use_resume else None
                rows.append((p, "synthetic", v.name, v.role_description, v.geo_preference, resume))
    # demo row (uses the demo resume + demo jobs ingested into the same collection)
    rows.append((
        _DemoPersona(), "demo", "demo",
        "Data Engineer AI/ML Python Flask ChromaDB federal government contractor",
        "Washington DC",
        _read_resume(ROOT / "data" / "demo" / "demo_resume.txt"),
    ))
    return rows


def submetrics(scores):
    """Per-quality sub-metrics from the rubric's per-item score objects."""
    recs = scores["rec_scores"]
    spots = scores["spot_scores"]
    tangible_pct = round(100 * sum(r.is_tangible for r in recs) / len(recs), 1) if recs else 0.0
    avg_cites    = round(sum(r.company_citations for r in recs) / len(recs), 2) if recs else 0.0
    grounded_pct = round(100 * sum(1 for s in spots if s.job_citations > 0) / len(spots), 1) if spots else 0.0
    return tangible_pct, avg_cites, grounded_pct


def run_row(scn, persona, dataset, variant_name, role, geo, resume_text, repeat=1):
    """One pipeline run under one scenario → one CSV-row dict."""
    base.LAST_TIMING.clear()
    t0 = time.monotonic()
    err = None
    try:
        result = run(SearchRequest(role_description=role, geo_preference=geo, resume_text=resume_text))
        d = result.as_dict()
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        d = {"top_jobs": [], "resume_recs": [], "blind_spots": [], "agent_validation": {}, "raw_agent_output": {}}
    elapsed = round(time.monotonic() - t0, 2)

    scores = ResultEvaluator.evaluate_search_result(d, persona)
    tangible_pct, avg_cites, grounded_pct = submetrics(scores)

    av = d.get("agent_validation", {})
    n_jobs = len(d.get("top_jobs", []))
    n_recs = len(d.get("resume_recs", []))
    n_spots = len(d.get("blind_spots", []))
    # MJ2: honest "usable_output" — grounding passes trivially on EMPTY output, so
    # validation alone is misleading. A row is only usable if it produced real,
    # job-grounded content (non-empty jobs + recs + spots).
    usable_output = bool(n_jobs and n_recs and n_spots and not err)
    m = SearchMetrics(
        timestamp=datetime.now().isoformat(),
        persona=getattr(persona, "name", "?"),
        search_variant=variant_name, search_query=role, geo_preference=geo,
        used_resume=bool(resume_text), execution_time_sec=elapsed,
        jobs_returned=n_jobs,
        jobs_score_avg=0.0,
        recommendations_returned=n_recs,
        blind_spots_returned=n_spots,
        validation_resume_coach=av.get("resume_coach", False),
        validation_career_strategist=av.get("career_strategist", False),
        fallback_used=any(not v for v in av.values()) if av else True,
        error_message=err, raw_agent_output_length=0,
    )

    return {
        "timestamp": m.timestamp, "label": LABEL, "repeat": repeat,
        "scenario_id": scn["id"], "gpu_simulated": scn["gpu"], "llm_used": scn["model"],
        "vram_mode": scn["vram_mode"], "dataset": dataset, "persona": m.persona,
        "variant_name": variant_name,
        "role_description": role, "geo_preference": geo or "", "used_resume": m.used_resume,
        "execution_time_sec": m.execution_time_sec,
        "tokens_per_sec": round(base.LAST_TIMING.get("tokens_per_sec"), 1) if base.LAST_TIMING.get("tokens_per_sec") else "",
        "jobs_returned": m.jobs_returned,
        "recommendations_returned": m.recommendations_returned,
        "blind_spots_returned": m.blind_spots_returned,
        "avg_job_score": round(scores["avg_job_score"], 2),
        "avg_rec_score": round(scores["avg_rec_score"], 2),
        "avg_spot_score": round(scores["avg_spot_score"], 2),
        "overall_score": round(scores["overall_score"], 2),
        "quality_label": scores["quality_label"],
        "tangible_rec_pct": tangible_pct,
        "avg_company_citations_per_rec": avg_cites,
        "blind_spot_grounded_pct": grounded_pct,
        "validation_resume_coach": m.validation_resume_coach,
        "validation_career_strategist": m.validation_career_strategist,
        "fallback_used": m.fallback_used,
        "usable_output": usable_output,
        "error_message": err or "",
    }


def main():
    global LABEL
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="pre", help="output suffix: hardware_eval_matrix_<label>.csv")
    ap.add_argument("--ollama-url", default=cfg.OLLAMA_BASE_URL, help="Ollama endpoint (e.g. SSH tunnel)")
    ap.add_argument("--scenarios", default="1,2,3,4,5", help="comma list of scenario ids")
    ap.add_argument("--smoke", action="store_true", help="3 personas + demo, scenario 5 only")
    ap.add_argument("--phi4-8gb-layers", type=int, default=30, help="GPU layers for the simulated-8GB phi4 run")
    ap.add_argument("--variant", choices=["switching", "stayinfield"], default="switching",
                    help="persona query set: switching->analytics (default) or stayinfield")
    ap.add_argument("--temp", type=float, default=0.0,
                    help="Ollama temperature: 0.0 greedy (synthetic baselines) | 0.2 reg (Adzuna)")
    ap.add_argument("--all-variants", action="store_true",
                    help="MJ1: run all 3 search_variants per persona (switching only)")
    ap.add_argument("--repeats", type=int, default=1,
                    help="MJ4: run each row N times (variance for non-greedy/Adzuna runs)")
    args = ap.parse_args()
    LABEL = args.label

    # Endpoint + temperature (base.chat reads cfg dynamically).
    cfg.OLLAMA_TEMPERATURE = args.temp
    cfg.OLLAMA_BASE_URL = args.ollama_url

    all_scn = scenarios(args.phi4_8gb_layers)
    want = {1,2,3,4,5} if not args.smoke else {5}
    if args.scenarios and not args.smoke:
        want = {int(x) for x in args.scenarios.split(",")}
    scns = [s for s in all_scn if s["id"] in want]
    rows_spec = build_rows(args.smoke, args.variant, args.all_variants)

    out = ROOT / "reports" / f"hardware_eval_matrix_{LABEL}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    total = len(scns) * len(rows_spec) * args.repeats
    print(f"Matrix: {len(scns)} scenario(s) x {len(rows_spec)} rows x {args.repeats} rep = {total} runs -> {out}")
    print(f"Ollama: {cfg.OLLAMA_BASE_URL} | temp={cfg.OLLAMA_TEMPERATURE} | variant={args.variant} | all_variants={args.all_variants}\n")

    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        i = 0
        for scn in scns:
            # Apply scenario to config (base.chat picks these up live).
            cfg.AGENT_MODEL    = scn["model"]
            cfg.OLLAMA_NUM_GPU = scn["num_gpu"]
            cfg.OLLAMA_NUM_THREAD = scn["num_thread"]
            for persona, dataset, variant_name, role, geo, resume in rows_spec:
              for rep in range(1, args.repeats + 1):
                i += 1
                who = getattr(persona, "name", "?")
                print(f"[{i}/{total}] scn{scn['id']} {scn['gpu']} {scn['model']} | {dataset}/{who}/{variant_name} r{rep} ...", flush=True)
                row = run_row(scn, persona, dataset, variant_name, role, geo, resume, repeat=rep)
                w.writerow(row); f.flush()
                tag = row["error_message"] or f"{row['overall_score']} ({row['quality_label']}) {row['execution_time_sec']}s {row['tokens_per_sec']}tok/s"
                print(f"      -> {tag}")

    print(f"\nDone. {total} rows -> {out}")


if __name__ == "__main__":
    main()
