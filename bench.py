#!/usr/bin/env -S uv run
"""Domain types and runner primitives for FP-lean evaluation."""
import argparse
import getpass
import hashlib
import json
import math
import pathlib
import random
import socket
import subprocess
import time
from multiprocessing import Pool
from typing import Literal, Optional, TypedDict

import lib
from runwithlimits import run_with_limits


ToolName = Literal["bitwuzla", "fplean"]

SEED: int = 0x5FE7
BITWUZLA_PATH: pathlib.Path = pathlib.Path("../bitwuzla/build/src/main/bitwuzla")
FPLEAN_PATH: pathlib.Path = pathlib.Path("../lean-mlir/Blase/.lake/build/bin/blasewuzla")
FP_DATASET_DIR: pathlib.Path = pathlib.Path("datasets/FP")
RUNRESULTS_DIR: pathlib.Path = pathlib.Path("runresults")

TOOLS: list[ToolName] = ["bitwuzla", "fplean"]

tool2color: dict[ToolName, str] = {"bitwuzla": "#FFAB40", "fplean": "#2E7D32"}
tool2label: dict[ToolName, str] = {"bitwuzla": "Bitwuzla", "fplean": "FP-Lean"}


class Problem(TypedDict):
    family: str
    benchmark: str
    path: pathlib.Path


class Config(TypedDict):
    tool: ToolName
    run: int
    family: str
    benchmark: str
    path: pathlib.Path


class RawRecord(TypedDict):
    tool: ToolName
    run: int
    family: str
    benchmark: str
    path: str
    cmd: list[str]
    cwd: Optional[str]
    returncode: int
    stdout: str
    stderr: str
    is_memout: bool
    is_timeout: bool
    is_exception: bool
    exception: Optional[str]
    wall_elapsed_ms: int


class ParsedRecord(RawRecord):
    is_unsat: bool
    is_sat: bool
    elapsed_ms: int


class Manifest(TypedDict):
    config_name: str
    tools: list[ToolName]
    nproblems: Optional[int]
    runs: int
    timeout_sec: int
    memout_mb: int
    seed: int
    timestamp_utc: str
    git_hash: str


def geomean(xs: list[float]) -> float:
    logs = [math.log(x) for x in xs if x > 0]
    return math.exp(sum(logs) / len(logs)) if logs else 0.0


def geomean_speedup(a: float, b: float) -> float:
    a = float(a)
    b = float(b)
    assert a >= 0
    assert b >= 0
    if a == 0:
        return 0.0
    if b == 0:
        return float("inf")
    return a / b


def format_newcommand(name: str, value: object, precision: int = 1) -> str:
    if isinstance(value, float):
        value_str = f"{value:.{precision}f}"
    else:
        value_str = str(value)
    return f"\\newcommand{{\\{name}}}{{{value_str}}}"


def write_config_tex(folder: pathlib.Path, opts: argparse.Namespace) -> None:
    lines = ["%% Auto-generated LaTeX commands"]
    lines.append(format_newcommand("ConfigTimeoutSec", opts.timeout_sec))
    lines.append(format_newcommand("ConfigMemoutMb", opts.memout_mb))
    lines.append(format_newcommand("ConfigNproc", opts.nproc))
    lines.append(format_newcommand("ConfigRuns", opts.runs))
    if opts.nproblems is not None:
        lines.append(format_newcommand("ConfigNproblems", opts.nproblems))
    (folder / "config.tex").write_text("\n".join(lines) + "\n")


def write_machine_data_tex(folder: pathlib.Path) -> None:
    specs = lib.get_system_specs()
    lines = ["%% Auto-generated LaTeX commands"]
    lines.append(format_newcommand("MachineUserName", getpass.getuser()))
    lines.append(format_newcommand("MachineHostname", socket.gethostname()))
    lines.append(format_newcommand("SystemSpecsProcessorName", specs.processor_name))
    lines.append(format_newcommand("SystemSpecsClockMhz", specs.clock_mhz))
    lines.append(format_newcommand("SystemSpecsCores", specs.cores))
    lines.append(format_newcommand("SystemSpecsMemoryGb", specs.memory_gb))
    (folder / "triple.tex").write_text("\n".join(lines) + "\n")


def tool_command(tool: ToolName, path: pathlib.Path) -> list[str]:
    if tool == "fplean":
        return ["lake", "env", str(FPLEAN_PATH.absolute()),
                "--elimIte", "--preconditionSub", "--elimSub",
                str(path.absolute())]
    if tool == "bitwuzla":
        return [str(BITWUZLA_PATH.absolute()), str(path.absolute())]
    raise RuntimeError(f"unknown tool: {tool}")


def tool_cwd(tool: ToolName) -> Optional[str]:
    if tool == "fplean":
        return str(FPLEAN_PATH.parent.absolute())
    return None


def fp_problems() -> list[Problem]:
    out: list[Problem] = []
    for sub, _, files in FP_DATASET_DIR.walk():
        for f in files:
            if f.endswith(".smt2"):
                p = sub / f
                rel = p.relative_to(FP_DATASET_DIR)
                family = rel.parts[0] if len(rel.parts) > 1 else ""
                out.append({"family": family, "benchmark": str(rel), "path": p})
    out.sort(key=lambda d: d["benchmark"])
    return out


def sampled_problems(n: Optional[int]) -> list[Problem]:
    probs = fp_problems()
    if n is None:
        return probs
    return random.Random(SEED).sample(probs, n)


def run_one(cfg: Config, timeout_sec: int, memout_mb: int, outdir: pathlib.Path) -> None:
    cmd = tool_command(cfg["tool"], cfg["path"])
    cwd = tool_cwd(cfg["tool"])
    t0 = time.time()
    r = run_with_limits(cmd, timeout_sec=timeout_sec, memout_mb=memout_mb, cwd=cwd)
    t1 = time.time()
    record: RawRecord = {
        "tool": cfg["tool"],
        "run": cfg["run"],
        "family": cfg["family"],
        "benchmark": cfg["benchmark"],
        "path": str(cfg["path"]),
        "cmd": cmd,
        "cwd": cwd,
        "returncode": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr,
        "is_memout": r.is_memout,
        "is_timeout": r.is_timeout,
        "is_exception": r.is_exception,
        "exception": str(r.exception) if r.exception else None,
        "wall_elapsed_ms": int((t1 - t0) * 1000),
    }
    key = hashlib.sha1(cfg["benchmark"].encode()).hexdigest()[:16]
    fpath = outdir / f"{cfg['tool']}__r{cfg['run']}__{key}.jsonl"
    fpath.write_text(json.dumps(record) + "\n")


def _run_one_star(a: tuple[Config, int, int, pathlib.Path]) -> None:
    run_one(*a)


def run_many(
    configs: list[Config],
    timeout_sec: int,
    memout_mb: int,
    nproc: int,
    outdir: pathlib.Path,
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    args = [(c, timeout_sec, memout_mb, outdir) for c in configs]
    total = len(configs)
    with Pool(nproc) as pool:
        for i, _ in enumerate(pool.imap_unordered(_run_one_star, args), 1):
            print(f"[{i}/{total}]")


def git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    except Exception:
        return "unknown"
