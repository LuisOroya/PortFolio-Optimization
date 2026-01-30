\
"""
Solve multiple AMPL-style .dat cases with the Pyomo model and export a results CSV.

Usage:
  python run_cases.py --data ../data/ampl_dat --solver highs --out results.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List

from ppas_hcr_pyomo import solve_case


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="A .dat file or a directory with .dat files")
    ap.add_argument("--solver", default="highs", help="MILP solver (highs, glpk, cbc, cplex, gurobi, ...)")
    ap.add_argument("--out", default="results.csv", help="Output CSV filename")
    ap.add_argument("--tee", action="store_true", help="Show solver output")
    args = ap.parse_args()

    data_path = Path(args.data)
    files: List[Path]
    if data_path.is_dir():
        files = sorted(data_path.glob("*.dat"))
    else:
        files = [data_path]

    rows = []
    for f in files:
        out = solve_case(f, solver=args.solver, tee=args.tee)
        rows.append(out)

    out_path = Path(args.out)
    # Build a stable header
    fieldnames = ["case", "termination", "Ingresos", "HedgeRate", "contracting_level", "total_spot", "selected_contracts", "y"]
    with out_path.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})

    print("Wrote:", out_path.resolve())


if __name__ == "__main__":
    main()
