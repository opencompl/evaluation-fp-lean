import argparse
import json
import re
import sys
import pathlib
from typing import cast, TypedDict
import numpy as np
import polars as pl
import matplotlib.pyplot as plt
import benchgod
import lib


TIME_MS_RE: re.Pattern[str] = re.compile(r"Time elapsed:\s*(\d+)\s*ms")


class ToolStats(TypedDict):
    nunsat: int
    nsat: int
    ntimeout: int
    nmemout: int
    nerror: int
    geomean_ms: float
    times: list[float]


class AllToolStats(TypedDict):
    bitwuzla: ToolStats
    fplean: ToolStats


def parse_raw(r: benchgod.RawRecord) -> benchgod.ParsedRecord:
    ok: bool = not (r["is_timeout"] or r["is_memout"] or r["is_exception"])
    tool: benchgod.ToolName = r["tool"]
    parsed: benchgod.ParsedRecord
    if tool == "fplean":
        is_unsat: bool = ok and r["returncode"] == 20
        is_sat: bool = ok and r["returncode"] == 10
        m = TIME_MS_RE.search(r["stdout"] or "")
        elapsed_ms: int = int(m.group(1)) if (is_unsat and m) else r["wall_elapsed_ms"]
        parsed = {
            **r,
            "is_unsat": is_unsat,
            "is_sat": is_sat,
            "elapsed_ms": elapsed_ms,
        }
    elif tool == "bitwuzla":
        so: str = r["stdout"] or ""
        parsed = {
            **r,
            "is_unsat": ok and "unsat" in so,
            "is_sat": ok and "sat" in so and "unsat" not in so,
            "elapsed_ms": r["wall_elapsed_ms"],
        }
    else:
        raise RuntimeError(f"unknown tool: {tool}")
    return parsed


def load(indir: pathlib.Path) -> pl.DataFrame:
    rows: list[benchgod.ParsedRecord] = []
    for f in sorted(indir.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                raw: benchgod.RawRecord = cast(benchgod.RawRecord, json.loads(line))
                rows.append(parse_raw(raw))
    return pl.from_dicts(cast(list, rows))


def compute_tool_stats(df: pl.DataFrame, agg: pl.DataFrame, tool: benchgod.ToolName) -> ToolStats:
    tool_df: pl.DataFrame = df.filter(pl.col("tool") == tool)
    tool_agg: pl.DataFrame = agg.filter(pl.col("tool") == tool)
    times: list[float] = sorted(tool_agg["elapsed_ms_geo"].to_list())
    stats: ToolStats = {
        "nunsat": len(times),
        "nsat": tool_df.filter(pl.col("is_sat")).height,
        "ntimeout": tool_df.filter(pl.col("is_timeout")).height,
        "nmemout": tool_df.filter(pl.col("is_memout")).height,
        "nerror": tool_df.filter(pl.col("is_exception")).height,
        "geomean_ms": benchgod.geomean(times),
        "times": times,
    }
    return stats


def plot_cactus(indir: pathlib.Path, outdir: pathlib.Path, opts: argparse.Namespace) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    df: pl.DataFrame = load(indir)

    if df.filter(pl.col("is_sat")).height > 0:
        print("!!! WARNING: 'sat' results detected (unsound if benchmarks are correctness obligations) !!!")
        for row in df.filter(pl.col("is_sat")).iter_rows(named=True):
            print(f"  SAT: {row['tool']} on {row['path']} (run {row['run']})")

    expected_runs: int = df["run"].n_unique()
    solved: pl.DataFrame = df.filter(pl.col("is_unsat"))

    agg: pl.DataFrame = (
        solved.with_columns(pl.col("elapsed_ms").cast(pl.Float64).log().alias("_log"))
        .group_by(["tool", "path"])
        .agg([
            pl.col("_log").mean().exp().alias("elapsed_ms_geo"),
            pl.len().alias("n_runs"),
        ])
        .filter(pl.col("n_runs") == expected_runs)
    )

    stats: AllToolStats = {
        "bitwuzla": compute_tool_stats(df, agg, "bitwuzla"),
        "fplean": compute_tool_stats(df, agg, "fplean"),
    }

    for tool in benchgod.TOOLS:
        s: ToolStats = stats[tool]
        print(f"  {tool:10s} unsat={s['nunsat']:<4d} sat={s['nsat']:<3d} "
              f"timeout={s['ntimeout']:<3d} memout={s['nmemout']:<3d} "
              f"error={s['nerror']:<3d} "
              f"geomean={lib.time_str_from_ms(s['geomean_ms'])}")

    lib.set_global_matplotlib_defaults()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    for tool in benchgod.TOOLS:
        times: list[float] = stats[tool]["times"]
        if not times:
            continue
        cum = np.cumsum(times)
        ax.plot(cum, range(1, len(cum) + 1),
                label=benchgod.tool2label[tool],
                color=benchgod.tool2color[tool],
                linewidth=2)
    ax.set_xscale("log")
    ax.set_xlabel("Cumulative time elapsed (ms)")
    ax.set_ylabel("# problems solved (unsat)")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.legend()
    fig.tight_layout()
    lib.save_fig(fig, str(outdir / "cactus.pdf"), str(outdir / "cactus.png"))

    nproblems_total: int = df["path"].n_unique()

    lines: list[str] = ["%% Auto-generated LaTeX commands"]
    lines.append("")
    lines.append("%% totals")
    lines.append(benchgod.format_newcommand("NumProblemsTotal", nproblems_total))

    for tool in benchgod.TOOLS:
        s: ToolStats = stats[tool]
        cap: str = tool.capitalize()
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
        lines.extend(benchgod.format_newcommand(k, v) for k, v in per_tool.items())

    speedups: dict[str, float] = {
        f"Speedup{a.capitalize()}Over{b.capitalize()}":
            benchgod.geomean_speedup_calc(stats[b]["geomean_ms"], stats[a]["geomean_ms"])
        for a in benchgod.TOOLS for b in benchgod.TOOLS if a != b
    }
    lines.append("")
    lines.append("%% speedups")
    lines.extend(benchgod.format_newcommand(k, v) for k, v in speedups.items())

    with open(outdir / "cactus.tex", "w") as f:
        f.write("\n".join(lines) + "\n")


benchgod.PLOTS["cactus"] = plot_cactus


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p: argparse.ArgumentParser = sub.add_parser("plot", help="Plot from a guid of runresults.")
    p.add_argument("plot_name", help=f"one of: {list(benchgod.PLOTS)}")
    p.add_argument("--guid", default="latest")
    p.add_argument("--outdir", default=None)


def cmd(opts: argparse.Namespace) -> None:
    if opts.plot_name not in benchgod.PLOTS:
        print(f"unknown plot '{opts.plot_name}'. valid: {list(benchgod.PLOTS)}")
        sys.exit(1)

    indir: pathlib.Path = benchgod.RUNRESULTS_DIR / opts.guid
    if not indir.exists():
        print(f"no such guid: {indir}")
        sys.exit(1)

    outdir: pathlib.Path = pathlib.Path(opts.outdir) if opts.outdir else (indir / "plots" / opts.plot_name)
    plot_fn = benchgod.PLOTS[opts.plot_name]
    plot_fn(indir, outdir, opts)
