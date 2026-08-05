#!/usr/bin/env python3
"""
solve_lp_with_gurobi.py

Usage:
    python solve_lp_with_gurobi.py model.lp /path/to/solutions [param_file]

Reads and solves an LP with Gurobi and prints information relevant to
simplex, barrier, concurrent optimization, performance, basis conditioning,
and numerical solution quality.
"""

from pathlib import Path
from datetime import datetime
import time
import sys

import gurobipy as gp


# ===============================
# Utility functions
# ===============================

def safe_get_attr(model, attr_name, default=None):
    """
    Safely retrieve a scalar Gurobi model attribute.

    Some attributes are only available for certain model classes,
    algorithms, statuses, or solution types.
    """
    try:
        return model.getAttr(attr_name)
    except (gp.GurobiError, AttributeError):
        return default


def print_scalar_attributes(model, attr_names):
    """
    Print scalar model attributes.

    Attributes that are not available for the current model or solution
    are reported as unavailable.
    """
    for name in attr_names:
        value = safe_get_attr(model, name)

        if value is None:
            print(f"{name:<25}: not available")
        else:
            print(f"{name:<25}: {value}")


# ===============================
# Main solve function
# ===============================

def solve_lp(lp_path, sol_folder, param_file=None):

    lp = Path(lp_path)

    if not lp.exists():
        raise FileNotFoundError(f"LP file not found: {lp}")

    solution_folder = Path(sol_folder)
    solution_folder.mkdir(parents=True, exist_ok=True)

    # ===============================
    # Read model
    # ===============================

    model = gp.read(str(lp))

    # ===============================
    # Read parameter file
    # ===============================

    if param_file:
        parameter_path = Path(param_file)

        if not parameter_path.exists():
            raise FileNotFoundError(
                f"Parameter file not found: {parameter_path}"
            )

        print(f"Reading Gurobi parameters from: {parameter_path}")
        model.read(str(parameter_path))
    else:
        print(
            "WARNING: no parameter file provided; "
            "running with default parameters."
        )

    # ===============================
    # Configure logging
    # ===============================

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = (
        solution_folder
        / f"{lp.stem}_{timestamp}.gurobi.log"
    )

    model.setParam("LogFile", str(log_path))

    print(f"Gurobi logging to     : {log_path}")

    # ===============================
    # Solve and measure time
    # ===============================

    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    optimize_error = None

    try:
        model.optimize()

    except gp.GurobiError as error:
        optimize_error = error

        print("\nWARNING: Gurobi terminated with an exception:")
        print(f"  {error}\n")

    except Exception as error:
        optimize_error = error

        print("\nWARNING: unexpected exception during optimization:")
        print(f"  {error}\n")

    wall_end = time.perf_counter()
    cpu_end = time.process_time()

    # ===============================
    # Structured summary
    # ===============================

    print("\n================================")
    print("         GUROBI SUMMARY         ")
    print("================================")

    print(f"Model                    : {lp.name}")
    print(
        f"External Wallclock       : "
        f"{wall_end - wall_start:.6f} sec"
    )
    print(
        f"External CPU Time        : "
        f"{cpu_end - cpu_start:.6f} sec"
    )

    # ===============================
    # Model dimensions
    # ===============================

    print("\n--- Model dimensions ---")

    model_attributes = [
        "NumVars",
        "NumConstrs",
        "NumNZs",
        "DNumNZs",
        "NumQConstrs",
        "NumQNZs",
        "NumIntVars",
        "NumBinVars",
        "NumPWLObjVars",
        "IsMIP",
        "IsQP",
        "IsQCP",
        "ModelSense",
    ]

    print_scalar_attributes(model, model_attributes)

    # ===============================
    # Status and objective
    # ===============================

    print("\n--- Status and objective ---")

    solution_attributes = [
        "Status",
        "SolCount",
        "ObjVal",
        "ObjBound",
        "ObjBoundC",
    ]

    print_scalar_attributes(model, solution_attributes)

    # ===============================
    # Performance
    # ===============================

    print("\n--- Performance ---")

    performance_attributes = [
        "Runtime",
        "Work",
        "MaxMemUsed",
        "IterCount",
        "BarIterCount",
        "ConcurrentWinMethod",
    ]

    print_scalar_attributes(model, performance_attributes)

    # ===============================
    # Basis condition
    # ===============================

    print("\n--- Basis condition ---")

    condition_attributes = [
        "Kappa",
        "KappaExact",
    ]

    print_scalar_attributes(model, condition_attributes)

    # ===============================
    # Numerical quality
    # ===============================

    print("\n--- Overall numerical quality ---")

    overall_quality_attributes = [
        "MaxVio",
        "MaxVioIndex",
        "MaxSVio",
        "MaxSVioIndex",
    ]

    print_scalar_attributes(model, overall_quality_attributes)

    print("\n--- Variable-bound violations ---")

    bound_quality_attributes = [
        "BoundVio",
        "BoundVioIndex",
        "BoundSVio",
        "BoundSVioIndex",
        "BoundVioSum",
        "BoundSVioSum",
    ]

    print_scalar_attributes(model, bound_quality_attributes)

    print("\n--- Constraint violations ---")

    constraint_quality_attributes = [
        "ConstrVio",
        "ConstrVioIndex",
        "ConstrSVio",
        "ConstrSVioIndex",
        "ConstrVioSum",
        "ConstrSVioSum",
    ]

    print_scalar_attributes(model, constraint_quality_attributes)

    print("\n--- Primal constraint residuals ---")

    primal_residual_attributes = [
        "ConstrResidual",
        "ConstrResidualIndex",
        "ConstrSResidual",
        "ConstrSResidualIndex",
        "ConstrResidualSum",
        "ConstrSResidualSum",
    ]

    print_scalar_attributes(model, primal_residual_attributes)

    print("\n--- Dual violations ---")

    dual_quality_attributes = [
        "DualVio",
        "DualVioIndex",
        "DualSVio",
        "DualSVioIndex",
        "DualVioSum",
        "DualSVioSum",
    ]

    print_scalar_attributes(model, dual_quality_attributes)

    print("\n--- Dual residuals ---")

    dual_residual_attributes = [
        "DualResidual",
        "DualResidualIndex",
        "DualSResidual",
        "DualSResidualIndex",
        "DualResidualSum",
        "DualSResidualSum",
    ]

    print_scalar_attributes(model, dual_residual_attributes)

    print("\n--- Complementarity violations ---")

    complementarity_attributes = [
        "ComplVio",
        "ComplVioIndex",
        "ComplVioSum",
    ]

    print_scalar_attributes(model, complementarity_attributes)

    # ===============================
    # Termination information
    # ===============================

    print("\n--- Termination ---")

    if optimize_error is None:
        print("Optimization Error       : None")
    else:
        print(f"Optimization Error       : {optimize_error}")

    # ===============================
    # Write solution
    # ===============================

    solution_count = safe_get_attr(
        model,
        "SolCount",
        default=0,
    )

    if solution_count is not None and solution_count > 0:
        try:
            existing_solutions = list(
                solution_folder.glob("*.sol.gz")
            )

            if existing_solutions:
                print(
                    f"\nSolution not written: "
                    f"{len(existing_solutions)} compressed solution "
                    f"file(s) already exist in {solution_folder}"
                )

            else:
                solution_timestamp = datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )

                solution_path = (
                    solution_folder
                    / (
                        f"{lp.stem}_{solution_timestamp}"
                        f".gurobi.sol.gz"
                    )
                )

                model.write(str(solution_path))

                print(
                    f"\nSolution written to     : {solution_path}"
                )

        except (gp.GurobiError, AttributeError) as error:
            print(
                "\nWARNING: solution exists but could not be written:",
                error,
            )

        except Exception as error:
            print(
                "\nWARNING: unexpected error during solution write:",
                error,
            )

    else:
        print("\nNo solution available; skipping solution write.")

    print(f"\nLog file                 : {log_path}")


# ===============================
# CLI
# ===============================

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print(
            "Usage: python solve_lp_with_gurobi.py "
            "model.lp /path/to/solutions [param_file]"
        )
        sys.exit(1)

    lp_path = sys.argv[1]
    solution_folder = sys.argv[2]
    parameter_file = (
        sys.argv[3]
        if len(sys.argv) >= 4
        else None
    )

    solve_lp(
        lp_path=lp_path,
        sol_folder=solution_folder,
        param_file=parameter_file,
    )
