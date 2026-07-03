#!/usr/bin/env bash
# Run run-camera-ready.sh (both paper headline suites) inside the container via
# podman. The container bitwuzla parses the E5M2/E5M4 minifloats and the image
# ships the extracted datasets. Env knobs are forwarded, e.g.
#   NPROBLEMS=500 TIMEOUT_SEC=120 ./docker-run-camera-ready.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-camera-ready.sh
