"""
Plot the 2x2 eval from reports/eval_aggregate.csv.

Produces a 2x2 grid (one subplot per cell: switching/stayinfield x synthetic/adzuna),
each showing mean overall_score for the 3 hardware lines (CPU/phi4-mini,
AvgGPU/gemma2:9b, ModernGPU/phi4) at the current version.

This is the baseline snapshot. As you add post-finetuning runs, tag them with a
`version` column in the aggregate and this becomes a line-per-hardware chart over
versions — the 4-chart README story.

    python scripts/plot_eval.py   ->  reports/eval_2x2_baseline.png
"""
import csv, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
AGG = ROOT / "reports" / "eval_aggregate.csv"

CELLS = ["switching/synthetic", "switching/adzuna", "stayinfield/synthetic", "stayinfield/adzuna"]
LINES = [("CPU\nphi4-mini", "5", "#d9772b"), ("Avg GPU\ngemma2:9b", "3", "#2b8cbe"),
         ("Modern GPU\nphi4", "2", "#41ab5d")]


def mean(rows, k):
    v = [float(r[k]) for r in rows if r.get(k) not in ("", None)]
    return st.mean(v) if v else 0.0


def main():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: pip install matplotlib", file=sys.stderr); sys.exit(1)

    rows = list(csv.DictReader(open(AGG, encoding="utf-8")))
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    fig.suptitle("Job-Search AI — 2x2 baseline (mean overall_score, 0-4)\n"
                 "CPU/phi4-mini · Avg GPU/gemma2:9b · Modern GPU/phi4", fontsize=12)

    for ax, cell in zip(axes.flat, CELLS):
        labels, vals, colors = [], [], []
        for name, sid, color in LINES:
            c = [r for r in rows if r["cell"] == cell and r["scenario_id"] == sid]
            labels.append(name); vals.append(round(mean(c, "overall_score"), 2)); colors.append(color)
        bars = ax.bar(labels, vals, color=colors)
        ax.set_title(cell, fontsize=11)
        ax.set_ylim(0, 4); ax.set_ylabel("overall_score")
        ax.axhspan(0, 1.5, color="#f0f0f0", zorder=0)  # "Poor" band
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width()/2, v + 0.05, f"{v:.2f}", ha="center", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = ROOT / "reports" / "eval_2x2_baseline.png"
    fig.savefig(out, dpi=130)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
