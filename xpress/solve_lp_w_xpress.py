#!/usr/bin/env python3
"""
solve_lp_w_xpress.py

Usage:
    python solve_lp_w_xpress.py model.lp /path/to/solutions [param_file]

Reads and solves an LP with FICO Xpress and prints information relevant to:

 - simplex
 - barrier
 - barrier crossover
 - performance
 - memory consumption
 - primal and dual feasibility
 - numerical solution quality
 - termination status

The script also prints the complete problem attribute and control objects.

The solution is written as a ZIP archive containing the .asc and .hdr files
created by Xpress.
"""

from pathlib import Path
import argparse
from datetime import datetime
import time
import sys
import zipfile

import xpress as xp


# ---------------------------------------------------------------------------
# Robust .prs parser
# ---------------------------------------------------------------------------

def parse_prs_file(param_file):
    """
    Parse an Xpress .prs control file.

    Each non-empty, non-comment line may have either of the forms

        CONTROL = VALUE
        CONTROL VALUE

    Returns
    -------
    list[tuple[str, object]]
        A list of (control_name, value) pairs.
    """
    parameter_path = Path(param_file)

    if not parameter_path.exists():
        raise FileNotFoundError(
            f"Parameter file not found: {parameter_path}"
        )

    control_settings = []

    with parameter_path.open("r", encoding="utf-8") as parameter_stream:
        for line_number, raw_line in enumerate(parameter_stream, start=1):
            line = raw_line.strip()

            if not line:
                continue

            if line.startswith("!") or line.startswith("#"):
                continue

            # Remove inline comments.
            for comment_character in ("!", "#"):
                if comment_character in line:
                    line = line.split(comment_character, 1)[0].strip()

            if not line:
                continue

            if "=" in line:
                parts = [
                    part.strip()
                    for part in line.split("=", 1)
                ]
            else:
                parts = line.split(maxsplit=1)

            if len(parts) != 2:
                print(
                    "WARNING: skipping invalid parameter line "
                    f"{line_number}: {raw_line.rstrip()!r}"
                )
                continue

            control_name = parts[0].lower()
            value_string = parts[1].strip()

            # Try integer, then floating point, then string.
            try:
                value = int(value_string)
            except ValueError:
                try:
                    value = float(value_string)
                except ValueError:
                    value = value_string.strip('"').strip("'")

            control_settings.append(
                (control_name, value)
            )

    return control_settings


# ---------------------------------------------------------------------------
# Attribute utilities
# ---------------------------------------------------------------------------

def safe_attrib(problem, attribute_name, default=None):
    """
    Safely retrieve an Xpress problem attribute.

    Some attributes are available only for certain methods, solution states,
    model types, or Xpress versions.
    """
    try:
        return problem.getAttrib(attribute_name)
    except Exception:
        return default


def print_attributes(problem, attribute_names):
    """
    Print scalar Xpress attributes.

    Attributes unavailable for the current model, method, solution state,
    or Xpress version are printed as 'not available'.
    """
    for attribute_name in attribute_names:
        value = safe_attrib(
            problem,
            attribute_name,
        )

        if value is None:
            print(
                f"{attribute_name:<28}: not available"
            )
        else:
            print(
                f"{attribute_name:<28}: {value}"
            )


def print_memory_attribute(
    problem,
    attribute_name,
    label,
):
    """
    Print an Xpress memory attribute in bytes and decimal gigabytes.
    """
    value = safe_attrib(
        problem,
        attribute_name,
    )

    if value is None:
        print(f"{label:<28}: not available")
        return

    try:
        gigabytes = float(value) / 1e9

        print(
            f"{label:<28}: "
            f"{value} bytes ({gigabytes:.6f} GB)"
        )
    except (TypeError, ValueError):
        print(f"{label:<28}: {value}")


# ---------------------------------------------------------------------------
# Solve routine
# ---------------------------------------------------------------------------

def solve_lp(lp_path, sol_folder, param_file=None, write_artifacts=False):
    """
    Read and solve an LP with FICO Xpress.

    Parameters
    ----------
    lp_path : str or Path
        Path to the LP file.
    sol_folder : str or Path
        Directory in which log and solution files are written.
    param_file : str or Path, optional
        Path to an Xpress .prs parameter file.
    """
    lp_path = Path(lp_path)
    solution_folder = Path(sol_folder)

    if not lp_path.exists():
        raise FileNotFoundError(
            f"LP file not found: {lp_path}"
        )

    solution_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Solution folder: {solution_folder}")

    # -----------------------------------------------------------------------
    # Create problem and read LP
    # -----------------------------------------------------------------------

    problem = xp.problem()
    problem.readProb(str(lp_path))

    print(f"Loaded LP: {lp_path.name}")

    # -----------------------------------------------------------------------
    # Apply parameter controls
    # -----------------------------------------------------------------------

    if param_file:
        print(f"Parsing parameter file: {param_file}")

        for control_name, value in parse_prs_file(param_file):
            try:
                problem.setControl(
                    control_name,
                    value,
                )

                print(
                    f"Set control "
                    f"{control_name} = {value!r}"
                )

            except Exception as error:
                print(
                    "WARNING: could not set control "
                    f"{control_name!r} = {value!r}: "
                    f"{error}"
                )
    else:
        print(
            "WARNING: no parameter file provided; "
            "using default controls."
        )

    # -----------------------------------------------------------------------
    # Logging
    # -----------------------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    log_path = (
        solution_folder
        / f"{lp_path.stem}_{timestamp}.xpress.log"
    )

    problem.setControl("outputlog", 1)
    problem.setLogFile(str(log_path))

    print(f"Xpress logging to: {log_path}")

    # -----------------------------------------------------------------------
    # Solve and measure external times
    # -----------------------------------------------------------------------

    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    optimize_error = None

    try:
        problem.solve()

    except Exception as error:
        optimize_error = error

        print("\nWARNING: Xpress terminated with an exception:")
        print(f"  {error}\n")

    wall_end = time.perf_counter()
    cpu_end = time.process_time()

    external_wallclock = wall_end - wall_start
    external_cpu_time = cpu_end - cpu_start

    # -----------------------------------------------------------------------
    # Complete attribute and control dumps
    # -----------------------------------------------------------------------

    print("\n================================")
    print("     ALL XPRESS ATTRIBUTES      ")
    print("================================")
    print(problem.attributes)

    print("\n================================")
    print("       ALL XPRESS CONTROLS      ")
    print("================================")
    print(problem.controls)

    # -----------------------------------------------------------------------
    # Structured summary
    # -----------------------------------------------------------------------

    print("\n================================")
    print("         XPRESS SUMMARY         ")
    print("================================")

    print(f"Model                       : {lp_path.name}")
    print(
        f"External Wallclock          : "
        f"{external_wallclock:.6f} sec"
    )
    print(
        f"External Python CPU Time    : "
        f"{external_cpu_time:.6f} sec"
    )
    print(f"Log file                    : {log_path}")

    # -----------------------------------------------------------------------
    # Model dimensions
    # -----------------------------------------------------------------------

    print("\n--- Model dimensions ---")

    model_attributes = [
        "rows",
        "cols",
        "elems",
        "inputrows",
        "inputcols",
        "originalrows",
        "originalcols",
        "qelems",
        "qconstraints",
        "qcelems",
        "sets",
        "setmembers",
        "indicators",
        "pwlcons",
        "pwlpoints",
    ]

    print_attributes(
        problem,
        model_attributes,
    )

    # -----------------------------------------------------------------------
    # Status and objective
    # -----------------------------------------------------------------------

    print("\n--- Status and objective ---")

    status_attributes = [
        "lpstatus",
        "solstatus",
        "solvestatus",
        "stopstatus",
        "objval",
        "lpobjval",
        "objsense",
        "optimizetypeused",
        "algorithm",
        "errorcode",
    ]

    print_attributes(
        problem,
        status_attributes,
    )

    # -----------------------------------------------------------------------
    # Performance
    # -----------------------------------------------------------------------

    print("\n--- Performance ---")

    performance_attributes = [
        "time",
        "work",
        "simplexiter",
        "bariter",
        "crossoveriter",
        "computeexecutions",
        "restarts",
    ]

    print_attributes(
        problem,
        performance_attributes,
    )

    # -----------------------------------------------------------------------
    # Simplex feasibility and numerical quality
    # -----------------------------------------------------------------------

    print("\n--- Simplex feasibility ---")

    simplex_feasibility_attributes = [
        "primalinfeas",
        "dualinfeas",
        "sumprimalinf",
        "maxabsprimalinfeas",
        "maxrelprimalinfeas",
        "maxabsdualinfeas",
        "maxreldualinfeas",
    ]

    print_attributes(
        problem,
        simplex_feasibility_attributes,
    )

    # -----------------------------------------------------------------------
    # Simplex basis conditioning
    # -----------------------------------------------------------------------

    print("\n--- Simplex basis condition ---")

    simplex_condition_attributes = [
        "maxkappa",
    ]

    print_attributes(
        problem,
        simplex_condition_attributes,
    )

    # -----------------------------------------------------------------------
    # Barrier information
    # -----------------------------------------------------------------------

    print("\n--- Barrier solution information ---")

    barrier_solution_attributes = [
        "barprimalobj",
        "bardualobj",
        "barprimalinf",
        "bardualinf",
        "barcgap",
    ]

    print_attributes(
        problem,
        barrier_solution_attributes,
    )

    # -----------------------------------------------------------------------
    # Barrier conditioning and singularities
    # -----------------------------------------------------------------------

    print("\n--- Barrier numerical information ---")

    barrier_numerical_attributes = [
        "barconda",
        "barcondd",
        "barsing",
        "barsingr",
        "baraasize",
        "barlsize",
        "bardensecol",
        "barcrossover",
    ]

    print_attributes(
        problem,
        barrier_numerical_attributes,
    )

    # -----------------------------------------------------------------------
    # Presolve information
    # -----------------------------------------------------------------------

    print("\n--- Presolve information ---")

    presolve_attributes = [
        "presolvestate",
        "presolveindex",
    ]

    print_attributes(
        problem,
        presolve_attributes,
    )

    # -----------------------------------------------------------------------
    # Memory
    # -----------------------------------------------------------------------

    print("\n--- Memory ---")

    print_memory_attribute(
        problem,
        "peakmemory",
        "Peak memory",
    )

    print_memory_attribute(
        problem,
        "currentmemory",
        "Current memory",
    )

    print_memory_attribute(
        problem,
        "totalmemory",
        "Total memory",
    )

    available_memory = safe_attrib(
        problem,
        "availablememory",
    )

    if available_memory is None:
        print(
            f"{'Available memory':<28}: "
            "not available"
        )
    else:
        print(
            f"{'Available memory':<28}: "
            f"{available_memory}"
        )

    # -----------------------------------------------------------------------
    # Hardware and version information
    # -----------------------------------------------------------------------

    print("\n--- Environment ---")

    environment_attributes = [
        "xpressversion",
        "coresdetected",
        "physicalcoresdetected",
        "cpusdetected",
        "systemmemory",
        "memorylimitdetected",
    ]

    print_attributes(
        problem,
        environment_attributes,
    )

    # -----------------------------------------------------------------------
    # Termination information
    # -----------------------------------------------------------------------

    print("\n--- Termination ---")

    if optimize_error is None:
        print(
            f"{'Optimization error':<28}: None"
        )
    else:
        print(
            f"{'Optimization error':<28}: "
            f"{optimize_error}"
        )

    # -----------------------------------------------------------------------
    # Write solution
    # -----------------------------------------------------------------------

    solution_status = safe_attrib(
        problem,
        "solstatus",
        default=0,
    )

    solution_exists = (
        solution_status is not None
        and solution_status != 0
    )

    if not write_artifacts:
        print("\nSolution writing disabled.")
    elif solution_exists:
        try:
            existing_solutions = list(
                solution_folder.glob("*.sol.zip")
            )

            if existing_solutions:
                print(
                    "\nSolution not written: "
                    f"{len(existing_solutions)} solution file(s) "
                    f"already exist in {solution_folder}"
                )

            else:
                solution_timestamp = datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )

                solution_base = (
                    solution_folder
                    / (
                        f"{lp_path.stem}_"
                        f"{solution_timestamp}.xpress.sol"
                    )
                )

                # Xpress creates .asc and .hdr files.
                problem.writeSol(str(solution_base))

                asc_file = solution_base.with_suffix(
                    solution_base.suffix + ".asc"
                )
                hdr_file = solution_base.with_suffix(
                    solution_base.suffix + ".hdr"
                )

                missing_files = [
                    path
                    for path in (asc_file, hdr_file)
                    if not path.exists()
                ]

                if missing_files:
                    raise RuntimeError(
                        "Expected solution files not found: "
                        f"{missing_files}"
                    )

                zip_file = solution_base.with_suffix(
                    solution_base.suffix + ".zip"
                )

                with zipfile.ZipFile(
                    zip_file,
                    mode="w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as zip_stream:
                    zip_stream.write(
                        asc_file,
                        arcname=asc_file.name,
                    )
                    zip_stream.write(
                        hdr_file,
                        arcname=hdr_file.name,
                    )

                asc_file.unlink()
                hdr_file.unlink()

                print(
                    f"\nSolution written to        : "
                    f"{zip_file}"
                )

        except Exception as error:
            print(
                "\nWARNING: solution exists but could not "
                f"be written: {error}"
            )

    else:
        print(
            "\nNo solution available; "
            "skipping solution write."
        )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("lp_file")
    parser.add_argument("solution_folder")
    parser.add_argument("parameter_file", nargs="?")
    parser.add_argument(
        "--write-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="write the solved .sol.zip artifact (default: disabled)",
    )
    args = parser.parse_args()
    solve_lp(
        lp_path=args.lp_file,
        sol_folder=args.solution_folder,
        param_file=args.parameter_file,
        write_artifacts=args.write_artifacts,
    )

    print()
