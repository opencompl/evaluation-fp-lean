#!/usr/bin/env bash
# Run bitwuzla vs fp-lean on a random sample of the unsat, fplean-supported
# QF_FP problems and plot the result. Uses the `supported` suite (the
# wintersteiger ops fplean solves, restricted to unsat instances -- see
# SUPPORTED_OPS in bench.py). The sample is deterministic (seed 42).
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-supported-sample.sh. Locally, pass the host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-supported-sample.sh
#
# Override knobs via env, e.g.  NPROBLEMS=500 TIMEOUT_SEC=120 ./run-supported-sample.sh
set -euo pipefail
cd "$(dirname "$0")"

export SUITE=supported
GUID="${GUID:-supported-sample}"
NPROBLEMS="${NPROBLEMS:-2000}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

exec uv run ./cli.py cactus --run --plot \
    --guid "$GUID" \
    --nproblems "$NPROBLEMS" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
