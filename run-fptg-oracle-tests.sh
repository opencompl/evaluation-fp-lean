#!/usr/bin/env bash
# FPTG oracle soundness test: run fp-lean over an fptg suite (default the small
# float8 set) and fail if any verdict disagrees with the MPFR/PyMPF oracle
# (set-info :status). Errors on ops fp-lean does not implement yet
# (fp.max/min/sqrt/roundToIntegral) are tolerated (xfail) and reported per op.
#
# This is the same gate the CI runs (.github/workflows/fptg-oracle-tests.yml).
# Runs on the current machine; for the container use ./docker-run-fptg-oracle-tests.sh.
#
# Override knobs via env, e.g.
#   SUITE=fptg-float16 ./run-fptg-oracle-tests.sh
#   TOOLS=fplean NPROC=8 ./run-fptg-oracle-tests.sh   # gate only the sound path
set -euo pipefail
cd "$(dirname "$0")"

SUITE="${SUITE:-fptg-float8}"
TOOLS="${TOOLS:-fplean,fplean-nokernel}"
NPROBLEMS="${NPROBLEMS:-}"        # empty = the whole suite
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
NPROC="${NPROC:-6}"
GUID="${GUID:-fptg-oracle-tests}"

npflag=()
[ -n "$NPROBLEMS" ] && npflag=(--nproblems "$NPROBLEMS")

exec uv run ./cli.py fptg-oracle-tests \
    --suite "$SUITE" --tools "$TOOLS" \
    "${npflag[@]}" --timeout-sec "$TIMEOUT_SEC" --nproc "$NPROC" --guid "$GUID"
