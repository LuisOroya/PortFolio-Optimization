\
"""
Lightweight parser for this project's AMPL-style .dat files.
Designed specifically for the data layout used in:
  - Modelo_Optimiza_PPAs_HCR_Dia_*.dat

It supports:
  - set NAME := ... ;
  - param NAME := (key value)* ;
  - param NAME: col1 col2 ... := (row v1 v2 ...)* ;
  - param NAME = scalar;

It ignores comments starting with '#'.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple


_NUM_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _strip_comments(line: str) -> str:
    # Remove everything after '#'
    return line.split("#", 1)[0].strip()


def _tokenize_block(lines: List[str]) -> List[str]:
    tokens: List[str] = []
    for ln in lines:
        ln = _strip_comments(ln)
        if not ln:
            continue
        tokens.extend(ln.replace("\t", " ").split())
    return tokens


def parse_dat(dat_path: Path) -> Dict[str, Any]:
    raw_lines = dat_path.read_text(encoding="utf-8", errors="replace").splitlines()

    sets: Dict[str, List[str]] = {}
    params: Dict[str, Any] = {}

    i = 0
    n = len(raw_lines)

    while i < n:
        line = _strip_comments(raw_lines[i])
        if not line:
            i += 1
            continue

        # --- Scalar param: param HedgeRate=0.8;
        m_scalar = re.match(r"^param\s+([A-Za-z_]\w*)\s*=\s*([^;]+)\s*;\s*$", line)
        if m_scalar:
            name = m_scalar.group(1)
            val_str = m_scalar.group(2).strip()
            try:
                val = float(val_str)
            except ValueError:
                val = val_str
            params[name] = val
            i += 1
            continue

        # --- Set definition: set NAME := ... ;
        if line.startswith("set "):
            # Collect until we see ';'
            block = [line]
            i += 1
            while i < n and ";" not in block[-1]:
                block.append(raw_lines[i])
                i += 1

            # Rebuild and parse
            joined = " ".join(_strip_comments(x) for x in block)
            # Example: set HORAS:= H01 H02 ... ;
            joined = joined.replace(":=", " := ")
            tokens = joined.replace(";", " ; ").split()
            # tokens: ['set','HORAS',':=','H01',...,';']
            name = tokens[1]
            # Everything after ':=' until ';'
            if ":=" not in tokens:
                raise ValueError(f"Malformed set block in {dat_path.name}: {joined}")
            start = tokens.index(":=") + 1
            end = tokens.index(";")
            sets[name] = tokens[start:end]
            continue

        # --- Param 1D: param NAME := key value ... ;
        if line.startswith("param ") and ":=" in line and ":" not in line.split(":=", 1)[0]:
            # Collect block until ';'
            block = [line]
            i += 1
            while i < n and ";" not in block[-1]:
                block.append(raw_lines[i])
                i += 1

            # First line has "param NAME :="
            first = _strip_comments(block[0])
            name = first.split()[1].split(":=")[0].strip()
            # Remaining lines contain key value
            # Remove first line prefix up to ':='
            # We'll tokenize block and then parse pairs
            # Safer: parse line-by-line after the first.
            mapping: Dict[str, float] = {}
            for ln in block[1:]:
                ln = _strip_comments(ln)
                if not ln:
                    continue
                if ";" in ln:
                    ln = ln.replace(";", " ")
                parts = ln.replace("\t", " ").split()
                if len(parts) >= 2:
                    k = parts[0]
                    v = float(parts[1])
                    mapping[k] = v
            params[name] = mapping
            continue

        # --- Param 2D table: param NAME: col1 col2 ... := rows ... ;
        if line.startswith("param ") and ":=" in line and ":" in line.split(":=", 1)[0]:
            # Collect block until ';'
            block = [line]
            i += 1
            while i < n and ";" not in block[-1]:
                block.append(raw_lines[i])
                i += 1

            header = _strip_comments(block[0])
            # Example: param DemandaPPA: NewPPA1 NewPPA2 NewPPA3 :=
            # Split at 'param' then name+':'
            after_param = header[len("param "):]
            name_part, rest = after_param.split(":", 1)
            name = name_part.strip()
            cols_part = rest.split(":=")[0].strip()
            cols = [c for c in cols_part.replace("\t", " ").split() if c]

            table: Dict[str, Dict[str, float]] = {}

            for ln in block[1:]:
                ln = _strip_comments(ln)
                if not ln:
                    continue
                if ";" in ln:
                    ln = ln.replace(";", " ")
                parts = ln.replace("\t", " ").split()
                if not parts:
                    continue
                row = parts[0]
                vals = parts[1:1+len(cols)]
                if len(vals) != len(cols):
                    # skip incomplete lines (defensive)
                    continue
                table[row] = {cols[j]: float(vals[j]) for j in range(len(cols))}

            params[name] = table
            continue

        # Unknown line: just move on
        i += 1

    return {"sets": sets, "params": params}


def dat_to_json(dat_path: Path, json_path: Path) -> None:
    payload = parse_dat(dat_path)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", required=True, help="Input .dat file")
    ap.add_argument("--json", required=True, help="Output .json file")
    args = ap.parse_args()
    dat_to_json(Path(args.dat), Path(args.json))


if __name__ == "__main__":
    main()
