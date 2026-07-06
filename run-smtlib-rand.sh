#!/usr/bin/env bash
# Run every tool (bitwuzla + the three fp-lean variants) on a stratified sample
# ACROSS ALL QF_FP families, not just wintersteiger. Uses the `smtlib-rand`
# suite (see bench.py): QF_FP is ~99% wintersteiger, so a uniform sample would
# be almost entirely wintersteiger and miss the small real-world families
# (griggio, Vector, schanda, ramalho, the UltimateAutomizer sets). This suite is
# stratified, so NPROBLEMS below is a PER-FAMILY cap: each family contributes
# min(NPROBLEMS, family-size) problems. The sample is deterministic (seed 42).
#
# NOTE: unlike the other run scripts, NPROBLEMS here is per-family, not a total.
# NPROBLEMS=300 -> 712 files total (wintersteiger 300, griggio 214, Vector 91,
# schanda 44, ramalho 36, UA2019 24, Heizmann 2, UA2023 1).
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-smtlib-rand.sh. Locally, pass host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-smtlib-rand.sh
#
# Override knobs via env, e.g.  NPROBLEMS=100 TIMEOUT_SEC=120 ./run-smtlib-rand.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-smtlib-rand}"
NPROBLEMS="${NPROBLEMS:-300}"   # per-family cap (this suite is stratified)
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

exec uv run ./cli.py cactus --run --plot \
    --suite smtlib-rand \
    --guid "$GUID" \
    --nproblems "$NPROBLEMS" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
