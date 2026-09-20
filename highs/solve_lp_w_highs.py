#!/usr/bin/env python3
"""Solve one LP with HiGHS and report standardized solve-only timings."""

from __future__ import annotations

import argparse
from datetime import datetime
import gzip
from pathlib import Path
import shutil
import time

import highspy


def require_ok(status, action):
    if status != highspy.HighsStatus.kOk:
        raise RuntimeError(f"HiGHS {action} failed with status {status}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lp_file", type=Path)
    parser.add_argument("result_dir", type=Path)
    parser.add_argument("options_file", type=Path)
    parser.add_argument("--run-index", type=int, required=True)
    parser.add_argument(
        "--write-artifacts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="write the first-run .highs.sol.gz artifact (default: disabled)",
    )
    args = parser.parse_args()

    args.result_dir.mkdir(parents=True, exist_ok=True)
    highs = highspy.Highs()
    model_path = args.lp_file
    decompressed_path = None
    if args.lp_file.suffix == ".gz":
        # This HiGHS build lacks zlib support, so materialize gzip input locally.
        decompressed_path = args.result_dir / args.lp_file.with_suffix("").name
        with gzip.open(args.lp_file, "rb") as source, decompressed_path.open("wb") as destination:
            shutil.copyfileobj(source, destination)
        model_path = decompressed_path
    try:
        require_ok(highs.readModel(str(model_path)), f"readModel({args.lp_file})")
    finally:
        if decompressed_path is not None:
            decompressed_path.unlink(missing_ok=True)
    require_ok(highs.readOptions(str(args.options_file)), f"readOptions({args.options_file})")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = args.result_dir / f"{args.lp_file.stem}_{timestamp}_run_{args.run_index}.highs.log"
    require_ok(highs.setOptionValue("log_file", str(log_path)), "setOptionValue(log_file)")

    runtime_before = float(highs.getRunTime())
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    status = highs.run()
    external_wallclock = time.perf_counter() - wall_start
    external_cpu_time = time.process_time() - cpu_start
    solver_runtime = max(0.0, float(highs.getRunTime()) - runtime_before)
    if status == highspy.HighsStatus.kError:
        raise RuntimeError("HiGHS run() returned kError")

    info = highs.getInfo()
    print("\n=== HIGHS SUMMARY ===")
    print(f"Model                       : {args.lp_file.name}")
    print(f"Status                      : {highs.modelStatusToString(highs.getModelStatus())}")
    print(f"External Wallclock          : {external_wallclock:.6f} sec")
    print(f"External Python CPU Time    : {external_cpu_time:.6f} sec")
    print(f"Solver Time                 : {solver_runtime:.6f} sec")
    print(f"Simplex Iterations          : {getattr(info, 'simplex_iteration_count', None)}")
    print(f"Barrier Iterations          : {getattr(info, 'ipm_iteration_count', None)}")
    print("Solver-native work units    : unavailable")
    print(f"Log file                    : {log_path}")

    if args.write_artifacts:
        solution_path = args.result_dir / f"{args.lp_file.stem}_{timestamp}_run_{args.run_index}.highs.sol"
        require_ok(highs.writeSolution(str(solution_path), 0), f"writeSolution({solution_path})")
        compressed_path = solution_path.with_suffix(solution_path.suffix + ".gz")
        with solution_path.open("rb") as source, gzip.open(compressed_path, "wb") as destination:
            shutil.copyfileobj(source, destination)
        solution_path.unlink()
        print(f"Solution written to         : {compressed_path}")
    else:
        print("Solution writing disabled.")


if __name__ == "__main__":
    main()
