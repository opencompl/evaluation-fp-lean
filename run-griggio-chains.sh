#!/usr/bin/env bash
# Run bitwuzla vs fplean (canon off, axiom-free) vs fplean-nancanon (canon on) on
# the `griggio-chains` suite -- real-world QF_FP problems that are CHAINS of
# floating-point ops (nested fp.add/sub/mul/div), unsat + float32, fplean-supported.
# These exercise the pack/unpack-cancellation (NaN-canonicalization) pass that the
# special fplean-nancanon enables and the normal fplean disables, so this is the
# suite that measures the canonicalization axiom's performance value.
#
# Runs directly on the current machine; to run in the container use
# ./docker-run-griggio-chains.sh. Locally, pass host solver paths:
#   BITWUZLA_PATH=/opt/homebrew/bin/bitwuzla LEANWUZLA_DIR=leanwuzla \
#     ./run-griggio-chains.sh
#
# Override knobs via env, e.g.  NPROBLEMS=8 TIMEOUT_SEC=120 ./run-griggio-chains.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-griggio-chains}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

# The griggio family lives in QF_FP.tar.zst; extract it if the tree isn't already
# unpacked (the container image unpacks at build time; mirror that for host runs).
if [[ ! -d datasets/non-incremental/QF_FP/griggio ]]; then
    if [[ ! -f datasets/QF_FP.tar.zst ]]; then
        echo "ERROR: griggio missing and datasets/QF_FP.tar.zst not found" >&2
        exit 1
    fi
    echo "== extracting datasets/QF_FP.tar.zst =="
    tar --use-compress-program=unzstd -xf datasets/QF_FP.tar.zst -C datasets/
fi

# --nproblems is only passed when NPROBLEMS is set (otherwise the whole suite).
NPROBLEMS_FLAG=()
if [ -n "${NPROBLEMS:-}" ]; then
    NPROBLEMS_FLAG=(--nproblems "$NPROBLEMS")
fi

exec uv run ./cli.py cactus --run --plot \
    --suite griggio-chains \
    --guid "$GUID" \
    "${NPROBLEMS_FLAG[@]}" \
    --runs "$RUNS" \
    --timeout-sec "$TIMEOUT_SEC" \
    --memout-mb "$MEMOUT_MB" \
    --nproc "$NPROC"
