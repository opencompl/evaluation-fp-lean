#!/usr/bin/env bash
# Run run-fptg-oracle-tests.sh (the FPTG oracle soundness gate) inside the
# container via podman. The image ships the extracted fptg dataset and the built
# leanwuzla, so no host setup is needed. Env knobs are forwarded, e.g.
#   SUITE=fptg-float16 TOOLS=fplean ./docker-run-fptg-oracle-tests.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-fptg-oracle-tests.sh
