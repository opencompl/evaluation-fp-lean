#!/usr/bin/env bash
# Run run-instcombine-fp-problems.sh (bitwuzla vs fp-lean on the InstCombine
# fp-problems suite) inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   TIMEOUT_SEC=120 RUNS=2 ./docker-run-instcombine-fp-problems.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-instcombine-fp-problems.sh
