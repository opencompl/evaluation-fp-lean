#!/usr/bin/env bash
# Run bitwuzla vs fp-lean on the FULL unsat, fplean-supported QF_FP set and plot
# the result. Uses the `supported` suite (the wintersteiger ops fplean solves,
# restricted to unsat instances -- see SUPPORTED_OPS in bench.py). ~11.5k
# problems; fplean dominates the wall time (~seconds each).
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-supported-all.sh. Locally, pass the host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-supported-all.sh
#
# Override knobs via env, e.g.  RUNS=2 TIMEOUT_SEC=120 ./run-supported-all.sh
set -euo pipefail
cd "$(dirname "$0")"

export SUITE=supported
GUID="${GUID:-supported-all}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

exec uv run ./cli.py cactus --run --plot \
    --guid "$GUID" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
