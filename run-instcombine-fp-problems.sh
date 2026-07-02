#!/usr/bin/env bash
# Run bitwuzla vs fp-lean on ALL of the InstCombine fp-problems (the
# `instcombine-fp-problems` suite -- ~101 QF_FP optimization-equivalence checks
# extracted from LLVM InstCombine tests) and plot the result.
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-instcombine-fp-problems.sh. Locally, pass host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-instcombine-fp-problems.sh
#
# Override knobs via env, e.g.  TIMEOUT_SEC=120 RUNS=2 ./run-instcombine-fp-problems.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-instcombine-fp-problems}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

exec uv run ./cli.py cactus --run --plot \
    --suite instcombine-fp-problems \
    --guid "$GUID" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
