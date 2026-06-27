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
import argparse, csv, os, sys, time, json
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
        {"id": 6, "gpu": "GPU",               "model": "gemma4:12b-it-q4_K_M","num_gpu": None,   "num_thread": None, "vram_mode": "full"},  # bake-off: gemma4 12B dense (fails career_strategist)
        {"id": 7, "gpu": "GPU",               "model": "gemma3:12b-it-q4_K_M","num_gpu": None,   "num_thread": None, "vram_mode": "full"},  # bake-off: gemma3 12B dense
        {"id": 8, "gpu": "GPU",               "model": "gemma4:26b-a4b-it-qat","num_gpu": None,  "num_thread": None, "vram_mode": "full"}, # bake-off: gemma4 26B MoE (4B active)
        {"id": 9, "gpu": "GPU",               "model": "llama3.1:8b","num_gpu": None,            "num_thread": None, "vram_mode": "full"},  # production GPU model (bake-off winner)
    ]

CSV_FIELDS = [
    "timestamp", "label", "scenario_id", "gpu_simulated", "llm_used", "vram_mode",
    "dataset", "persona", "role_description", "geo_preference", "used_resume",
    "execution_time_sec", "tokens_per_sec",
    "jobs_returned", "recommendations_returned", "blind_spots_returned",
    "avg_job_score", "avg_rec_score", "avg_spot_score", "overall_score", "quality_label",
    "tangible_rec_pct", "avg_company_citations_per_rec", "blind_spot_grounded_pct",
    "blind_spot_auth_grounded_pct", "rec_gap_closing_pct", "rubric_version",
    "validation_resume_coach", "validation_career_strategist", "fallback_used",
    "error_message",
]


class _DemoPersona:
    """Minimal persona stand-in so ResultEvaluator can score the demo run."""
    name = "demo"
    target_job_titles = ["data", "engineer", "python", "machine learning", "ai", "analytics"]


def _read_resume(path):
    p = Path(path) if path else None
    return p.read_text(errors="replace") if (p and p.exists()) else None


def build_rows(smoke: bool, variant: str = "switching"):
    """(persona_obj_or_demo, dataset, role, geo, resume_text, variant) tuples.

    variant="switching"  -> persona pivots to analytics (existing variant[0])
    variant="stayinfield"-> persona searches its own profession (geo=None, nationwide)
    """
    rows = []
    personas = ALL_PERSONAS[:3] if smoke else ALL_PERSONAS
    for p in personas:
        if variant == "stayinfield":
            role, geo = STAY_IN_FIELD_QUERIES[p.name], None
        else:
            v = p.search_variants[0]
            role, geo = v.role_description, v.geo_preference
        rows.append((p, "synthetic", role, geo, _read_resume(p.resume_path), variant))
    # demo row (uses the demo resume + demo jobs ingested into the same collection)
    rows.append((
        _DemoPersona(), "demo",
        "Data Engineer AI/ML Python Flask ChromaDB federal government contractor",
        "Washington DC",
        _read_resume(ROOT / "data" / "demo" / "demo_resume.txt"),
        variant,
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


def run_row(scn, persona, dataset, role, geo, resume_text, variant="switching"):
    """One pipeline run under one scenario → one CSV-row dict."""
    base.LAST_TIMING.clear()
    t0 = time.monotonic()
    err = None
    try:
        mode = "switch" if variant == "switching" else "stay"
        result = run(SearchRequest(role_description=role, geo_preference=geo,
                                   resume_text=resume_text, mode=mode))
        d = result.as_dict()
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        d = {"top_jobs": [], "resume_recs": [], "blind_spots": [], "agent_validation": {}, "raw_agent_output": {}}
    elapsed = round(time.monotonic() - t0, 2)

    # ponytail: pass variant to scoring so it uses appropriate targets
    scores = ResultEvaluator.evaluate_search_result(d, persona, variant)
    tangible_pct, avg_cites, grounded_pct = submetrics(scores)

    # Raw-output persistence (opt-in EVAL_PERSIST_RAW): bank the inputs so ANY future rubric
    # version re-scores offline for $0 (no pod). Re-score via evaluate_search_result(result, persona, variant).
    if os.getenv("EVAL_PERSIST_RAW", "").lower() in ("1", "true", "yes"):
        try:
            out = os.getenv("EVAL_OUT", "reports/eval_compare.csv")
            raw_path = (out[:-4] if out.endswith(".csv") else out) + ".raw.jsonl"
            with open(raw_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"persona": getattr(persona, "name", "?"), "variant": variant,
                                     "dataset": dataset, "result": d}, default=str) + "\n")
        except Exception:
            pass

    av = d.get("agent_validation", {})
    m = SearchMetrics(
        timestamp=datetime.now().isoformat(),
        persona=getattr(persona, "name", "?"),
        search_variant="v0", search_query=role, geo_preference=geo,
        used_resume=bool(resume_text), execution_time_sec=elapsed,
        jobs_returned=len(d.get("top_jobs", [])),
        jobs_score_avg=0.0,
        recommendations_returned=len(d.get("resume_recs", [])),
        blind_spots_returned=len(d.get("blind_spots", [])),
        validation_resume_coach=av.get("resume_coach", False),
        validation_career_strategist=av.get("career_strategist", False),
        fallback_used=any(not v for v in av.values()) if av else True,
        error_message=err, raw_agent_output_length=0,
    )

    return {
        "timestamp": m.timestamp, "label": LABEL,
        "scenario_id": scn["id"], "gpu_simulated": scn["gpu"], "llm_used": scn["model"],
        "vram_mode": scn["vram_mode"], "dataset": dataset, "persona": m.persona,
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
        "blind_spot_auth_grounded_pct": scores.get("blind_spot_auth_grounded_pct") if scores.get("blind_spot_auth_grounded_pct") is not None else "",
        "rec_gap_closing_pct": scores.get("rec_gap_closing_pct") if scores.get("rec_gap_closing_pct") is not None else "",
        "rubric_version": scores.get("rubric_version", "v1"),
        "validation_resume_coach": m.validation_resume_coach,
        "validation_career_strategist": m.validation_career_strategist,
        "fallback_used": m.fallback_used,
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
    rows_spec = build_rows(args.smoke, args.variant)

    out = ROOT / "reports" / f"hardware_eval_matrix_{LABEL}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    total = len(scns) * len(rows_spec)
    print(f"Matrix: {len(scns)} scenario(s) x {len(rows_spec)} rows = {total} runs -> {out}")
    print(f"Ollama: {cfg.OLLAMA_BASE_URL} | temp={cfg.OLLAMA_TEMPERATURE} | variant={args.variant}\n")

    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        i = 0
        for scn in scns:
            # Apply scenario to config (base.chat picks these up live).
            cfg.AGENT_MODEL    = scn["model"]
            cfg.OLLAMA_NUM_GPU = scn["num_gpu"]
            cfg.OLLAMA_NUM_THREAD = scn["num_thread"]
            for persona, dataset, role, geo, resume, variant in rows_spec:
                i += 1
                who = getattr(persona, "name", "?")
                print(f"[{i}/{total}] scn{scn['id']} {scn['gpu']} {scn['model']} | {dataset}/{who} ...", flush=True)
                row = run_row(scn, persona, dataset, role, geo, resume, variant)
                w.writerow(row); f.flush()
                tag = row["error_message"] or f"{row['overall_score']} ({row['quality_label']}) {row['execution_time_sec']}s {row['tokens_per_sec']}tok/s"
                print(f"      -> {tag}")

    print(f"\nDone. {total} rows -> {out}")


if __name__ == "__main__":
    main()
