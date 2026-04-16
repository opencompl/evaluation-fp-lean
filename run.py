import argparse
import json
import pathlib
import shutil
import sys
import time
import benchgod


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p: argparse.ArgumentParser = sub.add_parser("run", help="Run a benchmark configuration.")
    p.add_argument("config_name", help=f"one of: {list(benchgod.CONFIGURATIONS)}")
    p.add_argument("--guid", default="latest")
    p.add_argument("--nproblems", type=int, default=None)
    p.add_argument("--runs", type=int, default=2)
    p.add_argument("--timeout-sec", type=int, default=600, dest="timeout_sec")
    p.add_argument("--memout-mb", type=int, default=16000, dest="memout_mb")
    p.add_argument("--nproc", type=int, default=4)


def cmd(opts: argparse.Namespace) -> None:
    if opts.config_name not in benchgod.CONFIGURATIONS:
        print(f"unknown config '{opts.config_name}'. valid: {list(benchgod.CONFIGURATIONS)}")
        sys.exit(1)

    outdir: pathlib.Path = benchgod.RUNRESULTS_DIR / opts.guid
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)

    configs: list[benchgod.Config] = benchgod.CONFIGURATIONS[opts.config_name](opts)
    print(f"config '{opts.config_name}': {len(configs)} datapoints -> {outdir}")

    benchgod.run_many(configs, opts.timeout_sec, opts.memout_mb, opts.nproc, outdir)

    manifest: benchgod.Manifest = {
        "config_name": opts.config_name,
        "tools": benchgod.TOOLS,
        "nproblems": opts.nproblems,
        "runs": opts.runs,
        "timeout_sec": opts.timeout_sec,
        "memout_mb": opts.memout_mb,
        "seed": benchgod.SEED,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_hash": benchgod.git_hash(),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    benchgod.write_config_tex(outdir, opts)
    benchgod.write_machine_data_tex(outdir)
