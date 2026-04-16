#!/usr/bin/env python3
import subprocess
import os
import logging
import pathlib
import platform
import psutil
from dataclasses import dataclass
import sys
import getpass
import socket
import matplotlib
import matplotlib.pyplot as plt
import math
from typing import Callable


@dataclass
class SystemSpecs:
    processor_name: str
    clock_mhz: str
    cores: int
    memory_gb: float

def get_system_specs() -> SystemSpecs:
    name, freq = "Unknown CPU", "Unknown"
    if sys.platform.startswith("linux"):
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    name = line.split(":")[1].strip()[:60]
                elif line.startswith("cpu MHz") and freq == "Unknown":
                    freq = str(round(float(line.split(":")[1].strip()), 2))
        # Prefer max frequency over current (avoids cpufreq scaling artifacts)
        try:
            max_khz = int(pathlib.Path("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq").read_text().strip())
            freq = str(round(max_khz / 1000, 2))
        except (FileNotFoundError, ValueError):
            pass
    elif sys.platform == "darwin":  # macOS
        name = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
        freq = "Unknown (Darwin) MHz"
    else:
        logging.info(f"Unknown machine kind: {sys.platform}")

    cores = os.cpu_count()
    memory_gb = round(psutil.virtual_memory().total / (1024**3), 2)

    return SystemSpecs(
        processor_name=str(name),
        clock_mhz=freq,
        cores=cores,
        memory_gb=memory_gb
    )


def root_dir() -> pathlib.Path:
    return  pathlib.Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode('utf-8').strip())

def git_hash() -> str:
    return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()

def machine_uname() -> platform.uname_result:
    return platform.uname()

def machine_hostname() -> str:
    return socket.gethostname()

def machine_username() -> str:
    return getpass.getuser()

STATUS_FAIL = "❌"
STATUS_GREEN_CHECK = "✅"
STATUS_SUCCESS = "🎉"
STATUS_PROCESSING = "⌛️"

def setup_logging(log_file_path : str):
    # Set up the logging configuration
    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file_path, mode='a'), logging.StreamHandler()])



# helper for str_from_float.
# format float in scientific with at most *digits* digits.
#
# precision of the mantissa will be reduced as necessary,
# as much as possible to get it within *digits*, but this
# can't be guaranteed for very large numbers.
def get_scientific(x: float, digits: int):
    # get scientific without leading zeros or + in exp
    def get(x: float, prec: int) -> str:
      result = f'{x:.{prec}e}'
      result = result.replace('e+', 'e')
      while 'e0' in result:
        result = result.replace('e0', 'e')
      while 'e-0' in result:
        result = result.replace('e-0', 'e-')
      return result

    result = get(x, digits)
    len_after_e = len(result.split('e')[1])
    prec = max(0, digits - len_after_e - 2)
    return get(x, prec)

# format float with at most *digits* digits.
# if the number is too small or too big,
# it will be formatted in scientific notation,
# optionally a suffix can be passed for the unit.
#
# note: this displays different numbers with different
# precision depending on their length, as much as can fit.
def str_from_float(x: float, digits: int = 3, suffix: str = '') -> str:
  result = f'{x:.{digits}f}'
  before_decimal = result.split('.')[0]
  if len(before_decimal) == digits:
    return before_decimal
  if len(before_decimal) > digits:
    # we can't even fit the integral part
    return get_scientific(x, digits)

  result = result[:digits + 1] # plus 1 for the decimal point
  if float(result) == 0:
    # we can't even get one significant figure
    return get_scientific(x, digits)

  return result[:digits + 1]

# Attach a text label above each bar in *rects*, displaying its height
def autolabel(ax, rects, label_from_height: Callable[[float], str] =str_from_float, xoffset=0, yoffset=1, **kwargs):
    # kwargs is directly passed to ax.annotate and overrides defaults below
    assert 'xytext' not in kwargs, "use xoffset and yoffset instead of xytext"
    default_kwargs = dict(
        xytext=(xoffset, yoffset),
        fontsize="smaller",
        rotation=0,
        ha='center',
        va='bottom',
        textcoords='offset points')

    for rect in rects:
        height = rect.get_height()
        ax.annotate(
            label_from_height(height),
            xy=(rect.get_x() + rect.get_width() / 2, height),
            **(default_kwargs | kwargs),
        )

# utility to logging.info times as 1h4m, 1d15h, 143.2ms, 10.3s etc.
def time_str_from_ms(ms):
  ms = int(ms)
  def maybe_val_with_unit(val, unit):
    return f'{val}{unit}' if val != 0 else ''

  if ms < 1000:
    return f'{ms:.3g}ms'

  s = ms / 1000
  ms = 0
  if s < 60:
    return f'{s:.3g}s'

  m = int(s // 60)
  s -= 60*m
  if m < 60:
    return f'{m}m{maybe_val_with_unit(math.floor(s), "s")}'

  h = int(m // 60)
  m -= 60*h
  if h < 24:
    return f'{h}h{maybe_val_with_unit(m, "m")}'

  d = int(h // 24)
  h -= 24*d
  return f'{d}d{maybe_val_with_unit(h, "h")}'

def autolabel_ms(ax, rects, **kwargs):
  autolabel(ax, rects, label_from_height=time_str_from_ms, **kwargs)

def set_global_matplotlib_defaults():
    ## Use TrueType fonts instead of Type 3 fonts
    #
    # Type 3 fonts embed bitmaps and are not allowed in camera-ready submissions
    # for many conferences. TrueType fonts look better and are accepted.
    # This follows: https://www.conference-publishing.com/Help.php
    matplotlib.rcParams['pdf.fonttype'] = 42
    matplotlib.rcParams['ps.fonttype'] = 42

    ## Enable tight_layout by default
    #
    # This ensures the plot has always sufficient space for legends, ...
    # Without this sometimes parts of the figure would be cut off.
    matplotlib.rcParams['figure.autolayout'] = True

    ## Legend defaults
    matplotlib.rcParams['legend.frameon'] = False

    # Hide the right and top spines
    #
    # This reduces the number of lines in the plot. Lines typically catch
    # a readers attention and distract the reader from the actual content.
    # By removing unnecessary spines, we help the reader to focus on
    # the figures in the graph.
    matplotlib.rcParams['axes.spines.right'] = False
    matplotlib.rcParams['axes.spines.top'] = False
    matplotlib.rcParams['figure.figsize'] = 5, 2

def save_fig(figure, pdf_file_path : str, jpeg_file_path : str =None):
    if jpeg_file_path is None:
       jpeg_file_path = os.path.splitext(pdf_file_path)[0] + ".jpeg"

    # Do not emit a creation date, creator name, or producer. This will make the
    # content of the pdfs we generate more deterministic.
    metadata = {'CreationDate': None, 'Creator': None, 'Producer': None}

    # Save as PDF
    figure.savefig(pdf_file_path, metadata=metadata)

    # Save as JPEG
    figure.savefig(jpeg_file_path, format='jpeg')

    # Close figure to avoid warning about too many open figures.
    plt.close(figure)

    logging.info(f'written to PDF ({pdf_file_path}) and JPEG ({jpeg_file_path})')


def fmt_newcommand(key : str, val : str) -> str:
    """
    Format a LaTeX \\newcommand, with key and val.
    """
    return f"\\newcommand{{\\{key}}}{{{val}}}\n"

