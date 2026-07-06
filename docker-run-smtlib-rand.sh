#!/usr/bin/env bash
# Run run-smtlib-rand.sh (all tools on a stratified cross-family QF_FP sample)
# inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   NPROBLEMS=100 TIMEOUT_SEC=120 ./docker-run-smtlib-rand.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-smtlib-rand.sh
