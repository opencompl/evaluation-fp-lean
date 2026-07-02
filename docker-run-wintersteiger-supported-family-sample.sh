#!/usr/bin/env bash
# Run run-wintersteiger-supported-sample.sh (bitwuzla vs fp-lean, sampled unsat
# wintersteiger-supported QF_FP set) inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   NPROBLEMS=500 TIMEOUT_SEC=120 ./docker-run-wintersteiger-supported-sample.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-wintersteiger-supported-sample.sh
