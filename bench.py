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


ToolName = Literal["bitwuzla", "fplean", "fplean-nokernel", "fplean-nancanon", "exhaustive-enumeration"]

SEED: int = 42  # the SMT-LIB / SMT-COMP standard seed
# Paths default to the container layout but can be overridden via the
# environment so the harness also runs on a host checkout, e.g.
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla
BITWUZLA_PATH: pathlib.Path = pathlib.Path(
    os.environ.get("BITWUZLA_PATH", "../bitwuzla/build/src/main/bitwuzla"))
LEANWUZLA_DIR: pathlib.Path = pathlib.Path(
    os.environ.get("LEANWUZLA_DIR", "leanwuzla"))
FPLEAN_PATH: pathlib.Path = LEANWUZLA_DIR / ".lake/build/bin/leanwuzla"
RUNRESULTS_DIR: pathlib.Path = pathlib.Path("runresults")

# The registry of all known tools, in display order. Which subset actually runs
# is per-suite (see Suite.tools_to_run); plotting filters this to the tools present in
# the data.
TOOLS: list[ToolName] = ["bitwuzla", "fplean", "fplean-nokernel", "fplean-nancanon", "exhaustive-enumeration"]

@dataclass(frozen=True)
class Suite:
    dataset_dir: pathlib.Path   # benchmark tree to walk
    families: list[str]         # top-level subdirs of dataset_dir to include
    keep_problems_with_status: Optional[str]  # keep only files whose
                                # (set-info :status ...) equals this, or None to
                                # keep every problem regardless of status
    tools_to_run: list[ToolName]   # which solvers to run for this suite
    tools_to_plot: list[ToolName]  # which of the run tools to draw on the cactus
                                # curve -- a subset of tools_to_run (the rest are
                                # still run and reported in the summary/macros,
                                # just not plotted). Every suite sets it.
    name_regex: str = ".*"      # keep only files whose name matches this regex
    stratified: bool = False    # if True, --nproblems is a *per-family* cap (see
                                # sampled_problems); else it is a total sample size

    def __post_init__(self) -> None:
        extra = set(self.tools_to_plot) - set(self.tools_to_run)
        if extra:
            raise ValueError(
                f"tools_to_plot {sorted(extra)} not a subset of tools_to_run")


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
#   instcombine-fp-problems         QF_FP equivalence checks extracted from LLVM
#                                   InstCombine tests (llvm-fp-bv-smt-extractor).
# The normal fp-lean bundle: all axiom-free (NaN-canonicalization off). The
# special axiom-relying fplean-nancanon is added only to the suite that measures
# its performance value (griggio-chains).
_LEAN_TOOLS: list[ToolName] = ["bitwuzla", "fplean", "fplean-nokernel"]

# The 12 operation subdirectories in each fptg-testsuite format. fplean does not
# support all of them (it errors on e.g. fp.max/min/sqrt/rem/roundToIntegral),
# but including them all keeps the soundness comparison comprehensive -- those
# show up as solver errors, distinct from disagreements (wrong verdicts).
_FPTG_OPS: list[str] = [
    "fp.abs", "fp.add", "fp.div", "fp.fma", "fp.max", "fp.min",
    "fp.mul", "fp.neg", "fp.rem", "fp.roundToIntegral", "fp.sqrt", "fp.sub",
]

SUITES: dict[str, Suite] = {
    "wintersteiger-all-family": Suite(
        dataset_dir=pathlib.Path("datasets/non-incremental/QF_FP/wintersteiger"),
        families=["lt", "gt", "eq", "abs", "add", "sub", "mul", "div",
                  "fma", "max", "min", "rem", "sqrt", "toIntegral"],
        keep_problems_with_status=None,
        tools_to_run=_LEAN_TOOLS,
        tools_to_plot=_LEAN_TOOLS,
    ),
    "wintersteiger-uniform-family": Suite(
        # Every wintersteiger operator, unsat only, sampled UNIFORMLY per
        # operator: stratified=True makes --nproblems a *per-family* cap, so each
        # of the 14 operator families contributes min(nproblems, family-size)
        # problems and is equally weighted -- unlike wintersteiger-all-family /
        # -supported-family, where --nproblems is a flat total over the pooled
        # families. unsat-only keeps verdicts oracle-checkable. fplean errors or
        # times out on the ops it does not support (fp.min/max/sqrt/
        # roundToIntegral/rem/fma) -- informative for per-operator coverage.
        dataset_dir=pathlib.Path("datasets/non-incremental/QF_FP/wintersteiger"),
        families=["lt", "gt", "eq", "abs", "add", "sub", "mul", "div",
                  "fma", "max", "min", "rem", "sqrt", "toIntegral"],
        keep_problems_with_status="unsat",
        tools_to_run=["bitwuzla", "fplean", "fplean-nokernel"],
        tools_to_plot=["bitwuzla", "fplean", "fplean-nokernel"],
        stratified=True,
    ),
    "wintersteiger-supported-family": Suite(
        dataset_dir=pathlib.Path("datasets/non-incremental/QF_FP/wintersteiger"),
        # ops fplean solves; it does NOT support fp.min/fp.max/fp.sqrt/
        # fp.roundToIntegral, times out on fp.rem, and does not finish fp.fma.
        families=["lt", "gt", "eq", "abs", "add", "sub", "mul", "div"],
        keep_problems_with_status="unsat",
        tools_to_run=_LEAN_TOOLS,
        tools_to_plot=_LEAN_TOOLS,
    ),
    "instcombine-fp-problems": Suite(
        # ~101 QF_FP optimization-equivalence checks extracted from LLVM
        # InstCombine tests. No :status is known, so all of them are run.
        dataset_dir=pathlib.Path("datasets/instcombine"),
        families=["fp-problems"],
        keep_problems_with_status=None,
        tools_to_run=_LEAN_TOOLS,
        tools_to_plot=_LEAN_TOOLS,
    ),
    "instcombine-small": Suite(
        # The 25 constant-free (width-parametric) InstCombine identities
        # reparametrized to several widths. e5m2 (5 3, 256 values/var) and e5m4
        # (5 5, 1024 values/var) are the tiny tiers where exhaustive-enumeration
        # is near-instant. isoslow is an "iso-difficulty" tier that picks the
        # width PER variable-count (1-var (8 16), 2-var (8 3), 3-var (5 2)) so
        # every identity enumerates in ~25-35s -- large enough to be genuinely
        # slow, but still terminating under a 60s timeout, so the cactus shows
        # enumeration's exponential wall against the fast SMT tools. Regenerate
        # with datasets/gen-instcombine-small-isoslow.py. All have 1-3 free FP
        # variables.
        dataset_dir=pathlib.Path("datasets/instcombine-small"),
        families=["e5m2", "e5m4", "isoslow"],
        keep_problems_with_status=None,
        tools_to_run=["bitwuzla", "fplean", "fplean-nokernel", "exhaustive-enumeration"],
        tools_to_plot=["bitwuzla", "fplean", "fplean-nokernel", "exhaustive-enumeration"],
    ),
    "griggio-chains": Suite(
        # Real-world QF_FP problems that are *chains* of floating-point ops (nested
        # fp.add/sub/mul/div/fma), from Griggio's fmcad12 set. These exercise the
        # pack/unpack-cancellation (NaN-canonicalization) pass -- which the normal
        # fplean disables (axiom-free) and the special fplean-nancanon enables
        # (--fp-normalize on, resting on the Canonical_all axiom). The pass rewrites
        # `euf.pack.unpack = euf`, which only fires when one op's pack meets its
        # parent's unpack -- i.e. exactly on chains. So this is the suite that
        # measures the axiom's performance value: it runs and plots both fplean
        # (canon off) and fplean-nancanon (canon on). Restricted to unsat + float32
        # (8 24) + fplean-supported ops via name_regex: the test_v* (random nested
        # formulas, 27-175 fp ops), sine.N and square.N (Taylor-series chains)
        # files -- ~34 total, a natural chain-depth sweep. The add_*/mul_* unsat
        # files use `to_fp` (unsupported) and qurt/pow are float64 (costly); both
        # excluded.
        dataset_dir=pathlib.Path("datasets/non-incremental/QF_FP/griggio"),
        families=["fmcad12"],
        keep_problems_with_status="unsat",
        name_regex=r"^(test_v|sine\.\d|square\.\d)",
        tools_to_run=["bitwuzla", "fplean", "fplean-nancanon"],
        tools_to_plot=["bitwuzla", "fplean", "fplean-nancanon"],
    ),
    "smtlib-rand": Suite(
        # A cross-family QF_FP sample: every top-level SMT-LIB QF_FP family, not
        # just wintersteiger (which is ~99% of the 40.4k-file set). Stratified so
        # the tiny real-world families are represented -- `--nproblems` is a
        # PER-FAMILY cap, so each family contributes min(cap, size) problems
        # (e.g. cap=300 -> 712 files: wintersteiger 300, griggio 214, Vector 91,
        # schanda 44, ramalho 36, UA2019 24, Heizmann 2, UA2023 1). status=None:
        # sat, unsat and unknown are all kept (a coverage survey, not an oracle
        # set -- plot.py grades disagreement only where :status is known). QF_FP
        # is quantifier-free throughout. wintersteiger is one family here (rooted
        # at the QF_FP dir), so its sample spans every operator subdir including
        # the ones fplean does not support -- informative for coverage.
        dataset_dir=pathlib.Path("datasets/non-incremental/QF_FP"),
        families=["20170501-Heizmann-UltimateAutomizer",
                  "20190429-UltimateAutomizerSvcomp2019",
                  "20210211-Vector", "20230321-UltimateAutomizerSvcomp2023",
                  "griggio", "ramalho", "schanda", "wintersteiger"],
        keep_problems_with_status=None,
        tools_to_run=_LEAN_TOOLS,
        tools_to_plot=_LEAN_TOOLS,
        stratified=True,
    ),
    # Template "small" suite -- the only place `exhaustive-enumeration` runs, so
    # that solver stays off by default. Left COMMENTED because there is no working
    # target yet: exhaustive-enumeration is quantifier-free only (leanwuzla's
    # parser rejects `exists`), and the only small-width data we have -- the 805
    # width-3/5 (256-value) Preiner files -- each contain one `exists`, so it
    # errors on them. Repoint this at quantifier-free small-width problems (or
    # once leanwuzla learns to enumerate `exists`) and uncomment.
    # "preiner-small": Suite(
    #     dataset_dir=pathlib.Path("datasets/non-incremental/FP"),
    #     families=["2019-Preiner"],
    #     keep_problems_with_status=None,
    #     name_regex=r"^3_5_",
    #     tools_to_run=["bitwuzla", "exhaustive-enumeration"],
    #     tools_to_plot=["bitwuzla", "exhaustive-enumeration"],
    # ),

    # fptg-testsuite (Schanda's fp_test_generator): ground QF_FP tests whose
    # (set-info :status) is an MPFR/PyMPF oracle ground truth -- a differential
    # soundness suite. NOTE: bitwuzla must be built with --fpexp to accept the
    # non-standard float8 (3/5) and bfloat16 (8/8) formats (the container
    # bitwuzla is; the homebrew one is not), else it errors on every file.
    # float8 (8-bit, 256 values) is small enough for exhaustive-enumeration.
    "fptg-float8": Suite(
        dataset_dir=pathlib.Path("datasets/fptg-testsuite/QF_FP/tests_validated/float8"),
        families=_FPTG_OPS,
        keep_problems_with_status=None,
        tools_to_run=["bitwuzla", "fplean", "fplean-nokernel", "exhaustive-enumeration"],
        tools_to_plot=["bitwuzla", "fplean", "fplean-nokernel", "exhaustive-enumeration"],
    ),
    "fptg-float16": Suite(
        dataset_dir=pathlib.Path("datasets/fptg-testsuite/QF_FP/tests_validated/float16"),
        families=_FPTG_OPS,
        keep_problems_with_status=None,
        tools_to_run=["bitwuzla", "fplean", "fplean-nokernel"],
        tools_to_plot=["bitwuzla", "fplean", "fplean-nokernel"],
    ),
    "fptg-bfloat16": Suite(
        dataset_dir=pathlib.Path("datasets/fptg-testsuite/QF_FP/tests_validated/bfloat16"),
        families=_FPTG_OPS,
        keep_problems_with_status=None,
        tools_to_run=["bitwuzla", "fplean", "fplean-nokernel"],
        tools_to_plot=["bitwuzla", "fplean", "fplean-nokernel"],
    ),
}
DEFAULT_SUITE: str = "wintersteiger-supported-family"

tool2color: dict[ToolName, str] = {
    "bitwuzla": "#FFAB40", "fplean": "#2E7D32", "fplean-nokernel": "#1565C0",
    "fplean-nancanon": "#C62828", "exhaustive-enumeration": "#8E24AA"}
tool2label: dict[ToolName, str] = {
    "bitwuzla": "Bitwuzla", "fplean": "FP-Lean", "fplean-nokernel": "FP-Lean (no kernel)",
    "fplean-nancanon": "FP-Lean + NaN-canon", "exhaustive-enumeration": "Exhaustive enum"}


class Problem(TypedDict):
    family: str
    benchmark: str
    path: pathlib.Path
    # The benchmark's declared (set-info :status ...) -- the expected/reference
    # answer ("sat"/"unsat"/"unknown"), or None if unlabelled. For the fptg
    # suites this is an MPFR-oracle-validated ground truth.
    expected_status: Optional[str]


class Config(TypedDict):
    tool: ToolName
    run: int
    family: str
    benchmark: str
    path: pathlib.Path
    expected_status: Optional[str]


class RawRecord(TypedDict):
    tool: ToolName
    run: int
    family: str
    benchmark: str
    path: str
    expected_status: Optional[str]
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
    if tool in ("fplean", "fplean-nokernel", "fplean-nancanon", "exhaustive-enumeration"):
        # leanwuzla's --timeout is the internal SAT-solver budget (default 10s);
        # match the harness limit so it isn't cut off before bitwuzla is.
        # --maxHeartbeats is raised far above the default (200000) so that simp
        # preprocessing isn't aborted before the wall-clock timeout is reached.
        # --maxRecDepth is raised above the default (512) so the kernel re-check
        # of a deep bvDecide reflection proof doesn't abort with "maximum
        # recursion depth reached" (e.g. instcombine-small's multi-use fmul
        # identity needs ~10k; 100000 gives ample headroom without risking a
        # native stack overflow).
        cmd = ["lake", "env", str(FPLEAN_PATH.absolute()),
               "--timeout", str(timeout_sec),
               "--maxHeartbeats", "9999999",
               "--maxRecDepth", "100000"]
        # NaN-canonicalization (the staged pack/unpack-cancellation simp) rests on
        # the unproven `Canonical_all` axiom, so we DISABLE it for the normal
        # profiles: their reported results must not depend on a new axiom. Only the
        # special `fplean-nancanon` profile leaves it on, so the axiom's
        # performance value can be measured against the axiom-free default.
        if tool != "fplean-nancanon":
            cmd.append("--disable-fp-normalize")
        if tool == "fplean-nokernel":
            # skip the Lean kernel re-check of the bvDecide reflection proof;
            # only the LRAT certificate is verified (Leanwuzla decideSmtNoKernel).
            cmd.append("--disableKernel")
        if tool == "exhaustive-enumeration":
            # decide the goal by native-evaluating a Decidable instance over all
            # FP values instead of bv_decide (only feasible for tiny bit-widths).
            cmd.append("--exhaustive-enumeration")
        cmd.append(str(path.absolute()))
        return cmd
    if tool == "bitwuzla":
        return [str(BITWUZLA_PATH.absolute()), str(path.absolute())]
    raise RuntimeError(f"unknown tool: {tool}")


def tool_cwd(tool: ToolName) -> Optional[str]:
    if tool in ("fplean", "fplean-nokernel", "fplean-nancanon", "exhaustive-enumeration"):
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
                # Restrict to filenames matching the suite's regex (default ".*"
                # matches everything; e.g. r"^3_5_" picks a single bit-width).
                if not re.search(suite.name_regex, f):
                    continue
                # Read the declared (set-info :status ...) once: it is both the
                # optional suite filter and the expected/reference answer we
                # record. Files are tiny so reading each is cheap.
                expected = _status_of(p)
                if (suite.keep_problems_with_status is not None
                        and expected != suite.keep_problems_with_status):
                    continue
                out.append({"family": family, "benchmark": str(rel), "path": p,
                            "expected_status": expected})
    out.sort(key=lambda d: d["benchmark"])
    return out


def sampled_problems(n: Optional[int], suite: Suite) -> list[Problem]:
    probs = fp_problems(suite)
    if n is None:
        return probs
    if suite.stratified:
        # `n` is a *per-family* cap: take up to n problems from each family so
        # every family is represented regardless of the huge size imbalance
        # (in QF_FP, wintersteiger is ~99% of the set, so a uniform sample would
        # be ~all wintersteiger and draw 0 from the tiny families). Deterministic
        # (seed 42): one RNG, families visited in sorted order.
        by_family: dict[str, list[Problem]] = {}
        for p in probs:
            by_family.setdefault(p["family"], []).append(p)
        rng = random.Random(SEED)
        out: list[Problem] = []
        for family in sorted(by_family):
            fam = by_family[family]
            out.extend(fam if n >= len(fam) else rng.sample(fam, n))
        out.sort(key=lambda d: d["benchmark"])
        return out
    if n >= len(probs):
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
        "expected_status": cfg["expected_status"],
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
