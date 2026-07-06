#!/usr/bin/env bash
# Run run-full-smtlib-trustworthy.sh (the whole QF_FP set, 60s timeout, NPROC=14,
# cactus-quality timings) inside the container via podman. Rebuild the image
# first (make docker-build) so it includes any local leanwuzla fixes. Env knobs
# are forwarded, e.g.  NPROC=12 TIMEOUT_SEC=30 ./run-full-smtlib-trustworthy-docker.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-full-smtlib-trustworthy.sh
