#!/usr/bin/env bash
# Run bitwuzla vs fp-lean on the FULL wintersteiger-supported-family set (unsat
# instances of the ops fplean solves -- see the suite in bench.py) and plot the
# result. ~11.5k problems; fplean dominates the wall time (~seconds each).
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-wintersteiger-supported-family.sh. Locally, pass host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-wintersteiger-supported-family.sh
#
# Override knobs via env, e.g.  RUNS=2 TIMEOUT_SEC=120 ./run-wintersteiger-supported-family.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-wintersteiger-supported-family}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

exec uv run ./cli.py cactus --run --plot \
    --suite wintersteiger-supported-family \
    --guid "$GUID" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
