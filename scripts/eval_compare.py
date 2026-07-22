#!/usr/bin/env python3
"""
Retrieval vs Few-shot comparison harness.

Runs the persona eval under two configs (retrieval-quality improvement vs prompt-few-shot
improvement) with --repeats N and prints a mean±sd comparison table to the console.

Usage:
  python scripts/eval_compare.py --repeats 3 [--smoke] [--variant switching|stayinfield]
                                 [--configs baseline,retrieval,fewshot] [--scenario 5]
"""
import argparse, csv, sys, statistics
from datetime import datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import app.config as cfg
from scripts.eval_hardware_matrix import build_rows, run_row, submetrics, scenarios, CSV_FIELDS

# Metric names we track for comparison
HEADLINE_METRICS = [
    "overall_score",
    "avg_job_score",
    "avg_rec_score",
    "avg_spot_score",
    "blind_spot_grounded_pct",
    "blind_spot_auth_grounded_pct",
    "tangible_rec_pct",
    "fallback_used",  # we'll convert to pct
    "jobs_returned",
]


def apply_config(cfg_name):
    """Apply configuration knobs for the given config."""
    if cfg_name == "baseline":
        cfg.RERANK_PASSES = 1
        cfg.PROMPT_FEWSHOT = False
    elif cfg_name == "retrieval":
        cfg.RERANK_PASSES = 3
        cfg.PROMPT_FEWSHOT = False
    elif cfg_name == "fewshot":
        cfg.RERANK_PASSES = 1
        cfg.PROMPT_FEWSHOT = True
    else:
        raise ValueError(f"Unknown config: {cfg_name}")


def run_comparison(scn, rows_spec, repeats, configs, label):
    """Run the comparison across all configs and repeats.

    Returns:
        tuple of (results, all_rows) where:
        - results: dict[config_name] -> dict[metric_name] -> list[per-repeat means]
        - all_rows: list of raw CSV_FIELDS-keyed dicts, one per run
    """
    results = defaultdict(lambda: defaultdict(list))
    all_rows = []
    total_runs = len(configs) * repeats * len(rows_spec)
    run_count = 0

    for config in configs:
        apply_config(config)
        for repeat in range(repeats):
            # ponytail: set LABEL global for run_row
            import scripts.eval_hardware_matrix
            scripts.eval_hardware_matrix.LABEL = label

            # Accumulate metrics for this repeat
            repeat_metrics = defaultdict(list)

            for persona, dataset, role, geo, resume, row_variant in rows_spec:
                run_count += 1
                who = getattr(persona, "name", "?")
                print(
                    f"[{run_count}/{total_runs}] {config} repeat {repeat+1}/{repeats} | "
                    f"{dataset}/{who} ...",
                    flush=True,
                )

                row = run_row(scn, persona, dataset, role, geo, resume, row_variant)

                # ponytail: reuse the existing 'label' column to tag config+repeat so we don't widen CSV_FIELDS.
                row["label"] = f"compare-{config}-r{repeat+1}"
                all_rows.append(row)

                # Accumulate metrics
                for metric in HEADLINE_METRICS:
                    if metric == "fallback_used":
                        # Convert bool to int
                        val = 1 if row.get(metric) else 0
                    else:
                        val = row.get(metric, 0)
                        if val == "":
                            val = 0
                    repeat_metrics[metric].append(float(val))

                tag = row.get("error_message") or f"{row.get('overall_score', 0)}"
                print(f"      -> {tag}")

            # Compute per-repeat means
            for metric, values in repeat_metrics.items():
                mean_val = (
                    statistics.mean(values) if values else 0.0
                )
                # Special handling: convert fallback_used back to percentage
                if metric == "fallback_used":
                    mean_val = mean_val * 100  # 0.0-1.0 to 0-100
                elif metric == "jobs_returned":
                    # jobs_returned stays as-is (mean of counts)
                    pass

                results[config][metric].append(mean_val)

    return results, all_rows


def format_metric(mean, sd, metric_name):
    """Format a metric as 'mean ± sd' with appropriate precision."""
    if metric_name.endswith("pct") or "fallback" in metric_name:
        # Percentages: 1 decimal
        return f"{mean:.1f} ± {sd:.1f}"
    else:
        # Scores: 2 decimals; counts: 1 decimal
        if "score" in metric_name:
            return f"{mean:.2f} ± {sd:.2f}"
        else:
            return f"{mean:.1f} ± {sd:.1f}"


def print_comparison_table(results, configs, variant, repeats, scn, n_rows):
    """Print a formatted comparison table to console."""
    # Print headers
    print(
        f"\nRetrieval vs Few-shot comparison  | repeats={repeats} | "
        f"variant={variant} | scenario={scn['id']} ({scn['model']}) | "
        f"rows={n_rows}\n"
    )
    rerank_model = cfg.RERANK_MODEL or "none"
    print(f"RERANK_MODEL={rerank_model}  (note: 'none' => retrieval config is a no-op)\n")

    # Build table
    header = "metric" + "".join(f"{c:>20}" for c in configs)
    print(header)
    print("-" * (len(header) + 10))

    # Compute mean±sd for each metric across repeats
    metric_best = {}  # metric -> (best_config, best_mean)
    for metric in HEADLINE_METRICS:
        row_data = [metric]
        best_mean = -999
        best_config = None

        for config in configs:
            values = results.get(config, {}).get(metric, [])
            if not values:
                row_data.append("N/A".rjust(20))
                continue

            mean_val = statistics.mean(values)
            sd_val = statistics.stdev(values) if len(values) > 1 else 0.0

            # Track best (only for certain metrics)
            if metric == "overall_score" and mean_val > best_mean:
                best_mean = mean_val
                best_config = config

            formatted = format_metric(mean_val, sd_val, metric)
            row_data.append(formatted.rjust(20))

        if metric == "overall_score":
            metric_best[metric] = (best_config, best_mean)

        print("  ".join(row_data))

    # Final line: best config
    print("-" * (len(header) + 10))
    if "overall_score" in metric_best:
        best_config, best_mean = metric_best["overall_score"]
        # Get baseline mean for delta
        baseline_mean = (
            statistics.mean(results.get("baseline", {}).get("overall_score", []))
            if "baseline" in results and results["baseline"].get("overall_score")
            else 0.0
        )
        delta = best_mean - baseline_mean
        delta_sign = "+" if delta >= 0 else ""
        print(f"Best overall_score: {best_config} ({best_mean:.2f})   delta vs baseline: {delta_sign}{delta:.2f}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of repeats per config (default 3)",
    )
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="Quick run: 3 personas + demo, scenario 5 only",
    )
    ap.add_argument(
        "--variant",
        choices=["switching", "stayinfield"],
        default="switching",
        help="Persona query set: switching (default) or stayinfield",
    )
    ap.add_argument(
        "--configs",
        default="baseline,retrieval,fewshot",
        help="Comma-separated list of configs to run (default: baseline,retrieval,fewshot)",
    )
    ap.add_argument(
        "--scenario",
        type=int,
        default=5,
        help="Hardware scenario ID (default 5 = CPU/phi4-mini)",
    )
    ap.add_argument(
        "--ollama-url",
        default=cfg.OLLAMA_BASE_URL,
        help="Ollama endpoint",
    )
    ap.add_argument(
        "--phi4-8gb-layers",
        type=int,
        default=30,
        help="GPU layers for simulated 8GB phi4 run",
    )
    ap.add_argument(
        "--temp",
        type=float,
        default=0.0,
        help="Ollama temperature (0.0 greedy / 0.2 regular)",
    )
    ap.add_argument("--model", default=None,
                    help="Override the scenario's agent model (e.g. qwen2.5:32b) — for base-model A/Bs")

    args = ap.parse_args()

    # Apply base config
    cfg.OLLAMA_BASE_URL = args.ollama_url
    cfg.OLLAMA_TEMPERATURE = args.temp

    # Parse configs
    want_configs = [c.strip() for c in args.configs.split(",")]

    # Get scenario
    all_scn = scenarios(args.phi4_8gb_layers)
    scn = next((s for s in all_scn if s["id"] == args.scenario), None)
    if not scn:
        print(f"ERROR: Scenario {args.scenario} not found", file=sys.stderr)
        sys.exit(1)

    # Apply scenario to config (--model overrides for base-model A/Bs)
    cfg.AGENT_MODEL = args.model or scn["model"]
    cfg.OLLAMA_NUM_GPU = scn["num_gpu"]
    cfg.OLLAMA_NUM_THREAD = scn["num_thread"]

    # Build rows
    rows_spec = build_rows(args.smoke, args.variant)
    print(
        f"Comparison: {len(want_configs)} config(s) x {args.repeats} repeat(s) x "
        f"{len(rows_spec)} rows = {len(want_configs) * args.repeats * len(rows_spec)} runs\n"
    )

    # Run comparison
    results, all_rows = run_comparison(
        scn,
        rows_spec,
        args.repeats,
        want_configs,
        label="compare",
    )

    # Print table
    print_comparison_table(results, want_configs, args.variant, args.repeats, scn, len(rows_spec))

    # Write CSV (one row per repeat-config-persona run). EVAL_OUT lets parallel
    # runs (same variant, different corpus) write to distinct files without racing.
    import os
    out = Path(os.environ["EVAL_OUT"]) if os.environ.get("EVAL_OUT") \
        else ROOT / "reports" / f"eval_compare_{args.variant}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in all_rows:
            w.writerow(row)
    print(f"\nRaw results written to {out} ({len(all_rows)} rows)")


if __name__ == "__main__":
    main()
