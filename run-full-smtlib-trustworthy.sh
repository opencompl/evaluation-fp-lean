#!/usr/bin/env bash
# Fidelity sweep over the ENTIRE QF_FP set (all 8 families, ~40,406 problems),
# all four tools, with TRUSTWORTHY per-problem timings: NPROC=14 (<= the 16
# physical cores of the Ryzen 9 9950X, with headroom, and below the SMT-sibling
# threshold), so recorded solve times are uncontended. This is the run whose
# cactus/geomean numbers you can report -- the companion run-full-smtlib-fast.sh
# (NPROC=24) is for quick soundness looping where per-problem times don't matter.
#
# TIMEOUT_SEC=10: on the smtlib-rand data the kernel-checked fplean solved ZERO
# problems in the 10-60s window (all solves are <10s), so a 10s cap costs it no
# solving power while cutting the timeout tail 6x; only bitwuzla/fplean-nokernel
# lose a few percent of solves. Bump TIMEOUT_SEC=60 if you want the full tail.
#
# Same coverage mechanism as run-full-smtlib-fast.sh: the stratified smtlib-rand
# suite with a per-family cap >= the largest family (39,994) pulls in every
# problem of every family = all of QF_FP.
#
# Runs directly on the current machine (uses the locally-built leanwuzla, so it
# picks up local fixes without an image rebuild). Locally, pass host solver
# paths:
#   BITWUZLA_PATH=/usr/local/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-full-smtlib-trustworthy.sh
#
# Override knobs via env, e.g.  NPROC=12 TIMEOUT_SEC=30 ./run-full-smtlib-trustworthy.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-full-smtlib-trustworthy}"
# Per-family cap; >= the largest family (39,994) means "take everything".
NPROBLEMS="${NPROBLEMS:-40000}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-10}"   # 10s keeps ~all fplean solves (see header)
MEMOUT_MB="${MEMOUT_MB:-8000}"
# 14 <= 16 physical cores, no SMT-sibling contention -> trustworthy timings.
NPROC="${NPROC:-14}"

exec uv run ./cli.py cactus --run --plot \
    --suite smtlib-rand \
    --guid "$GUID" \
    --nproblems "$NPROBLEMS" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
