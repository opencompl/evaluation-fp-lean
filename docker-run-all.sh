#!/usr/bin/env bash
# Run the full evaluation (run-all.sh) inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   RUNS=3 TIMEOUT_SEC=900 ./docker-run-all.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-all.sh
