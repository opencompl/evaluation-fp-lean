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
    probs = bench.sampled_problems(opts.nproblems)
    out: list[bench.Config] = []
    for tool in bench.TOOLS:
        for run in range(opts.runs):
            for p in probs:
                out.append({
                    "tool": tool,
                    "run": run,
                    "family": p["family"],
                    "benchmark": p["benchmark"],
                    "path": p["path"],
                })
    return out


def do_run(opts: argparse.Namespace, config_name: str, configs_fn: ConfigFn) -> None:
    outdir = bench.RUNRESULTS_DIR / opts.guid
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)

    configs = configs_fn(opts)
    print(f"config '{config_name}': {len(configs)} datapoints -> {outdir}")
    bench.run_many(configs, opts.timeout_sec, opts.memout_mb, opts.nproc, outdir)

    manifest: bench.Manifest = {
        "config_name": config_name,
        "tools": bench.TOOLS,
        "nproblems": opts.nproblems,
        "runs": opts.runs,
        "timeout_sec": opts.timeout_sec,
        "memout_mb": opts.memout_mb,
        "seed": bench.SEED,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_hash": lib.git_hash(),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    bench.write_config_tex(outdir, opts)
    bench.write_machine_data_tex(outdir)


def do_plot(opts: argparse.Namespace, plot_fn: PlotFn) -> None:
    indir = bench.RUNRESULTS_DIR / opts.guid
    if not indir.exists():
        print(f"no such guid: {indir}")
        sys.exit(1)
    outdir = pathlib.Path(opts.outdir) if opts.outdir else (indir / "plots" / opts.command)
    plot_fn(indir, outdir, opts)


def cmd_cactus(opts: argparse.Namespace) -> None:
    if opts.run:
        do_run(opts, "cactus", cactus_configs)
    if opts.plot:
        do_plot(opts, plot.plot_cactus)


def add_common_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", action="store_true")
    p.add_argument("--plot", action="store_true")
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
    }

    for name in dispatch:
        p = sub.add_parser(name, help=f"{name} experiment")
        add_common_options(p)

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
