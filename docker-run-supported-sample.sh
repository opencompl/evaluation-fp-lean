#!/usr/bin/env bash
# Run run-supported-sample.sh (bitwuzla vs fp-lean, sampled unsat supported
# QF_FP set) inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   NPROBLEMS=500 TIMEOUT_SEC=120 ./docker-run-supported-sample.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-supported-sample.sh
