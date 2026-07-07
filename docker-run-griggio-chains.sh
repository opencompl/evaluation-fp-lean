#!/usr/bin/env bash
# Run run-griggio-chains.sh (bitwuzla vs fplean vs fplean-nancanon on the
# griggio FP-chain problems, to measure the NaN-canonicalization delta) inside the
# container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   NPROBLEMS=8 TIMEOUT_SEC=120 ./docker-run-griggio-chains.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-griggio-chains.sh
