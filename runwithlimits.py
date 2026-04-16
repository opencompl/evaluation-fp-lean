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


def monitor_memory(pid: int, memout_mb: int, flag: MonitorFlags):
    """
    Monitor memory of process 'pid', and ensure that it
    does not exceed 'memout_mb' (in megabytes) by polling.
    'flag' is an inout class
    the monitor thread and the main thread.
    - flag.done: whether the process has finished running
    - flag.memout: whether the process has exceeded memory limits.
    """
    try:
        proc = psutil.Process(pid)
        while not flag.done:
            mem = proc.memory_info().rss
            for child in proc.children(recursive=True):
                try:
                    mem += child.memory_info().rss
                except psutil.NoSuchProcess:
                    continue
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
        monitor_thread = threading.Thread(
            target=monitor_memory, args=(proc.pid, memout_mb, flag)
        )
        monitor_thread.start()

        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec)
            flag.done = True
            monitor_thread.join()
            output = RunWithLimitsOutput(stdout, stderr, proc.returncode)
            if flag.memout:
                output.set_memout()
            return output
        except subprocess.TimeoutExpired:
            flag.done  = True
            flag.timeout = True
            kill_process_tree(proc.pid)
            stdout, stderr = proc.communicate()
            monitor_thread.join()
            output = RunWithLimitsOutput(stdout, stderr, proc.returncode)
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

