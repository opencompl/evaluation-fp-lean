#!/usr/bin/env bash
# Run the debug runner (run-debug.sh) inside the container via podman.
#
# The .smt2 path must resolve inside the container (e.g. a file under
# datasets/, baked into the image at build time).
#
# Usage:  ./docker-run-debug.sh datasets/non-incremental/FP/<family>/<problem>.smt2
# Env knobs are forwarded, e.g.  TIMEOUT_SEC=300 ./docker-run-debug.sh path/to/problem.smt2
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-debug.sh "$@"
