#!/usr/bin/env bash
# Run all four tools on the InstCombine-small suite (the `instcombine-small`
# suite -- the 50 tiny-width E5M2/E5M4 reparametrizations of the constant-free
# InstCombine identities) and plot the result. These have 1-3 free FP variables,
# so exhaustive-enumeration genuinely enumerates (feasible for <=2 vars).
#
# NOTE: instcombine-small uses the non-standard E5M2/E5M4 minifloats, so bitwuzla
# must parse those -- the qfbv / container build does.
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-instcombine-small.sh. Locally, pass host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-instcombine-small.sh
#
# Override knobs via env, e.g.  TIMEOUT_SEC=120 RUNS=2 ./run-instcombine-small.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-instcombine-small}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

exec uv run ./cli.py cactus --run --plot \
    --suite instcombine-small \
    --guid "$GUID" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
