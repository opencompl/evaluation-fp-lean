#!/usr/bin/env bash
# Run run-full-smtlib-fast.sh (the whole QF_FP set, 10s timeout, soundness
# sweep) inside the container via podman. Rebuild the image first (make
# docker-build) so it includes any local leanwuzla fixes. Env knobs are
# forwarded, e.g.  TIMEOUT_SEC=5 NPROC=28 ./run-full-smtlib-fast-docker.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-full-smtlib-fast.sh
