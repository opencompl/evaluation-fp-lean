#!/usr/bin/env bash
# Run run-instcombine-small.sh (all four tools on the tiny-width E5M2/E5M4
# InstCombine-small identities) inside the container via podman.
#
# Env knobs are forwarded into the container, e.g.
#   TIMEOUT_SEC=120 ./docker-run-instcombine-small.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-instcombine-small.sh
