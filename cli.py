#! /usr/bin/env -S uv run
import argparse
from multiprocessing import Pool
import pathlib
from typing import Optional
import json
import sys
import time
import polars as pl
import matplotlib.pyplot as plt
import functools
import math
import lib
import numpy as np
import re
import matplotlib.colors as mcolors
from typing import TypedDict
from runwithlimits import run_with_limits
from dataclasses import dataclass

FIGSIZE_A4_WIDTH = 8.27
FIGSIZE_A4_HEIGHT = 11.69

BLASE_PATH = pathlib.Path("lean-mlir/Blase/.lake/build/bin/blasewuzla")
CVC5_PATH = pathlib.Path("/pbv-2025-artifact/pbvsolver")

class Colors:
    material_red = "#F48FB1"
    material_blue = "#90CAF9"
    material_green = "#4CAF50"
    material_green_darker = "#2E7D32"
    material_yellow = "#FFEB3B"
    material_orange = "#FFAB40"
    material_purple = "#B39DDB"
    material_teal = "#80CBC4"
    material_brown = "#795548" 
    material_gray = "#B0BEC5"
    material_blue_darker = "#01579B"

tool2color = {
    "mw-bmc-naive": Colors.material_brown,
    "mw-bmc-mono": Colors.material_red,
    "cvc5-pbv": Colors.material_orange,
    "mw-pbv-kind": Colors.material_blue_darker,
    "mw-pbv-ric3": Colors.material_green,
    "mw-pbv-abc": Colors.material_green_darker,
    "mw-pbv-dry-run": Colors.material_brown,
}

tool2label = {
    "mw-bmc-naive": "BMC-Naive",
    "mw-bmc-mono": "BMC-Ours",
    "cvc5-pbv": "cvc5-berger",
    "mw-pbv-kind": "Unbounded-Ours-k-ind",
    "mw-pbv-ric3": "Unbounded-Ours-ric3",
    "mw-pbv-abc": "unbounded-abc",
    "mw-pbv-dry-run": "mw-pbv-dry-run",
}

tool2marker = {
    "mw-bmc-naive": ".",
    "mw-bmc-mono": "s",
    "cvc5-pbv": "v",
    "mw-pbv-kind": "s",
    "mw-pbv-ric3": "x",
    "mw-pbv-abc": "+",
    "mw-pbv-dry-run": "mw-pbv-dry-run",
}

tool2lineopts = {
    "mw-bmc-naive":   {"linestyle": "dashed", "linewidth": 3},
    "mw-bmc-mono":    {"linestyle": "dashed", "linewidth": 3},
    "cvc5-pbv":       {"linestyle": "solid",  "linewidth": 2},
    "mw-pbv-kind":    {"linestyle": "solid",  "linewidth": 2},
    "mw-pbv-ric3":    {"linestyle": "solid",  "linewidth": 2},
    "mw-pbv-abc":     {"linestyle": "solid",  "linewidth": 2},
    "mw-pbv-dry-run": {"linestyle": "solid",  "linewidth": 2},
}


def tool_command(config) -> list[str]:
    blase2backend = {
            "mw-pbv-dry-run": "dryrun",
            "mw-pbv-kind": "k-induction",
            "mw-pbv-ric3": "rIC3",
            "mw-pbv-abc": "abc",
            "mw-bmc-naive": "naivebmc",
            "mw-bmc-mono": "monobmc",
    }
    match config["tool"]:
        case "mw-pbv-kind" | "mw-pbv-ric3" | "mw-bmc-naive" | "mw-bmc-mono" | "mw-pbv-abc" | "mw-pbv-dry-run":
            lake_env = ["lake", "env"]
            blasewuzla_call = [str(BLASE_PATH.absolute()), \
                    "--backend", blase2backend[config["tool"]], \
                    "--elimIte", \
                    "--preconditionSub", \
                    "--elimSub", \
                    str(config["path"].absolute())]
            bound = []
            if "bmc" in config["tool"]:
                bound = ["--bound", str(config["bound"])]
            return lake_env + blasewuzla_call + bound
        case "cvc5-pbv": 
            return [str(CVC5_PATH.absolute()), "--pbv", '--cvc5:"nl-ext-tplanes full-saturate-quant"', \
                    str(config["path"].absolute())]
        case _: 
            tool = config["tool"]
            raise RuntimeError(f"unknown tool '{tool}' at tool_command")

def tool_cwd(cli_options, config) -> Optional[str]:
    """Return the CWD that the tool needs to be run in."""
    if "mw" in config["tool"]:
        return str(BLASE_PATH.parent.absolute())
    return None

def tool_is_success(tool_name, stdout, stderr, returncode) -> Optional[str]:
    """Return whether the tool execution was a success based on parameters"""
    if "mw" in tool_name:
        return returncode == 20
    elif "cvc5" in tool_name:
        return "unsat" in stdout 
    else:
        raise RuntimeError("unknown tool kind")

def tool_is_unsound(tool_name, stdout, stderr, returncode) -> Optional[str]:
    """Return whether the tool execution was unsound (i.e. it returned SAT)"""
    if "mw" in tool_name:
        return returncode == 10
    elif "cvc5" in tool_name:
        return "sat" in stdout  and "unsat" not in stdout
    else:
        raise RuntimeError("unknown tool kind")

def tool_time_elapsed_ms(tool_name:str, time_start_ms:int, time_end_ms:int, stdout:str, stderr:str, returncode:int) -> int:
    if "mw" in tool_name and returncode == 20:
        matcher = re.search(r"Time elapsed:\s*(\d+)\s*ms", stdout)
        return int(matcher.group(1)) if matcher else 0
    else:
        return time_end_ms - time_start_ms

def config_to_str(config) -> str:
    """config to string"""
    return f"{config['run']}-{config['tool']}-{config['path']}"

def current_time_to_str() -> str:
   return time.strftime('%l:%M%p %Z on %b %d, %Y')


def config_stage1_path(cli_options, config) -> pathlib.Path:
    """Return the path to the stage1 file for a given config."""
    return config["path"].with_suffix(".run.jsonl")

# output path is hardcoded based on the config.
def run_benchmark(cli_options, config):
    print(f"[{current_time_to_str():30}]{config_to_str(config):>80}")

    cmd = tool_command(cli_options, config)
    start_time = time.time()
    result = run_with_limits(
        cmd,
        timeout_sec=cli_options.timeout_sec,
        memout_mb=cli_options.memout_mb,
        cwd=tool_cwd(cli_options, config)
    )
    end_time = time.time()

    config["returncode"] = result.returncode
    config["elapsedms"] = tool_time_elapsed_ms(tool_name=config["tool"], \
                            time_start_ms=start_time * 1000, \
                            time_end_ms=end_time*1000, \
                            stdout=result.stdout, \
                            stderr=result.stderr, \
                            returncode=result.returncode)
    config["cmd"] = str(cmd)
    config["is_memout"] = result.is_memout
    config["is_timeout"] = result.is_timeout
    config["is_exception"] = result.is_exception
    config["stdout"] = result.stdout
    config["stderr"] = result.stderr
    config["cwd"] = str(tool_cwd(cli_options, config))
    config["exception"] = str(result.exception)

    with open(config_stage1_path(cli_options, config), "a") as log_file:
        json.dump(json_encode_value(config), log_file, indent=2)

def progress_bar(i : int, total : int, start_time : float) -> str:
    frac = i / total
    width = 80
    filled = int(width * frac)
    bar = "█" * filled + "-" * (width - filled)
    elapsed = time.time() - start_time
    avg_time = elapsed / i if elapsed > 0 else 0
    eta = (total - i) * avg_time
    return (
        f"\r[{bar}] {i}/{total} "
        f"{frac:6.2%} "
        f"{avg_time:6.1f} s/it "
        f"ETA {eta:6.1f}s"
    )

def json_encode_value(v):
    """encode a value as a json-encodable type, so a list[] / int / float"""
    if isinstance(v, int) or isinstance(v, float) or isinstance(v, str):
        return v
    elif isinstance(v, pathlib.Path):
        return str(v)
    elif isinstance(v, list):
        return [json_encode_value(x) for x in v]
    elif isinstance(v, dict):
        return {x:json_encode_value(y) for (x, y) in v.items()}
    else:
        raise RuntimeError(f"unknown value to encode to JSON(type: {type(v)}): {v}")


def run_benchmark_ouput_to_string(output):
    if output["is_timeout"]:
        return "(timeout)⏳❌"
    if output["is_memout"]:
        return "(memout)🧠❌"
    elif output["is_exception"]:
        return "(exception)💥❌"
    elif output["is_success"]:
        return "(success)✅✅"
    elif output["is_unsound"]:
        return "(UNSOUND)💀❌"
    else:
        return "(unknown)❌"

def run_configs(cli_options, configs):
    total = len(configs)
    with Pool(processes=cli_options.nproc) as pool:
        for output in pool.imap_unordered(functools.partial(run_benchmark, cli_options), configs, chunksize=3):
            i += 1
            print(f"[{current_time_to_str():30}]{run_benchmark_ouput_to_string(output):>3}({output['elapsedms']/1000.0:>5.2f}sec){config_to_str(output):>60}")
            print(progress_bar(i, total, start_time))


_DIGIT_NAMES = {
    '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
    '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine',
}

def latex_sanitize(s: str) -> str:
    """Turn e.g. 'mw-bmc-naive' into 'MwBmcNaive', and 'foo01bar' into 'FooZeroOneBar'."""
    # Replace each digit with its English name surrounded by dashes to create word boundaries.
    s = re.sub(r'\d', lambda m: f'-{_DIGIT_NAMES[m.group()]}-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    s = "".join(part.capitalize() for part in s.replace("_", "-").split("-"))
    return s

def geomean_speedup(a : float, b : float):
    """
    Calculate geomean speedup, taking into account the corner cases of numerator and denominator being zero
    """
    a = float(a)
    b = float(b)
    assert a >= 0 
    assert b >= 0
    if a == 0:
        return 0
    elif b == 0:
        return float("inf")
    else:
        return a / b

def geomean(xs: list[float]) -> float:
    """Return geomean, returning zero if there are no valid data points"""
    logs = [math.log(x) for x in xs if x > 0]
    return math.exp(sum(logs) / len(logs)) if logs else 0.0


def format_newcommand( command_name : str, command_val: str | float, precision: int = 1, preamble: str = "") -> str:
    if isinstance(value, float):
        value = f"{value:.{precision}f}"
    return f"\\newcommand{{\\{name}}}{{{value}}} %% Auto-generated latex command\n"

def write_config_tex(cli_options) -> str:
    """Write run configuration (limits, parallelism, etc.) to config.tex."""
    commands = {
        "ConfigTimeoutSec":       cli_options.timeout_sec,
        "ConfigMemoutMb":         cli_options.memout_mb,
        "ConfigNproc":            cli_options.nproc,
        "ConfigRuns":             cli_options.runs,
    }
    if cli_options.nproblems_per_tool is not None:
        commands["ConfigNproblemsPerTool"] = cli_options.nproblems_per_tool
    write_newcommands(folder / "config.tex", commands)

def write_machine_data_tex() -> str:
    system_specs = lib.get_system_specs()
    write_newcommands(folder / "triple.tex", {
            "MachineUserName": lib.machine_username(),
            "MachineHostname": lib.machine_hostname(),
            "SystemSpecsProcessorName": system_specs.processor_name,
            "SystemSpecsClockMhz": system_specs.clock_mhz,
            "SystemSpecsCores": system_specs.cores,
            "SystemSpecsMemoryGb": system_specs.memory_gb,
        })

def cmd_bmc_hero(cli_options):
    """BMC hero figure: naive vs mono on ours-zextsext (small bound range)."""
    cli_options.jsonlpath = pathlib.Path("./output/bmc-hero/data.jsonl")
    if cli_options.run:
        run_configs(cli_options, bmc_hero_configs(cli_options))

    if cli_options.plot:
        plot_bmc_hero_pdf_png(cli_options.jsonlpath)
        write_machine_data_tex(cli_options.jsonlpath.parent)
        write_config_tex(cli_options.jsonlpath.parent, cli_options)



def add_parser_common_options(p, command_name):
    p.add_argument("--run", default=False, action='store_true')
    p.add_argument("--plot", default=False, action='store_true')
    p.add_argument("--runs", type=int, default=2)
    p.add_argument("--timeout-sec", type=int, default=600)
    p.add_argument("--nproc", type=int, default=4)
    p.add_argument("--nproblems-per-tool", type=int, default=None) # optional argument, number of problems to run.
    p.add_argument("--memout-mb", type=int, default=16000)

def main():
    parser = argparse.ArgumentParser(description="OOPSLA 2026 evaluation driver")
    sub = parser.add_subparsers(dest="command")

    dispatch = {
        "small": functools.partial(cmd_run_smtlib,
                        tools=bmc_tools + pbv_tools + dry_run_tools,
                        pbv_families=["sext-zext-instcombine"],
                        name='sext-zext-instcombine',
                        latex_prefix='SextZextInstcombine',
                        title='Cactus plot of all tools on sext-zext-instcombine rewrites',
                        xticks_delta=50),
        "everybench": cmd_everybench,
    }

    for name in dispatch.keys():
        p = sub.add_parser(name, help=f"{name} figure")
        add_parser_common_options(p, name)

    add_parser_run_tool(sub)
    cli_options = parser.parse_args()

    if cli_options.command is None:
        parser.print_help()
        sys.exit(1)

    if cli_options.command == "run-tool":
        cmd_run_tool(cli_options)
        sys.exit(0)

    if not cli_options.plot and not cli_options.run:
        print("expected either '--plot' or '--run', found neither, so quitting since no action was given.")
        parser.print_help()
        sys.exit(1)
    dispatch[cli_options.command](cli_options=cli_options)

if __name__ == "__main__":
    main()

