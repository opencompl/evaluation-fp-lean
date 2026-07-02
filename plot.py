"""Pure plotting functions over a runresults directory."""
import argparse
import json
import pathlib
import re
from typing import TypedDict, cast

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

import bench
import lib


TIME_MS_RE: re.Pattern[str] = re.compile(r"Time elapsed:\s*(\d+)\s*ms")


def _texname(tool: str) -> str:
    """Letters-only, capitalized form of a tool name for use in LaTeX
    \\newcommand names (which may not contain hyphens or digits)."""
    return re.sub(r"[^A-Za-z]", "", tool).capitalize()


class ToolStats(TypedDict):
    nunsat: int
    nsat: int
    ntimeout: int
    nmemout: int
    nerror: int
    geomean_ms: float
    times: list[float]


def parse_raw(r: bench.RawRecord) -> bench.ParsedRecord:
    ok = not (r["is_timeout"] or r["is_memout"] or r["is_exception"])
    tool = r["tool"]
    if tool in ("fplean", "fplean-nokernel", "exhaustive-enumeration"):
        # leanwuzla reports its verdict as `sat`/`unsat` on stdout and exits 0
        # (it does not use the 10/20 SMT-COMP exit codes). Failures such as the
        # "potentially spurious counterexample" abstraction error print neither
        # token (and exit non-zero), so they count as unsolved, not sat/unsat.
        so = r["stdout"] or ""
        is_unsat = ok and "unsat" in so
        is_sat = ok and "sat" in so and "unsat" not in so
        m = TIME_MS_RE.search(so)
        elapsed_ms = int(m.group(1)) if (is_unsat and m) else r["wall_elapsed_ms"]
        return {**r, "is_unsat": is_unsat, "is_sat": is_sat, "elapsed_ms": elapsed_ms}
    if tool == "bitwuzla":
        so = r["stdout"] or ""
        return {
            **r,
            "is_unsat": ok and "unsat" in so,
            "is_sat": ok and "sat" in so and "unsat" not in so,
            "elapsed_ms": r["wall_elapsed_ms"],
        }
    raise RuntimeError(f"unknown tool: {tool}")


def load(indir: pathlib.Path) -> pl.DataFrame:
    rows: list[bench.ParsedRecord] = []
    for f in sorted(indir.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                raw = cast(bench.RawRecord, json.loads(line))
                rows.append(parse_raw(raw))
    # infer_schema_length=None scans all rows: sorted filenames put every
    # bitwuzla record (cwd=null) before the fplean ones (cwd="…/leanwuzla"), so
    # a bounded inference window would wrongly type `cwd` as Null and fail.
    return pl.from_dicts(cast(list, rows), infer_schema_length=None)


def compute_tool_stats(df: pl.DataFrame, agg: pl.DataFrame, tool: bench.ToolName) -> ToolStats:
    tool_df = df.filter(pl.col("tool") == tool)
    tool_agg = agg.filter(pl.col("tool") == tool)
    times = sorted(tool_agg["elapsed_ms_geo"].to_list())
    return {
        "nunsat": len(times),
        "nsat": tool_df.filter(pl.col("is_sat")).height,
        "ntimeout": tool_df.filter(pl.col("is_timeout")).height,
        "nmemout": tool_df.filter(pl.col("is_memout")).height,
        "nerror": tool_df.filter(pl.col("is_exception")).height,
        "geomean_ms": bench.geomean(times),
        "times": times,
    }


def plot_cactus(indir: pathlib.Path, outdir: pathlib.Path, opts: argparse.Namespace) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    df = load(indir)

    if df.filter(pl.col("is_sat")).height > 0:
        print("!!! WARNING: 'sat' results detected (unsound if benchmarks are correctness obligations) !!!")
        for row in df.filter(pl.col("is_sat")).iter_rows(named=True):
            print(f"  SAT: {row['tool']} on {row['path']} (run {row['run']})")

    expected_runs = df["run"].n_unique()
    solved = df.filter(pl.col("is_unsat"))
    agg = (
        solved.with_columns(pl.col("elapsed_ms").cast(pl.Float64).log().alias("_log"))
        .group_by(["tool", "path"])
        .agg([
            pl.col("_log").mean().exp().alias("elapsed_ms_geo"),
            pl.len().alias("n_runs"),
        ])
        .filter(pl.col("n_runs") == expected_runs)
    )

    # Only report/plot tools actually present in this run's data, in registry
    # order (a suite may run a subset of bench.TOOLS).
    present = set(df["tool"].to_list())
    tools = [t for t in bench.TOOLS if t in present]

    stats: dict[bench.ToolName, ToolStats] = {
        tool: compute_tool_stats(df, agg, tool) for tool in tools
    }

    for tool in tools:
        s = stats[tool]
        print(f"  {tool:10s} unsat={s['nunsat']:<4d} sat={s['nsat']:<3d} "
              f"timeout={s['ntimeout']:<3d} memout={s['nmemout']:<3d} "
              f"error={s['nerror']:<3d} "
              f"geomean={lib.time_str_from_ms(s['geomean_ms'])}")

    lib.set_global_matplotlib_defaults()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    for tool in tools:
        times = stats[tool]["times"]
        if not times:
            continue
        cum = np.cumsum(times)
        ax.plot(cum, range(1, len(cum) + 1),
                label=bench.tool2label[tool],
                color=bench.tool2color[tool],
                linewidth=2)
    ax.set_xscale("log")
    ax.set_xlabel("Cumulative time elapsed (ms)")
    ax.set_ylabel("# problems solved (unsat)")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.legend()
    fig.tight_layout()
    lib.save_fig(fig, str(outdir / "cactus.pdf"), str(outdir / "cactus.png"))

    nproblems_total = df["path"].n_unique()

    lines = ["%% Auto-generated LaTeX commands", "", "%% totals"]
    lines.append(bench.format_newcommand("NumProblemsTotal", nproblems_total))

    for tool in tools:
        s = stats[tool]
        cap = _texname(tool)
        per_tool: dict[str, object] = {
            f"NumUnsat{cap}":     s["nunsat"],
            f"NumSat{cap}":       s["nsat"],
            f"NumTimeout{cap}":   s["ntimeout"],
            f"NumMemout{cap}":    s["nmemout"],
            f"NumError{cap}":     s["nerror"],
            f"GeomeanTime{cap}":  lib.time_str_from_ms(s["geomean_ms"]),
            f"GeomeanMs{cap}":    f"{s['geomean_ms']:.1f}",
        }
        lines.append("")
        lines.append(f"%% {tool}")
        lines.extend(bench.format_newcommand(k, v) for k, v in per_tool.items())

    speedups = {
        f"Speedup{_texname(a)}Over{_texname(b)}":
            bench.geomean_speedup(stats[b]["geomean_ms"], stats[a]["geomean_ms"])
        for a in tools for b in tools if a != b
    }
    lines.append("")
    lines.append("%% speedups")
    lines.extend(bench.format_newcommand(k, v) for k, v in speedups.items())

    (outdir / "cactus.tex").write_text("\n".join(lines) + "\n")
