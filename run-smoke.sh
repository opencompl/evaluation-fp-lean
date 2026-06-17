#!/usr/bin/env bash
# Smoke test: run the FP evaluation on a small sample of problems.
#
# Runs inside the container via podman (docker-mount-script-and-run.sh).
# Assumes the benchmark dataset is already extracted inside the image
# (the Dockerfile unpacks datasets/*.tar.zst at build time).
#
# Override knobs via env, e.g.  NPROBLEMS=8 RUNS=2 ./run-smoke.sh
set -euo pipefail
cd "$(dirname "$0")"

GUID="${GUID:-smoke}"
NPROBLEMS="${NPROBLEMS:-4}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-4}"

exec ./docker-mount-script-and-run.sh \
    uv run ./cli.py cactus --run \
        --guid "$GUID" \
        --nproblems "$NPROBLEMS" \
        --runs "$RUNS" \
        --timeout-sec "$TIMEOUT_SEC" \
        --memout-mb "$MEMOUT_MB" \
        --nproc "$NPROC"
