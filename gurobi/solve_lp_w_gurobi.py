#!/usr/bin/env python3
"""
solve_lp_with_gurobi.py

Usage:
    python solve_lp_with_gurobi.py /path/to/model.lp /path/to/solutions [num_threads]

This script:
 - reads the LP
 - optional: sets Threads
 - optional: sets Method=2 (barrier) and disables crossover (Crossover=0)
 - measures wallclock time and reads Gurobi attributes (Runtime, IterCount, BarIterCount, Work)
 - writes a timestamped .sol file (and prints a short summary)
"""
from pathlib import Path
import argparse
from datetime import datetime
import time
import sys
import os

import gurobipy as gp
from gurobipy import GRB

def solve_lp(lp_path, sol_folder, param_file=None, write_artifacts=False):
    lp = Path(lp_path)
    if not lp.exists():
        raise FileNotFoundError("LP file not found: {}".format(lp))

    #debug
    print(f"sol_folder: {sol_folder}")
    
    # Ensure output folder exists
    os.makedirs(sol_folder, exist_ok=True)

    # Read model (reads the LP into a Gurobi Model)
    model = gp.read(str(lp))

    # read parameter file
    if param_file:
        print(f"Reading Gurobi parameters from: {param_file}")
        model.read(str(param_file))
    else:
        print("WARNING: no parameter file provided, running with default parameters.")

    # Optional: set a log file next to solution (uncomment if you want a separate log)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = Path(sol_folder) / f"{lp.stem}_{timestamp}.gurobi.log"
    model.setParam('LogFile', str(log_path))
    print("Gurobi logging to     : {}".format(log_path))

    # --- Solve and measure times ---
    t0 = time.time()
    
    optimize_error = None

    try:
        model.optimize()
    except gp.GurobiError as e:
        optimize_error = e
        print("\nWARNING: Gurobi terminated with an exception:")
        print(f"  {e}\n")

    t1 = time.time()

    # --- Collect results (safe access to attributes) ---

    print("Wallclock time         : {:.3f} sec (external timer)".format(t1 - t0))

    print("\n=== Gurobi Attributes ===\n")

    attrs = [
        "Status",
        "ObjVal",
        "ObjBound",
        
        "Runtime",
        "IterCount",
        "BarIterCount",
        "Work",
        "MaxMemUsed",

        "MaxVio",
        
        "BoundVio",
        "BoundSVio",
        "BoundVioSum",
        "BoundSVioSum",
        
        "ConstrVio",
        "ConstrSVio",
        "ConstrVioSum",
        "ConstrSVioSum",
        "ConstrResidual",
        "ConstrSResidual",
        "ConstrResidualSum",
        "ConstrSResidualSum",

        "DualVio",
        "DualSVio",
        "DualVioSum",
        "DualSVioSum",
        "DualResidual",
        "DualSResidual",
        "DualResidualSum",
        "DualSResidualSum",

        "ComplVio",
        "ComplVioSum",
    ]

    for name in attrs:
        try:
            print(f"{name}:             {model.getAttr(name)}")
        except (gp.GurobiError, AttributeError):
            print(name, "not available")

    if not write_artifacts:
        print("Solution writing disabled.")
    elif model.SolCount > 0:
        try:
            existing_sols = list(Path(sol_folder).glob("*.sol.gz"))
            if existing_sols:
                print(f"Solution not written: {len(existing_sols)} solution file(s) already exist in {sol_folder}")
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                base_name = lp.stem
                sol_path = Path(sol_folder) / "{}_{}.gurobi.sol.gz".format(base_name, timestamp)
                model.write(str(sol_path))
                print("Solution written to     : {}".format(sol_path))
        except (gp.GurobiError, AttributeError) as e:
            print("WARNING: solution exists but could not be written:", e)
    else:
        print("No solution available; skipping solution write.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("lp")
    parser.add_argument("sol_folder")
    parser.add_argument("param_file", nargs="?")
    parser.add_argument(
        "--write-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="write the solved .sol.gz artifact (default: disabled)",
    )
    args = parser.parse_args()
    solve_lp(
        args.lp,
        args.sol_folder,
        args.param_file,
        write_artifacts=args.write_artifacts,
    )
