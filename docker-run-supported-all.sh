#!/usr/bin/env bash
# Run run-supported-all.sh (bitwuzla vs fp-lean, full unsat supported QF_FP set)
# inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   RUNS=2 TIMEOUT_SEC=120 ./docker-run-supported-all.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-supported-all.sh
