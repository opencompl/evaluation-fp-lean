#!/usr/bin/env -S uv run
import argparse
import sys
import run
import plot


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="FP-lean evaluation driver.")
    sub = parser.add_subparsers(dest="command", required=True)
    run.add_parser(sub)
    plot.add_parser(sub)
    opts: argparse.Namespace = parser.parse_args()

    if opts.command == "run":
        run.cmd(opts)
    elif opts.command == "plot":
        plot.cmd(opts)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
