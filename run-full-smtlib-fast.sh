#!/usr/bin/env bash
# Fast soundness sweep over the ENTIRE QF_FP set (all 8 families, ~40,406
# problems), all four tools, with a short 10s timeout so the whole thing
# finishes in a few hours and can be looped. The point is not performance
# fidelity (use the camera-ready suites for that) -- it is to catch soundness
# regressions: every tool's verdict is graded against each problem's declared
# (set-info :status ...), and plot.py reports NumDisagreementsWithExpectedStatus
# (a definite verdict that contradicts the oracle = unsound).
#
# Mechanism: the `smtlib-rand` suite is stratified with a PER-FAMILY cap, so a
# cap >= the largest family (wintersteiger, 39,994) pulls in every problem of
# every family -- i.e. all of QF_FP, not a sample. status=None keeps sat/unsat/
# unknown, so it grades against whatever each benchmark declares.
#
# Runs directly on the current machine (uses the locally-built leanwuzla, so it
# picks up local fixes without an image rebuild). For the container use
# ./run-full-smtlib-fast-docker.sh (rebuild the image first to include fixes).
#   BITWUZLA_PATH=/usr/local/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-full-smtlib-fast.sh
#
# Override knobs via env, e.g.  TIMEOUT_SEC=5 NPROC=28 ./run-full-smtlib-fast.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-full-smtlib-fast}"
# Per-family cap; >= the largest family (39,994) means "take everything".
NPROBLEMS="${NPROBLEMS:-40000}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-10}"   # short on purpose so the full sweep is loopable
MEMOUT_MB="${MEMOUT_MB:-8000}"
# Soundness sweep, not a timing measurement -> use most of the box.
NPROC="${NPROC:-24}"

exec uv run ./cli.py cactus --run --plot \
    --suite smtlib-rand \
    --guid "$GUID" \
    --nproblems "$NPROBLEMS" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
