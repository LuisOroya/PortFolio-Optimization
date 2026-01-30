\
"""
Pyomo port of the AMPL model:
  - Modelo_Optimiza_PPAs_HCR_Dia.mod
  - Deterministic case analysis via AMPL-style .dat files (E01..E07, CAB, ...)

Key decisions:
  - y[c] in {0,1} selects up to 3 candidate PPAs.
  - CompraSpot[h] >= 0 buys deficits in the spot market.
  - Daily hedge/coverage constraint: TotalDemand <= HedgeRate * TotalSupply

Notes:
  - This script uses Pyomo's AbstractModel so you can KEEP your AMPL .dat files.
  - You must have a MILP solver available (HiGHS, GLPK, CBC, CPLEX, Gurobi, ...).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Any, List
from xml.parsers.expat import model

import pyomo.environ as pyo

import re
import tempfile

def sanitize_dat_for_pyomo(dat_path: Path) -> Path:
    raw = dat_path.read_text(encoding="utf-8", errors="replace")

    raw = re.sub(r";[ \t]+(\r?\n)", r";\1", raw)  # remove tabs after ';'
    raw = re.sub(r"(^\s*param\s+\w+)\s*=\s*([^;]+);",
                 r"\1 := \2;",
                 raw,
                 flags=re.MULTILINE)

    tmp_dir = Path(tempfile.gettempdir()) / "pyomo_ampl_dat_sanitized"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / dat_path.name
    out_path.write_text(raw, encoding="utf-8")
    return out_path


def build_abstract_model() -> pyo.AbstractModel:
    m = pyo.AbstractModel()

    # --- Sets ---
    m.HORAS = pyo.Set(doc="Hours")
    m.CONTRATOS = pyo.Set(doc="Candidate PPAs (customers)")
    m.PRY_RER = pyo.Set(doc="Renewable projects")

    # --- Parameters (same names as AMPL) ---
    m.DemandaPortafolioActual = pyo.Param(m.HORAS, within=pyo.Reals)
    m.DemandaPPA = pyo.Param(m.HORAS, m.CONTRATOS, within=pyo.Reals)
    m.Produccion_Convencional = pyo.Param(m.HORAS, within=pyo.Reals)
    m.Produccion_RER = pyo.Param(m.HORAS, m.PRY_RER, within=pyo.Reals)
    m.PrecioPPA = pyo.Param(m.CONTRATOS, within=pyo.Reals)
    m.PrecioSpot = pyo.Param(m.HORAS, within=pyo.Reals)
    m.HedgeRate = pyo.Param(within=pyo.Reals)

    # --- Variables ---
    m.y = pyo.Var(m.CONTRATOS, within=pyo.Binary)
    m.CompraSpot = pyo.Var(m.HORAS, within=pyo.NonNegativeReals)

    # --- Expressions ---
    def total_supply_rule(mm):
        return sum(
            mm.Produccion_Convencional[h] + sum(mm.Produccion_RER[h, p] for p in mm.PRY_RER)
            for h in mm.HORAS
        )

    def total_demand_rule(mm):
        return sum(
            mm.DemandaPortafolioActual[h] + sum(mm.DemandaPPA[h, c] * mm.y[c] for c in mm.CONTRATOS)
            for h in mm.HORAS
        )

    mm = m  # alias for doc clarity
    m.TotalSupply = pyo.Expression(rule=total_supply_rule)
    m.TotalDemand = pyo.Expression(rule=total_demand_rule)

    # --- Objective (maximize incomes - spot purchases) ---
    def ingresos_rule(mm):
        revenue = sum(mm.PrecioPPA[c] * mm.DemandaPPA[h, c] * mm.y[c] for h in mm.HORAS for c in mm.CONTRATOS)
        spot_cost = sum(mm.PrecioSpot[h] * mm.CompraSpot[h] for h in mm.HORAS)
        return revenue - spot_cost

    m.Ingresos = pyo.Objective(rule=ingresos_rule, sense=pyo.maximize)

    # --- Constraints (match AMPL .mod) ---
    def compra_spot_maxima_rule(mm, h):
        demand_h = mm.DemandaPortafolioActual[h] + sum(mm.DemandaPPA[h, c] * mm.y[c] for c in mm.CONTRATOS)
        supply_h = mm.Produccion_Convencional[h] + sum(mm.Produccion_RER[h, p] for p in mm.PRY_RER)
        return mm.CompraSpot[h] >= demand_h - supply_h

    m.CompraSpotMaxima = pyo.Constraint(m.HORAS, rule=compra_spot_maxima_rule)

    def balance_oferta_demanda_rule(mm, h):
        demand_h = mm.DemandaPortafolioActual[h] + sum(mm.DemandaPPA[h, c] * mm.y[c] for c in mm.CONTRATOS)
        supply_h = mm.Produccion_Convencional[h] + sum(mm.Produccion_RER[h, p] for p in mm.PRY_RER)
        return demand_h <= supply_h + mm.CompraSpot[h]

    m.BalanceOfertaDemanda = pyo.Constraint(m.HORAS, rule=balance_oferta_demanda_rule)

    # Ratio constraint is linear because TotalSupply is constant (all parameters).
    def restriccion_cobertura_diaria_rule(mm):
        return mm.TotalDemand <= mm.HedgeRate * mm.TotalSupply

    m.RestriccionCoberturaDiaria = pyo.Constraint(rule=restriccion_cobertura_diaria_rule)

    def seleccion_contrato_rule(mm):
        return sum(mm.y[c] for c in mm.CONTRATOS) <= 3

    m.SeleccionContrato = pyo.Constraint(rule=seleccion_contrato_rule)

    return m


def solve_case(data_file: Path, solver: str, tee: bool = False) -> Dict[str, Any]:
    model = build_abstract_model()
    dat_sanitized = sanitize_dat_for_pyomo(data_file)
    inst = model.create_instance(str(dat_sanitized))


    opt = pyo.SolverFactory(solver)
    if opt is None or not opt.available():
        raise RuntimeError(
            f"Solver '{solver}' is not available. Install it or choose another (highs, glpk, cbc, cplex, gurobi, ...)."
        )

    res = opt.solve(inst, tee=tee)
    term = res.solver.termination_condition

    out: Dict[str, Any] = {"case": data_file.name, "termination": str(term)}
    if term != pyo.TerminationCondition.optimal:
        return out

    y_sol = {str(c): int(round(pyo.value(inst.y[c]))) for c in inst.CONTRATOS}
    selected = [c for c, v in y_sol.items() if v == 1]

    total_supply = float(pyo.value(inst.TotalSupply))
    total_demand = float(pyo.value(inst.TotalDemand))
    contracting_level = (total_demand / total_supply) if total_supply > 1e-12 else float("nan")

    ingresos = float(pyo.value(inst.Ingresos))
    total_spot = float(sum(pyo.value(inst.CompraSpot[h]) for h in inst.HORAS))

    out.update(
        {
            "selected_contracts": selected,
            "y": y_sol,
            "Ingresos": ingresos,
            "total_spot": total_spot,
            "contracting_level": contracting_level,
            "HedgeRate": float(pyo.value(inst.HedgeRate)),
        }
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True, help="One or more AMPL .dat files")
    ap.add_argument("--solver", default="highs", help="MILP solver (highs, glpk, cbc, cplex, gurobi, ...)")
    ap.add_argument("--tee", action="store_true", help="Show solver output")
    args = ap.parse_args()

    files: List[Path] = []
    for x in args.data:
        p = Path(x)
        if p.is_dir():
            files.extend(sorted(p.glob("*.dat")))
        else:
            files.append(p)

    for f in files:
        out = solve_case(f, solver=args.solver, tee=args.tee)
        print("\n---", out["case"], "---")
        for k, v in out.items():
            if k != "case":
                print(f"{k}: {v}")


if __name__ == "__main__":
    main()
