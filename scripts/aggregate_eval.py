"""
Aggregate all reports/hardware_eval_matrix_*.csv into one tidy CSV for analysis.

Adds `variant` (switching|stayinfield), `source` (synthetic|adzuna), and `cell`
columns derived from the run label, so the 2x2 is sliceable directly. Merges the
local CPU scenario-5 run into the #4 cell (and drops the pod's partial scn-5 rows)
so scenario 5 isn't double-counted. Skips the smoke test.

    python scripts/aggregate_eval.py   ->  reports/eval_aggregate.csv
"""
import csv, glob, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REP = ROOT / "reports"

# label -> (variant, source). scn5 local run normalizes into the adzuna_stayfield cell.
LABEL_MAP = {
    "pre":                    ("switching",   "synthetic"),
    "adzuna_switch":          ("switching",   "adzuna"),
    "pre_stayfield":          ("stayinfield", "synthetic"),
    "adzuna_stayfield":       ("stayinfield", "adzuna"),
    "adzuna_stayfield_scn5":  ("stayinfield", "adzuna"),
}
SCN5_OVERRIDE_LABEL = "adzuna_stayfield_scn5"  # local CPU re-run of scn5 for #4
SCN5_TARGET_LABEL   = "adzuna_stayfield"


def main():
    files = sorted(REP.glob("hardware_eval_matrix_*.csv"))
    rows, header = [], None
    have_scn5_override = any(f.stem.endswith(SCN5_OVERRIDE_LABEL) for f in files)

    for f in files:
        label = f.stem.replace("hardware_eval_matrix_", "")
        if label == "smoke" or label not in LABEL_MAP:
            print(f"  skip {f.name}")
            continue
        variant, source = LABEL_MAP[label]
        with open(f, encoding="utf-8") as fh:
            r = csv.DictReader(fh)
            header = header or list(r.fieldnames)
            for row in r:
                # drop the pod's partial scn-5 rows for #4 if the local scn-5 run exists
                if (label == SCN5_TARGET_LABEL and have_scn5_override
                        and row.get("scenario_id") == "5"):
                    continue
                # fold the local scn-5 run into the #4 cell label
                row["label"] = SCN5_TARGET_LABEL if label == SCN5_OVERRIDE_LABEL else label
                row["variant"], row["source"] = variant, source
                row["cell"] = f"{variant}/{source}"
                rows.append(row)

    if not rows:
        print("No matrix CSVs found.", file=sys.stderr); sys.exit(1)

    out = REP / "eval_aggregate.csv"
    cols = header + ["variant", "source", "cell"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # quick coverage summary
    from collections import Counter
    cells = Counter((r["cell"], r["scenario_id"]) for r in rows)
    print(f"\n{len(rows)} rows -> {out}")
    for cell in sorted(set(r["cell"] for r in rows)):
        per = {s: cells[(cell, s)] for s in ["1", "2", "3", "4", "5"] if cells[(cell, s)]}
        print(f"  {cell:22s} {sum(per.values()):3d} rows  scn={per}")


if __name__ == "__main__":
    main()
