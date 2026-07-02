#!/usr/bin/env bash
# Run bitwuzla vs fp-lean on the FULL wintersteiger QF_FP family (every
# operator, sat and unsat -- the `wintersteiger-all-family` suite) and plot the result.
#
# NOTE: ~40k problems. bitwuzla handles them all quickly, but fplean errors on
# unsupported ops (fp.min/fp.max/fp.sqrt/fp.roundToIntegral), times out on
# fp.rem, and cannot model sat instances -- so a full fplean pass is very slow.
# Pair with NPROBLEMS to sample, e.g.  NPROBLEMS=2000 ./run-wintersteiger-all-family.sh
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-wintersteiger-all-family.sh. Locally, pass host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-wintersteiger-all-family.sh
#
# Override knobs via env, e.g.  NPROBLEMS=2000 TIMEOUT_SEC=60 ./run-wintersteiger-all-family.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-wintersteiger-all-family}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

# --nproblems is only passed when NPROBLEMS is set (otherwise the whole suite).
NPROBLEMS_FLAG=()
if [ -n "${NPROBLEMS:-}" ]; then
    NPROBLEMS_FLAG=(--nproblems "$NPROBLEMS")
fi

exec uv run ./cli.py cactus --run --plot \
    --suite wintersteiger-all-family \
    --guid "$GUID" \
    "${NPROBLEMS_FLAG[@]}" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
