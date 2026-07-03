#!/usr/bin/env bash
# Camera-ready run: regenerate the paper's two headline result sets, each with a
# cactus plot and a suite-prefixed cactus.tex (so both can be \input together):
#
#   (a) wintersteiger-supported-family -- 2000-problem sample (seed 42), bitwuzla
#       vs the fp-lean pair on the unsat supported QF_FP set.
#   (b) instcombine-small -- all 50 tiny-width (E5M2/E5M4) InstCombine identities,
#       a 4-way comparison including exhaustive-enumeration.
#
# Runs on the current machine; for the container use ./docker-run-camera-ready.sh.
# Locally, pass host solver paths. NOTE: instcombine-small uses the non-standard
# E5M2/E5M4 minifloats, so bitwuzla must parse those -- the qfbv / container build
# does (the earlier "--fpexp" worry was actually a define-const issue, now fixed):
#   BITWUZLA_PATH=/path/to/bitwuzla LEANWUZLA_DIR=leanwuzla ./run-camera-ready.sh
#
# Override knobs via env, e.g.  NPROBLEMS=500 TIMEOUT_SEC=120 ./run-camera-ready.sh
set -euo pipefail
cd "$(dirname "$0")"

NPROBLEMS="${NPROBLEMS:-2000}"   # sample size for (a); (b) always runs all 50
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

echo "== camera-ready (1/2): wintersteiger-supported-family sample =="
uv run ./cli.py cactus --run --plot \
    --suite wintersteiger-supported-family \
    --guid wintersteiger-supported-family-sample \
    --nproblems "$NPROBLEMS" \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo "== camera-ready (2/2): instcombine-small =="
uv run ./cli.py cactus --run --plot \
    --suite instcombine-small \
    --guid instcombine-small \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo
echo "camera-ready outputs:"
echo "  runresults/wintersteiger-supported-family-sample/outputs/plots/cactus/  (\\WintersteigerSupportedFamily... macros)"
echo "  runresults/instcombine-small/outputs/plots/cactus/                      (\\InstcombineSmall... macros)"
