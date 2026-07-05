#!/usr/bin/env bash
# Run run-fptg-oracle-tests.sh (the FPTG oracle soundness gate) inside the
# container via podman. The image ships the extracted fptg dataset and the built
# leanwuzla, so no host setup is needed. Every QF_FP op fp-lean parses -- now
# including fp.fma, fp.sqrt, fp.min, fp.max, and fp.roundToIntegral -- is
# bit-blasted and expected to pass, so a solver error on any op fails the gate
# (no xfail tolerance). Env knobs are forwarded, e.g.
#   SUITE=fptg-float16 TOOLS=fplean ./docker-run-fptg-oracle-tests.sh
set -euo pipefail
cd "$(dirname "$0")"

exec ./docker-mount-script-and-run.sh ./run-fptg-oracle-tests.sh
