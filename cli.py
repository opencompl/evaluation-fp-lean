#!/usr/bin/env -S uv run
"""FP-lean evaluation driver. Defines experiments and dispatches run/plot."""
import argparse
import json
import pathlib
import shutil
import sys
import time
from typing import Callable

import bench
import lib
import plot


ConfigFn = Callable[[argparse.Namespace], list[bench.Config]]
PlotFn = Callable[[pathlib.Path, pathlib.Path, argparse.Namespace], None]


def cactus_configs(opts: argparse.Namespace) -> list[bench.Config]:
    suite = bench.SUITES[opts.suite]
    probs = bench.sampled_problems(opts.nproblems, suite)
    out: list[bench.Config] = []
    for tool in suite.tools_to_run:
        for run in range(opts.runs):
            for p in probs:
                out.append({
                    "tool": tool,
                    "run": run,
                    "family": p["family"],
                    "benchmark": p["benchmark"],
                    "path": p["path"],
                    "expected_status": p["expected_status"],
                })
    return out


def debug_configs(opts: argparse.Namespace) -> list[bench.Config]:
    path = pathlib.Path(opts.file).resolve()
    if not path.exists():
        print(f"no such file: {path}")
        sys.exit(1)
    try:
        dataset_dir = bench.SUITES[opts.suite].dataset_dir
        rel = path.relative_to(dataset_dir.resolve())
        family = rel.parts[0] if len(rel.parts) > 1 else "debug"
        benchmark = str(rel)
    except ValueError:
        family = "debug"
        benchmark = path.name
    expected_status = bench._status_of(path)
    out: list[bench.Config] = []
    for tool in bench.SUITES[opts.suite].tools_to_run:
        for run in range(opts.runs):
            out.append({
                "tool": tool,
                "run": run,
                "family": family,
                "benchmark": benchmark,
                "path": path,
                "expected_status": expected_status,
            })
    return out


def fptg_oracle_configs(opts: argparse.Namespace) -> list[bench.Config]:
    """Like `cactus_configs`, but runs only the tools named in `--tools` (default
    the two fp-lean paths) instead of the whole suite's tool list -- the oracle
    test grades fp-lean against the :status ground truth, so it needs neither the
    --fpexp bitwuzla nor the slow exhaustive enumerator."""
    suite = bench.SUITES[opts.suite]
    probs = bench.sampled_problems(opts.nproblems, suite)
    tools = [t.strip() for t in opts.tools.split(",") if t.strip()]
    out: list[bench.Config] = []
    for tool in tools:
        for run in range(opts.runs):
            for p in probs:
                out.append({
                    "tool": tool,
                    "run": run,
                    "family": p["family"],
                    "benchmark": p["benchmark"],
                    "path": p["path"],
                    "expected_status": p["expected_status"],
                })
    return out


def do_run(opts: argparse.Namespace, config_name: str, configs_fn: ConfigFn) -> None:
    outdir = bench.RUNRESULTS_DIR / opts.guid
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
    data_dir = outdir / "data"
    outputs_dir = outdir / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()

    configs = configs_fn(opts)
    print(f"config '{config_name}': {len(configs)} datapoints -> {outdir}")
    bench.run_many(configs, opts.timeout_sec, opts.memout_mb, opts.nproc, data_dir)

    manifest: bench.Manifest = {
        "config_name": config_name,
        "suite": opts.suite,
        "tools": bench.SUITES[opts.suite].tools_to_run,
        "nproblems": opts.nproblems,
        "runs": opts.runs,
        "timeout_sec": opts.timeout_sec,
        "memout_mb": opts.memout_mb,
        "seed": bench.SEED,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_hash": lib.git_hash(),
    }
    manifest_path = data_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.copy(manifest_path, outputs_dir / "manifest.json")
    bench.write_config_tex(outputs_dir, opts)
    bench.write_machine_data_tex(outputs_dir)


def do_plot(opts: argparse.Namespace, plot_fn: PlotFn) -> None:
    base_dir = bench.RUNRESULTS_DIR / opts.guid
    data_dir = base_dir / "data"
    if not data_dir.exists():
        print(f"no such guid: {base_dir}")
        sys.exit(1)
    outdir = pathlib.Path(opts.outdir) if opts.outdir else (base_dir / "outputs" / "plots" / opts.command)
    plot_fn(data_dir, outdir, opts)


def cmd_cactus(opts: argparse.Namespace) -> None:
    if opts.run:
        do_run(opts, "cactus", cactus_configs)
    if opts.plot:
        do_plot(opts, plot.plot_cactus)


def cmd_debug(opts: argparse.Namespace) -> None:
    if opts.run:
        do_run(opts, "debug", debug_configs)
    if opts.plot:
        do_plot(opts, plot.plot_cactus)


def cmd_fptg_oracle_tests(opts: argparse.Namespace) -> None:
    """Run the fp-lean tools over an fptg suite and grade every verdict against
    the MPFR/PyMPF oracle :status. Every QF_FP op fp-lean parses is bit-blasted
    (fp.fma, fp.sqrt, fp.min, fp.max, fp.roundToIntegral included), so we expect
    ALL operations to pass: the gate fails (exit 1) on any *wrong* verdict AND on
    any solver *error* -- there is no xfail tolerance."""
    import polars as pl

    if opts.run:
        do_run(opts, "fptg-oracle-tests", fptg_oracle_configs)

    data_dir = bench.RUNRESULTS_DIR / opts.guid / "data"
    if not data_dir.exists():
        print(f"no such guid: {data_dir}")
        sys.exit(1)
    df = plot.load(data_dir).with_columns(
        pl.when(pl.col("is_unsat")).then(pl.lit("unsat"))
          .when(pl.col("is_sat")).then(pl.lit("sat"))
          .otherwise(pl.lit(None)).alias("_verdict")
    )
    answered = pl.col("is_unsat") | pl.col("is_sat")
    known = pl.col("expected_status").is_in(["sat", "unsat"])

    tools = [t.strip() for t in opts.tools.split(",") if t.strip()]
    print(f"\n=== FPTG oracle test: suite '{opts.suite}' ===")
    any_wrong = False
    any_error = False
    for tool in tools:
        t = df.filter(pl.col("tool") == tool)
        if t.height == 0:
            continue
        checkable = t.filter(answered & known)
        wrong = checkable.filter(pl.col("_verdict") != pl.col("expected_status"))
        errors = t.filter(~(answered | pl.col("is_timeout") | pl.col("is_memout")))
        ntimeout = t.filter(pl.col("is_timeout")).height
        agree = checkable.height - wrong.height
        verdict = "FAIL" if (wrong.height or errors.height) else "ok"
        print(f"\n[{verdict}] {tool}: {agree} correct, {wrong.height} WRONG, "
              f"{errors.height} error, {ntimeout} timeout, "
              f"of {t.height} problems")
        if errors.height:
            any_error = True
            per_op = (errors.group_by("family").agg(pl.len().alias("n"))
                            .sort("family"))
            ops = ", ".join(f"{r['family']}={r['n']}" for r in per_op.iter_rows(named=True))
            print(f"       errors by op: {ops}")
            for r in errors.head(20).iter_rows(named=True):
                print(f"       ERROR: {r['family']}/{pathlib.Path(r['path']).name}")
        for r in wrong.iter_rows(named=True):
            any_wrong = True
            print(f"       WRONG: expected {r['expected_status']} got {r['_verdict']} "
                  f"-- {r['family']}/{pathlib.Path(r['path']).name}")

    if any_wrong or any_error:
        why = []
        if any_wrong:
            why.append("disagrees with the oracle")
        if any_error:
            why.append("errors on ops that are all expected to pass")
        print(f"\nFPTG oracle test FAILED: fp-lean {' and '.join(why)} (see above).")
        sys.exit(1)
    print("\nFPTG oracle test PASSED: every operation decides and every definite "
          "verdict agrees with the oracle.")


def add_common_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", action="store_true")
    p.add_argument("--plot", action="store_true")
    p.add_argument("--suite", choices=list(bench.SUITES), default=bench.DEFAULT_SUITE,
                   help="benchmark suite: fixes dataset dir, families, and status filter")
    p.add_argument("--guid", default="latest")
    p.add_argument("--nproblems", type=int, default=None)
    p.add_argument("--runs", type=int, default=2)
    p.add_argument("--timeout-sec", type=int, default=600, dest="timeout_sec")
    p.add_argument("--memout-mb", type=int, default=16000, dest="memout_mb")
    p.add_argument("--nproc", type=int, default=4)
    p.add_argument("--outdir", default=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="FP-lean evaluation driver.")
    sub = parser.add_subparsers(dest="command")

    dispatch: dict[str, Callable[[argparse.Namespace], None]] = {
        "cactus": cmd_cactus,
        "debug": cmd_debug,
        "fptg-oracle-tests": cmd_fptg_oracle_tests,
    }

    for name in dispatch:
        p = sub.add_parser(name, help=f"{name} experiment")
        add_common_options(p)
        if name == "debug":
            p.add_argument("--file", required=True, help="path to a single .smt2 file")
            p.set_defaults(runs=1, guid="debug")
        if name == "fptg-oracle-tests":
            p.add_argument("--tools", default="fplean,fplean-nokernel",
                           help="comma-separated tools to grade (default the fp-lean paths)")
            # A soundness gate: run+grade in one shot, default to the small float8
            # oracle set, one timing run, a short per-problem timeout. Every op is
            # expected to pass -- wrong verdicts AND solver errors fail the gate.
            p.set_defaults(run=True, suite="fptg-float8", runs=1,
                           guid="fptg-oracle-tests", timeout_sec=60)

    opts = parser.parse_args()

    if opts.command is None:
        parser.print_help()
        sys.exit(1)

    if not opts.run and not opts.plot:
        print("expected --run or --plot")
        parser.print_help()
        sys.exit(1)

    dispatch[opts.command](opts)


if __name__ == "__main__":
    main()
