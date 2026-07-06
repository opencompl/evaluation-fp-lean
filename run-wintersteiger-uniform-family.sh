#!/usr/bin/env bash
# Run bitwuzla vs fp-lean on the wintersteiger QF_FP family sampled UNIFORMLY
# across every operator (the `wintersteiger-uniform-family` suite: all 14 ops,
# unsat only, stratified). Because the suite is stratified, NPROBLEMS is a
# *per-family* cap, not a total: each operator contributes min(NPROBLEMS,
# family-size) problems, so every operator is equally weighted regardless of its
# size. Deterministic (seed 42). Plots the result.
#
# NOTE: fplean errors on unsupported ops (fp.min/fp.max/fp.sqrt/
# fp.roundToIntegral), times out on fp.rem, and does not finish fp.fma -- those
# show up as errors/timeouts, which is informative for per-operator coverage.
# With NPROBLEMS unset the whole unsat set runs (~20k), which is slow for fplean;
# pass NPROBLEMS to sample, e.g.  NPROBLEMS=200 ./run-wintersteiger-uniform-family.sh
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-wintersteiger-uniform-family.sh. Locally, pass host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-wintersteiger-uniform-family.sh
#
# Override knobs via env, e.g.  NPROBLEMS=200 TIMEOUT_SEC=60 ./run-wintersteiger-uniform-family.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-wintersteiger-uniform-family}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

# --nproblems (here a per-family cap) is only passed when NPROBLEMS is set;
# otherwise the whole unsat set runs.
NPROBLEMS_FLAG=()
if [ -n "${NPROBLEMS:-}" ]; then
    NPROBLEMS_FLAG=(--nproblems "$NPROBLEMS")
fi

exec uv run ./cli.py cactus --run --plot \
    --suite wintersteiger-uniform-family \
    --guid "$GUID" \
    "${NPROBLEMS_FLAG[@]}" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
