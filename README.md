# Pyomo port — PPAs + Daily Hedge/Coverage Rate (HCR)

This folder contains a Python (Pyomo) implementation of the AMPL model:
- `original_ampl/Modelo_Optimiza_PPAs_HCR_Dia.mod`
- deterministic case analysis using `data/ampl_dat/*.dat` (E01..E07, CAB, ...)

## What stays the same vs AMPL
- Same sets/parameters/variables names (Spanish), to make validation easier.
- Same objective and constraints.
- The daily hedge/coverage ratio is implemented in a linear form:
  `TotalDemand <= HedgeRate * TotalSupply` (the denominator is constant).

## Install (Python)
```bash
pip install -r requirements.txt
```

## Solver
You need a MILP solver. Options:
- HiGHS: `pip install highspy` then run with `--solver highs`
- GLPK / CBC: install system packages, then run with `--solver glpk` or `--solver cbc`
- CPLEX / Gurobi: if available, use `--solver cplex` or `--solver gurobi`

## Solve one case (keep .dat)
```bash
python src/ppas_hcr_pyomo.py --data data/ampl_dat/Modelo_Optimiza_PPAs_HCR_Dia_E01.dat --solver highs
```

## Solve all cases and export results.csv
```bash
python src/run_cases.py --data data/ampl_dat --solver highs --out results.csv
```

## Convert a .dat case to JSON (optional)
This converter does NOT depend on Pyomo.
```bash
python src/dat_to_json.py --dat data/ampl_dat/Modelo_Optimiza_PPAs_HCR_Dia_E01.dat --json data/json_cases/E01.json
```

The repository already includes JSON dumps for the provided cases under `data/json_cases/`.
