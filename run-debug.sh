#!/usr/bin/env bash
# Debug runner: run a single .smt2 file against both solvers and print the
# raw results.
#
# Runs inside the container via podman (docker-mount-script-and-run.sh). FILE
# must be a path resolvable inside the container, e.g. a file already under
# datasets/ (baked into the image at build time).
#
# Usage:           ./run-debug.sh datasets/non-incremental/FP/<family>/<problem>.smt2
# Override knobs via env, e.g.  TIMEOUT_SEC=300 ./run-debug.sh path/to/problem.smt2
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -lt 1 ]; then
    echo "usage: $0 <path-to-smt2-file>" >&2
    exit 1
fi
FILE="$1"

GUID="${GUID:-debug}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-4}"

./docker-mount-script-and-run.sh \
    uv run ./cli.py debug --run \
        --file "$FILE" \
        --guid "$GUID" \
        --runs "$RUNS" \
        --timeout-sec "$TIMEOUT_SEC" \
        --memout-mb "$MEMOUT_MB" \
        --nproc "$NPROC"

echo
echo "=== records: runresults/$GUID/data/ ==="
for f in runresults/"$GUID"/data/*.jsonl; do
    echo "--- $f ---"
    python3 -m json.tool < "$f"
done
