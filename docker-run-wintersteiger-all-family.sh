#!/usr/bin/env bash
# Run run-wintersteiger-all-family.sh (bitwuzla vs fp-lean, the full
# wintersteiger QF_FP family) inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   NPROBLEMS=2000 TIMEOUT_SEC=60 ./docker-run-wintersteiger-all-family.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-wintersteiger-all-family.sh
