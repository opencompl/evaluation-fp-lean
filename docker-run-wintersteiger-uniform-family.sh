#!/usr/bin/env bash
# Run run-wintersteiger-uniform-family.sh (bitwuzla vs fp-lean, the wintersteiger
# QF_FP family sampled uniformly per operator) inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   NPROBLEMS=200 TIMEOUT_SEC=60 ./docker-run-wintersteiger-uniform-family.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-wintersteiger-uniform-family.sh
