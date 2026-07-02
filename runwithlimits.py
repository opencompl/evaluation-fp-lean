#!/usr/bin/env -S uv run
import os
import subprocess
import psutil
import time
import threading
import argparse
import sys
from typing import List, Optional

def kill_process_tree(pid: int):
    """
    Kill the entire process tree owned by 'pid'
    """
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass

class MonitorFlags:
    done : bool = False
    memout : bool = False
    timeout : bool = False


def monitor_limits(pid: int, memout_mb: int, deadline: float, flag: MonitorFlags):
    """
    Poll the process tree rooted at 'pid' and kill it if it exceeds either the
    wall-clock 'deadline' (a time.monotonic() value) or 'memout_mb' megabytes.

    This thread is the PRIMARY wall-timeout enforcer. Relying on
    subprocess.communicate(timeout=...) alone is not enough: under heavy CPU
    oversubscription the parent can be starved so that the child finishes (and
    communicate returns "success") before communicate ever gets scheduled to
    check its own deadline, so the timeout silently leaks. An independent thread
    that actively kills at the deadline whenever it is scheduled closes that gap.

    'flag' is shared inout state between this thread and the main thread:
    - flag.done: set by the main thread once the process has finished.
    - flag.memout / flag.timeout: set here when the corresponding limit is hit.
    """
    try:
        proc = psutil.Process(pid)
        while not flag.done:
            if time.monotonic() >= deadline:
                flag.timeout = True
                kill_process_tree(pid)
                return
            try:
                mem = proc.memory_info().rss
                for child in proc.children(recursive=True):
                    try:
                        mem += child.memory_info().rss
                    except psutil.NoSuchProcess:
                        continue
            except psutil.NoSuchProcess:
                return
            if mem > memout_mb * 1024 * 1024:
                flag.memout = True
                kill_process_tree(pid)
                return
            time.sleep(0.1)
    except psutil.NoSuchProcess:
        pass


class RunWithLimitsOutput:
    stdout : str 
    stderr : str
    returncode : int 
    is_memout : bool = False
    is_timeout : bool = False
    is_exception : bool = False
    exception : Exception = None

    def __init__(self, stdout, stderr, returncode):
        self.stdout = stdout 
        self.stderr = stderr 
        self.returncode = returncode

    def set_memout(self):
        self.is_memout = True

    def set_timeout(self):
        self.is_timeout = True

    def set_exception(self, e : Exception):
        self.is_exception = True 
        self.exception = e


def run_with_limits(cmd: List[str], timeout_sec: int, memout_mb: int, cwd : Optional[str] = None) -> RunWithLimitsOutput:
    """
    Run the process 'cmd' with timeout 'timeout_sec' in seconds,
    and memout 'memout_mb' in megabyte.
    Note: this is a blocking, synchronous function.

    Returns a 'RunWithLimitsOutput'
    """
    # The monitor thread enforces the wall deadline by actively killing the
    # process tree. communicate() keeps its own timeout only as a last-resort
    # backstop (in case the monitor thread itself dies), with a small grace
    # period so the monitor is the one that normally fires.
    BACKSTOP_GRACE_SEC = 5
    try:
        # logging.info(f"running command w/limits: '{" ".join(cmd)}' @ cwd: '{cwd}' with limits timeout: '{timeout}' memout: '{memout_mb}'")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
            cwd=cwd
        )
        flag = MonitorFlags()
        deadline = time.monotonic() + timeout_sec
        monitor_thread = threading.Thread(
            target=monitor_limits, args=(proc.pid, memout_mb, deadline, flag)
        )
        monitor_thread.start()

        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec + BACKSTOP_GRACE_SEC)
        except subprocess.TimeoutExpired:
            # Backstop path: the monitor did not kill in time. Force it.
            flag.timeout = True
            kill_process_tree(proc.pid)
            stdout, stderr = proc.communicate()
        flag.done = True
        monitor_thread.join()

        output = RunWithLimitsOutput(stdout, stderr, proc.returncode)
        if flag.memout:
            output.set_memout()
        if flag.timeout:
            output.set_timeout()
        return output
    except Exception as e:
        output = RunWithLimitsOutput("", "", -1)
        output.set_exception(e)
        return output

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
        "Run a command with timeout and memory limits.\n\n"
        ))
    parser.add_argument("--timeout-sec", type=int, required=True, help="Timeout in seconds")
    parser.add_argument("--memout-mb", type=int, required=True, help="Memory limit in MB")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run with arguments")
    return parser.parse_args()

def main():
    args = parse_args()

    if args.cmd and args.cmd[0] == "--":
        cmd_args = args.cmd[1:]
    else:
        cmd_args = args.cmd

    output = run_with_limits(cmd_args, args.timeout_sec, args.memout_mb)
    print(output.stdout, file=sys.stdout, end="")
    print(output.stderr, file=sys.stderr, end="")
    if output.is_timeout:
        print("error: timeout")
    elif output.is_memout:
        print("error: memout")
    elif output.is_exception:
        print(f"error: exception. {output.exception}")
    else:
        print("success")

if __name__ == "__main__":
    main()

