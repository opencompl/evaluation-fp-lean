#!/usr/bin/env bash
# Full run: evaluate every problem in the dataset.
#
# Runs inside the container via podman (docker-mount-script-and-run.sh).
# Omitting --nproblems makes the harness use the entire dataset.
#
# Override knobs via env, e.g.  RUNS=3 TIMEOUT_SEC=900 ./run-all.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-all}"
RUNS="${RUNS:-2}"
TIMEOUT_SEC="${TIMEOUT_SEC:-600}"
MEMOUT_MB="${MEMOUT_MB:-16000}"
NPROC="${NPROC:-4}"

exec ./docker-mount-script-and-run.sh \
    uv run ./cli.py cactus --run \
        --guid "$GUID" \
        --runs "$RUNS" \
        --timeout-sec "$TIMEOUT_SEC" \
        --memout-mb "$MEMOUT_MB" \
        --nproc "$NPROC"
