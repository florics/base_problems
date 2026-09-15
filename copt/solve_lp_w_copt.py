#!/usr/bin/env python3
"""
solve_lp_with_copt.py

Usage:
    python solve_lp_with_copt.py model.lp /path/to/solutions [param_file]

Solves an LP using COPT and prints performance, algorithmic, and numerical
quality metrics relevant to both barrier and simplex.
"""

from pathlib import Path
import argparse
from datetime import datetime
import time
import sys
import os
import gzip
import shutil

import coptpy as cp
from coptpy import COPT


# ===============================
# Utility: safely retrieve attributes
# ===============================

def safe_get_attr(model, attr_name, default=None):
    """
    Retrieve a COPT model attribute without terminating the script if the
    attribute is unavailable in the installed COPT version or inappropriate
    for the current model/solution status.
    """
    try:
        return model.getAttr(attr_name)
    except (cp.CoptError, AttributeError):
        return default


# ===============================
# Utility: compute primal residual manually
# ===============================

def compute_primal_residual(model):
    """
    Compute the maximum constraint violation and maximum bound violation
    using the returned primal solution.

    Returns
    -------
    max_constr_violation : float
        Maximum violation among all linear constraints.
    max_bound_violation : float
        Maximum violation among all variable bounds.
    """
    max_constr_violation = 0.0
    max_bound_violation = 0.0

    # Constraint violations
    for constr in model.getConstrs():
        activity = model.getRow(constr).getValue()
        sense = constr.getAttr("Sense")
        rhs = constr.getAttr("RHS")

        if sense == COPT.LESS_EQUAL:
            violation = max(0.0, activity - rhs)
        elif sense == COPT.GREATER_EQUAL:
            violation = max(0.0, rhs - activity)
        else:
            violation = abs(activity - rhs)

        max_constr_violation = max(
            max_constr_violation,
            violation,
        )

    # Variable-bound violations
    for var in model.getVars():
        x = var.getAttr("X")
        lb = var.getAttr("LB")
        ub = var.getAttr("UB")

        if lb is not None:
            max_bound_violation = max(
                max_bound_violation,
                max(0.0, lb - x),
            )

        if ub is not None:
            max_bound_violation = max(
                max_bound_violation,
                max(0.0, x - ub),
            )

    return max_constr_violation, max_bound_violation


# ===============================
# Main solve function
# ===============================

def solve_lp(lp_path, sol_folder, param_file=None, write_artifacts=False):

    lp = Path(lp_path)
    if not lp.exists():
        raise FileNotFoundError(f"LP file not found: {lp}")

    sol_folder = Path(sol_folder)
    sol_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = sol_folder / f"{lp.stem}_{timestamp}.copt.log"

    # ===============================
    # Create environment and model
    # ===============================

    env = cp.Envr()
    model = env.createModel()

    model.read(str(lp))

    # ===============================
    # Parameter configuration
    # ===============================

    model.setLogFile(str(log_path))

    if param_file:
        param_path = Path(param_file)

        if not param_path.exists():
            raise FileNotFoundError(
                f"Parameter file not found: {param_path}"
            )

        print(f"Reading parameter file: {param_path}")
        model.read(str(param_path))
    else:
        print("WARNING: No parameter file provided.")

    # ===============================
    # Solve
    # ===============================

    print("\n=== Optimization Started ===\n")

    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    optimize_error = None

    try:
        model.solve()
    except cp.CoptError as error:
        optimize_error = error
        print("\nWARNING: COPT terminated with an exception:")
        print(f"  {error}\n")
    except Exception as error:
        optimize_error = error
        print("\nWARNING: Unexpected exception during optimization:")
        print(f"  {error}\n")

    wall_end = time.perf_counter()
    cpu_end = time.process_time()

    # ===============================
    # Collect solver information
    # ===============================

    # Unified solution attributes recommended by newer COPT versions.
    status = safe_get_attr(model, "Status")
    has_sol = bool(safe_get_attr(model, "HasSol", 0))
    objval = safe_get_attr(model, "ObjVal") if has_sol else None

    # LP-specific attributes. These are retained for compatibility with older
    # COPT versions and for explicitly reporting LP information.
    lp_status = safe_get_attr(model, "LpStatus")
    has_lp_sol = bool(safe_get_attr(model, "HasLpSol", 0))
    lp_objval = (
        safe_get_attr(model, "LpObjval")
        if has_lp_sol
        else None
    )

    solving_time = safe_get_attr(model, "SolvingTime")
    simplex_iter = safe_get_attr(model, "SimplexIter")
    barrier_iter = safe_get_attr(model, "BarrierIter")

    has_basis = bool(safe_get_attr(model, "HasBasis", 0))
    has_primal_ray = bool(
        safe_get_attr(model, "HasPrimalRay", 0)
    )
    has_dual_farkas = bool(
        safe_get_attr(model, "HasDualFarkas", 0)
    )

    # ===============================
    # Compute numerical quality
    # ===============================

    max_constr_violation = None
    max_bound_violation = None

    if not write_artifacts:
        print("\nSolution writing disabled.")
    elif has_lp_sol:
        try:
            (
                max_constr_violation,
                max_bound_violation,
            ) = compute_primal_residual(model)
        except cp.CoptError as error:
            print(
                "WARNING: Could not compute manual primal residuals:",
                error,
            )
        except Exception as error:
            print(
                "WARNING: Unexpected error while computing residuals:",
                error,
            )

    # ===============================
    # Write solution
    # ===============================

    if has_lp_sol:
        try:
            existing_sols = list(sol_folder.glob("*.sol.gz"))

            if existing_sols:
                print(
                    f"\nSolution not written: {len(existing_sols)} "
                    f"compressed solution file(s) already exist in "
                    f"{sol_folder}"
                )
            else:
                solution_timestamp = datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )

                tmp_sol_path = (
                    sol_folder
                    / f"{lp.stem}_{solution_timestamp}.copt.sol"
                )
                final_sol_path = (
                    sol_folder
                    / f"{lp.stem}_{solution_timestamp}.copt.sol.gz"
                )

                model.write(str(tmp_sol_path))

                with open(tmp_sol_path, "rb") as input_file:
                    with gzip.open(final_sol_path, "wb") as output_file:
                        shutil.copyfileobj(input_file, output_file)

                tmp_sol_path.unlink()

                print(
                    f"\nSolution written to     : {final_sol_path}"
                )

        except cp.CoptError as error:
            print(
                "WARNING: Solution exists but could not be written:",
                error,
            )
        except Exception as error:
            print(
                "WARNING: Unexpected error during solution write:",
                error,
            )
    else:
        print("\nNo LP solution available; skipping solution write.")

    # ===============================
    # Structured summary
    # ===============================

    print("\n==============================")
    print("         SOLVER SUMMARY       ")
    print("==============================")

    print(f"Model                : {lp.name}")
    print(f"Status               : {status}")
    print(f"LP Status            : {lp_status}")
    print(f"Has Solution         : {has_sol}")
    print(f"Has LP Solution      : {has_lp_sol}")
    print(f"Objective            : {objval}")
    print(f"LP Objective         : {lp_objval}")

    print("\n--- Performance ---")
    print(
        f"External Wallclock   : "
        f"{wall_end - wall_start:.6f} sec"
    )
    print(
        f"External CPU Time    : "
        f"{cpu_end - cpu_start:.6f} sec"
    )

    if solving_time is None:
        print("Solver Time          : unavailable")
    else:
        print(f"Solver Time          : {solving_time:.6f} sec")

    print(f"Simplex Iterations   : {simplex_iter}")
    print(f"Barrier Iterations   : {barrier_iter}")

    print("\n--- Solution Information ---")
    print(f"Basis Available      : {has_basis}")
    print(f"Primal Ray Available : {has_primal_ray}")
    print(f"Dual Farkas Available: {has_dual_farkas}")

    print("\n--- Numerical Quality ---")

    if max_constr_violation is None:
        print("Max Constraint Viol. : unavailable")
    else:
        print(
            f"Max Constraint Viol. : "
            f"{max_constr_violation:.16e}"
        )

    if max_bound_violation is None:
        print("Max Bound Violation  : unavailable")
    else:
        print(
            f"Max Bound Violation  : "
            f"{max_bound_violation:.16e}"
        )

    print("\n--- Termination ---")
    print(
        f"Optimization Error   : "
        f"{optimize_error if optimize_error else 'None'}"
    )

    print(f"\nLog file             : {log_path}")


# ===============================
# CLI
# ===============================

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
