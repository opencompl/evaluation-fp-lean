#!/usr/bin/env bash
# Run the smoke test (run-smoke.sh) inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   NPROBLEMS=8 RUNS=2 ./docker-run-smoke.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-smoke.sh
