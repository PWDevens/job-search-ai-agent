"""
Before/after 2x2 chart: old (buggy) eval vs fixed eval, per cell, per hardware line.
Reads the local CSVs and writes reports/eval_2x2_beforeafter.png.

    python scripts/plot_beforeafter.py
"""
import csv, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
R = ROOT / "reports" / "hardware_eval_matrix_"

# cell -> (old csv label, [fixed csv labels merged])
CELLS = {
    "switching / synthetic":   ("pre",              ["fix_swsyn_gpu", "fix_swsyn_cpu"]),
    "switching / adzuna":      ("adzuna_switch",    ["fix_swadz_gpu", "fix_swadz_cpu"]),
    "stayinfield / synthetic": ("pre_stayfield",    ["fix_sfsyn_gpu", "fix_sfsyn_cpu"]),
    "stayinfield / adzuna":    ("adzuna_stayfield", ["fix_sfadz_gpu", "fix_sfadz_cpu"]),
}
LINES = [("CPU\nphi4-mini", "5"), ("AvgGPU\ngemma2:9b", "3"), ("ModGPU\nphi4", "2")]


def load(label):
    p = Path(f"{R}{label}.csv")
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def mean(rows, sid, k="overall_score"):
    v = [float(r[k]) for r in rows if r.get("scenario_id") == sid and r.get(k) not in ("", None)]
    return st.mean(v) if v else 0.0


def main():
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("pip install matplotlib", file=sys.stderr); sys.exit(1)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Eval before (buggy) vs after (fixed) — mean overall_score (0-4)", fontsize=13)
    x = np.arange(len(LINES)); w = 0.38
    for ax, (cell, (old_l, fix_ls)) in zip(axes.flat, CELLS.items()):
        old = load(old_l)
        fix = [r for l in fix_ls for r in load(l)]
        old_v = [round(mean(old, sid), 2) for _, sid in LINES]
        fix_v = [round(mean(fix, sid), 2) for _, sid in LINES]
        b1 = ax.bar(x - w/2, old_v, w, label="before", color="#bdbdbd")
        b2 = ax.bar(x + w/2, fix_v, w, label="after",  color="#41ab5d")
        ax.set_title(cell, fontsize=11); ax.set_ylim(0, 4)
        ax.set_xticks(x); ax.set_xticklabels([n for n, _ in LINES], fontsize=9)
        ax.axhspan(0, 1.5, color="#f5f5f5", zorder=0)  # "Poor" band
        ax.axhline(1.5, color="#999", lw=0.5, ls="--")
        for bars in (b1, b2):
            for b in bars:
                ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.05, f"{b.get_height():.2f}",
                        ha="center", fontsize=8)
        ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = ROOT / "reports" / "eval_2x2_beforeafter.png"
    fig.savefig(out, dpi=130)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
