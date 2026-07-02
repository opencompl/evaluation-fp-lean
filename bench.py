#!/usr/bin/env -S uv run
"""Domain types and runner primitives for FP-lean evaluation."""
import argparse
import getpass
import hashlib
import json
import math
import os
import pathlib
import random
import re
import socket
import time
from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool
from typing import Literal, Optional, TypedDict

import lib
from runwithlimits import run_with_limits


ToolName = Literal["bitwuzla", "fplean"]

SEED: int = 42  # the SMT-LIB / SMT-COMP standard seed
# Paths default to the container layout but can be overridden via the
# environment so the harness also runs on a host checkout, e.g.
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla
BITWUZLA_PATH: pathlib.Path = pathlib.Path(
    os.environ.get("BITWUZLA_PATH", "../bitwuzla/build/src/main/bitwuzla"))
LEANWUZLA_DIR: pathlib.Path = pathlib.Path(
    os.environ.get("LEANWUZLA_DIR", "Leanwuzla"))
FPLEAN_PATH: pathlib.Path = LEANWUZLA_DIR / ".lake/build/bin/leanwuzla"
RUNRESULTS_DIR: pathlib.Path = pathlib.Path("runresults")

TOOLS: list[ToolName] = ["bitwuzla", "fplean"]

@dataclass(frozen=True)
class Suite:
    dataset_dir: pathlib.Path   # benchmark tree to walk
    families: list[str]         # top-level subdirs of dataset_dir to include
    status: Optional[str]       # keep only this (set-info :status ...), or None


# The benchmark suites, selected with `cli.py <cmd> --suite <name>`. A suite
# fully fixes which problems run: the tree, the families under it, and an
# optional (set-info :status ...) filter. We only target QF_FP (fplean cannot
# handle the quantifiers in the FP division).
#
#   wintersteiger-all-family        every wintersteiger QF_FP operator, sat and
#                                   unsat (~40k; fplean solves only a fraction).
#   wintersteiger-supported-family  just the operators fplean solves, unsat
#                                   instances only -- the problems fplean has any
#                                   hope of solving, which both solvers finish.
#                                   The default.
SUITES: dict[str, Suite] = {
    "wintersteiger-all-family": Suite(
        dataset_dir=pathlib.Path("datasets/non-incremental/QF_FP/wintersteiger"),
        families=["lt", "gt", "eq", "abs", "add", "sub", "mul", "div",
                  "fma", "max", "min", "rem", "sqrt", "toIntegral"],
        status=None,
    ),
    "wintersteiger-supported-family": Suite(
        dataset_dir=pathlib.Path("datasets/non-incremental/QF_FP/wintersteiger"),
        # ops fplean solves; it does NOT support fp.min/fp.max/fp.sqrt/
        # fp.roundToIntegral, times out on fp.rem, and does not finish fp.fma.
        families=["lt", "gt", "eq", "abs", "add", "sub", "mul", "div"],
        status="unsat",
    ),
}
DEFAULT_SUITE: str = "wintersteiger-supported-family"

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
    suite: str
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


def tool_command(tool: ToolName, path: pathlib.Path, timeout_sec: int) -> list[str]:
    if tool == "fplean":
        # leanwuzla's --timeout is the internal SAT-solver budget (default 10s);
        # match the harness limit so it isn't cut off before bitwuzla is.
        # --maxHeartbeats is raised far above the default (200000) so that simp
        # preprocessing isn't aborted before the wall-clock timeout is reached.
        return ["lake", "env", str(FPLEAN_PATH.absolute()),
                "--timeout", str(timeout_sec),
                "--maxHeartbeats", "9999999",
                str(path.absolute())]
    if tool == "bitwuzla":
        return [str(BITWUZLA_PATH.absolute()), str(path.absolute())]
    raise RuntimeError(f"unknown tool: {tool}")


def tool_cwd(tool: ToolName) -> Optional[str]:
    if tool == "fplean":
        # run from the Leanwuzla project root so `lake env` finds the lakefile/oleans.
        return str(LEANWUZLA_DIR.absolute())
    return None


_STATUS_RE = re.compile(r"set-info\s*:status\s*(sat|unsat|unknown)")


def _status_of(path: pathlib.Path) -> Optional[str]:
    m = _STATUS_RE.search(path.read_text())
    return m.group(1) if m else None


def fp_problems(suite: Suite) -> list[Problem]:
    dataset_dir = suite.dataset_dir
    out: list[Problem] = []
    for sub, _, files in dataset_dir.walk():
        for f in files:
            if f.endswith(".smt2"):
                p = sub / f
                rel = p.relative_to(dataset_dir)
                family = rel.parts[0] if len(rel.parts) > 1 else ""
                if family not in suite.families:
                    continue
                # Filter on the benchmark's declared (set-info :status ...) when
                # the suite requests one (e.g. unsat). Files are tiny so reading
                # each is cheap.
                if suite.status is not None and _status_of(p) != suite.status:
                    continue
                out.append({"family": family, "benchmark": str(rel), "path": p})
    out.sort(key=lambda d: d["benchmark"])
    return out


def sampled_problems(n: Optional[int], suite: Suite) -> list[Problem]:
    probs = fp_problems(suite)
    if n is None or n >= len(probs):
        return probs
    return random.Random(SEED).sample(probs, n)


def run_one(cfg: Config, timeout_sec: int, memout_mb: int, outdir: pathlib.Path) -> str:
    cmd = tool_command(cfg["tool"], cfg["path"], timeout_sec)
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
    return f"{cfg['tool']} r{cfg['run']} {cfg['benchmark']}"


def run_many(
    configs: list[Config],
    timeout_sec: int,
    memout_mb: int,
    nproc: int,
    outdir: pathlib.Path,
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    worker = partial(run_one, timeout_sec=timeout_sec, memout_mb=memout_mb, outdir=outdir)
    total = len(configs)
    with Pool(nproc) as pool:
        for i, label in enumerate(pool.imap_unordered(worker, configs), 1):
            print(f"[{i}/{total}] {label}")
