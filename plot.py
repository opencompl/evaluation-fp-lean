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

# Cactus plot dimensions (inches), sized for a full-text-width ACM (`acmart`)
# figure: the `acmart`/sigconf `\textwidth` is ~7.0in (span both columns with a
# `figure*`), and the height is ~25% of the ~9.25in `\textheight` (a wide, short
# cactus). Include the PDF at `\includegraphics[width=\textwidth]{cactus.pdf}`
# for a 1:1 fit.
CACTUS_WIDTH_IN: float = 7.0
CACTUS_HEIGHT_IN: float = 2.3

# Which tools appear on the cactus *curve* is per-suite: each Suite lists a
# tools_to_plot subset of tools_to_run (bench.py). Tools that are run but not
# plotted are still reported in the summary and the LaTeX macros.


def _texname(tool: str) -> str:
    """Letters-only, capitalized form of a tool name for use in LaTeX
    \\newcommand names (which may not contain hyphens or digits)."""
    return re.sub(r"[^A-Za-z]", "", tool).capitalize()


_DIGIT_WORD = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four",
               "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}


def _texprefix(name: str) -> str:
    """A letters-only CamelCase LaTeX-safe prefix from a suite name. Unlike
    `_texname` it preserves digits (as words) so suites like `fptg-float8` and
    `fptg-float16` stay distinct (-> FptgFloatEight vs FptgFloatOneSix)."""
    out = []
    for word in re.split(r"[^A-Za-z0-9]+", name):
        chunk = "".join(_DIGIT_WORD[c] if c.isdigit() else c for c in word)
        if chunk:
            out.append(chunk[:1].upper() + chunk[1:])
    return "".join(out)


class ToolStats(TypedDict):
    nunsat: int
    nsat: int
    ntimeout: int
    nmemout: int
    nerror: int          # solver produced no sat/unsat verdict (and not a timeout/memout)
    ndisagree: int       # gave a definite verdict that contradicts the expected :status
    nchecked: int        # answered problems whose expected :status is known (disagree denom)
    pct_disagree: float  # 100 * ndisagree / nchecked
    geomean_ms: float
    times: list[float]


def parse_raw(r: bench.RawRecord) -> bench.ParsedRecord:
    ok = not (r["is_timeout"] or r["is_memout"] or r["is_exception"])
    tool = r["tool"]
    if tool in ("fplean", "fplean-nokernel", "fplean-nancanon", "exhaustive-enumeration"):
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
    df = pl.from_dicts(cast(list, rows), infer_schema_length=None)
    if "expected_status" not in df.columns:  # older runs predate the field
        df = df.with_columns(pl.lit(None).alias("expected_status"))
    return df


def compute_tool_stats(df: pl.DataFrame, agg: pl.DataFrame, tool: bench.ToolName) -> ToolStats:
    tool_df = df.filter(pl.col("tool") == tool)
    tool_agg = agg.filter(pl.col("tool") == tool)
    times = sorted(tool_agg["elapsed_ms_geo"].to_list())

    verdict = (
        pl.when(pl.col("is_unsat")).then(pl.lit("unsat"))
          .when(pl.col("is_sat")).then(pl.lit("sat"))
          .otherwise(pl.lit(None))
    )
    answered = pl.col("is_unsat") | pl.col("is_sat")
    known = pl.col("expected_status").is_in(["sat", "unsat"])
    v = tool_df.with_columns(verdict.alias("_verdict"))
    # answered problems whose expected answer is known -- the ones we can grade.
    checkable = v.filter(answered & known)
    nchecked = checkable.height
    ndisagree = checkable.filter(pl.col("_verdict") != pl.col("expected_status")).height
    # "error" = ran but gave no verdict, and it isn't a timeout/memout.
    nerror = tool_df.filter(
        ~(pl.col("is_unsat") | pl.col("is_sat") | pl.col("is_timeout") | pl.col("is_memout"))
    ).height
    return {
        "nunsat": len(times),
        "nsat": tool_df.filter(pl.col("is_sat")).height,
        "ntimeout": tool_df.filter(pl.col("is_timeout")).height,
        "nmemout": tool_df.filter(pl.col("is_memout")).height,
        "nerror": nerror,
        "ndisagree": ndisagree,
        "nchecked": nchecked,
        "pct_disagree": (100.0 * ndisagree / nchecked) if nchecked else 0.0,
        "geomean_ms": bench.geomean(times),
        "times": times,
    }


def _annotate_endpoint_labels(ax, endpoints: list[tuple[float, int, str, str]]) -> None:
    """Label each cactus curve's endpoint with "<solver>: <#solved>".

    `endpoints` is a list of (x, n_solved, text, color). The y-coordinate of a
    curve's end IS its solved count, so tools that solved the same number would
    overprint; nudge the labels apart vertically (keeping their order) with a
    minimum gap, and extend the y-limit if the topmost nudged label would clip.
    """
    if not endpoints:
        return
    ymin, ymax = ax.get_ylim()
    gap = (ymax - ymin) * 0.06  # minimum vertical spacing between labels
    label_y = [float(n) for _, n, _, _ in endpoints]
    prev = float("-inf")
    for i in sorted(range(len(endpoints)), key=lambda i: endpoints[i][1]):
        label_y[i] = max(label_y[i], prev + gap)
        prev = label_y[i]
    top = max(label_y)
    if top > ymax:
        ax.set_ylim(ymin, top + gap * 0.5)  # headroom so the top label isn't clipped
    for (x, _n, text, color), y in zip(endpoints, label_y):
        ax.annotate(text, xy=(x, y), xytext=(4, 0), textcoords="offset points",
                    va="center", ha="left", fontsize=8, color=color)


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
        print(f"  {tool:22s} unsat={s['nunsat']:<5d} sat={s['nsat']:<5d} "
              f"timeout={s['ntimeout']:<4d} memout={s['nmemout']:<3d} "
              f"error={s['nerror']:<5d} "
              f"disagree={s['ndisagree']:<4d}/{s['nchecked']:<5d} "
              f"({s['pct_disagree']:.2f}% unsound) "
              f"geomean={lib.time_str_from_ms(s['geomean_ms'])}")

    # Resolve which suite ran (the manifest is authoritative; fall back to the
    # --suite option) so we can (a) restrict the cactus curve to the suite's
    # tools_to_plot and (b) prefix the LaTeX macros. A suite may run a tool only
    # for the summary/macros and keep it off the curve; tools_to_plot is that
    # plotted subset.
    suite_name = opts.suite
    manifest = indir / "manifest.json"
    if manifest.exists():
        suite_name = json.loads(manifest.read_text()).get("suite", suite_name)
    suite = bench.SUITES.get(suite_name)
    plot_tools = set(suite.tools_to_plot) if suite else present
    pfx = _texprefix(suite_name)

    lib.set_global_matplotlib_defaults()
    fig, ax = plt.subplots(figsize=(CACTUS_WIDTH_IN, CACTUS_HEIGHT_IN))
    endpoints: list[tuple[float, int, str, str]] = []  # (x, #solved, label, color)
    for tool in tools:
        if tool not in plot_tools:
            continue
        times = stats[tool]["times"]
        if not times:
            continue
        cum = np.cumsum(times)
        n_solved = len(cum)
        ax.plot(cum, range(1, n_solved + 1),
                label=bench.tool2label[tool],
                color=bench.tool2color[tool],
                linewidth=2)
        endpoints.append((float(cum[-1]), n_solved,
                          f"{bench.tool2label[tool]}: {n_solved}",
                          bench.tool2color[tool]))
    ax.set_xscale("log")
    ax.set_xlabel("Cumulative time elapsed (ms)")
    ax.set_ylabel("# problems solved (unsat)")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.legend()
    ax.margins(x=0.18)  # right-side headroom for the endpoint labels
    # Label each curve's endpoint with "<solver>: <#solved>" (nudged apart on
    # ties), so the plot is readable without the legend or the cactus.tex macros.
    _annotate_endpoint_labels(ax, endpoints)
    fig.tight_layout()
    lib.save_fig(fig, str(outdir / "cactus.pdf"), str(outdir / "cactus.png"))

    nproblems_total = df["path"].n_unique()

    # Every macro is prefixed with the suite name (pfx, computed above) so several
    # runs' cactus.tex files can be \input together without redefining each
    # other's commands.
    lines = [f"%% Auto-generated LaTeX commands for suite '{suite_name}'", "", "%% totals"]
    lines.append(bench.format_newcommand(f"{pfx}NumProblemsTotal", nproblems_total))

    for tool in tools:
        s = stats[tool]
        cap = _texname(tool)
        per_tool: dict[str, object] = {
            f"{pfx}NumUnsat{cap}":     s["nunsat"],
            f"{pfx}NumSat{cap}":       s["nsat"],
            f"{pfx}NumTimeout{cap}":   s["ntimeout"],
            f"{pfx}NumMemout{cap}":    s["nmemout"],
            f"{pfx}NumErrors{cap}":    s["nerror"],
            f"{pfx}NumChecked{cap}":   s["nchecked"],
            f"{pfx}NumDisagreementsWithExpectedStatus{cap}":     s["ndisagree"],
            f"{pfx}PercentDisagreementsWithExpectedStatus{cap}": f"{s['pct_disagree']:.2f}",
            f"{pfx}GeomeanTime{cap}":  lib.time_str_from_ms(s["geomean_ms"]),
            f"{pfx}GeomeanMs{cap}":    f"{s['geomean_ms']:.1f}",
        }
        lines.append("")
        lines.append(f"%% {tool}")
        lines.extend(bench.format_newcommand(k, v) for k, v in per_tool.items())

    speedups = {
        f"{pfx}Speedup{_texname(a)}Over{_texname(b)}":
            bench.geomean_speedup(stats[b]["geomean_ms"], stats[a]["geomean_ms"])
        for a in tools for b in tools if a != b
    }
    lines.append("")
    lines.append("%% speedups")
    lines.extend(bench.format_newcommand(k, v) for k, v in speedups.items())

    (outdir / "cactus.tex").write_text("\n".join(lines) + "\n")
