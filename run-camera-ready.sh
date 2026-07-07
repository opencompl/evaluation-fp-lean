#!/usr/bin/env bash
# Camera-ready run: regenerate the paper's two headline result sets, each with a
# cactus plot and a suite-prefixed cactus.tex (so both can be \input together):
#
#   (a) wintersteiger-uniform-family -- a STRATIFIED sample of the wintersteiger
#       QF_FP set: every operator, unsat only, weighted equally. Because it is
#       stratified, NPROBLEMS is a PER-FAMILY cap (default 150 -> 150*14 = 2100
#       problems), not a total. bitwuzla vs the fp-lean pair (kernel + no-kernel).
#   (b) instcombine-small -- all 50 tiny-width (E5M2/E5M4) InstCombine identities,
#       a 4-way comparison including exhaustive-enumeration.
#
# Runs on the current machine; for the container use ./docker-run-camera-ready.sh.
# Locally, pass host solver paths. NOTE: instcombine-small uses the non-standard
# E5M2/E5M4 minifloats, so bitwuzla must parse those -- the qfbv / container build
# does (the earlier "--fpexp" worry was actually a define-const issue, now fixed):
#   BITWUZLA_PATH=/path/to/bitwuzla LEANWUZLA_DIR=leanwuzla ./run-camera-ready.sh
#
# Override knobs via env, e.g.  NPROBLEMS=200 TIMEOUT_SEC=60 ./run-camera-ready.sh
set -euo pipefail
cd "$(dirname "$0")"

# wintersteiger-uniform-family (a) is stratified, so NPROBLEMS is a PER-FAMILY
# cap; 150 -> 2100 problems across the 14 operators. (b) always runs all 50.
NPROBLEMS="${NPROBLEMS:-150}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
NPROC="${NPROC:-6}"

# Extract a dataset tarball if its tree isn't already unpacked. Locally the
# datasets/*.tar.zst archives are shipped but not extracted (the container image
# unpacks them at build time; see the Dockerfile). Mirror that here so a fresh
# checkout can run the camera-ready without a manual extract step.
#   $1 = directory that must exist   $2 = tarball to extract if it doesn't
ensure_dataset() {
    local dir="$1" tarball="$2"
    if [[ -d "$dir" ]]; then return 0; fi
    if [[ ! -f "$tarball" ]]; then
        echo "ERROR: $dir missing and tarball $tarball not found" >&2
        exit 1
    fi
    echo "== extracting $tarball -> $dir =="
    tar --use-compress-program=unzstd -xf "$tarball" -C datasets/
}

# wintersteiger-uniform-family reads datasets/non-incremental/QF_FP/wintersteiger.
ensure_dataset datasets/non-incremental/QF_FP/wintersteiger datasets/QF_FP.tar.zst
# instcombine-small reads datasets/instcombine-small.
ensure_dataset datasets/instcombine-small datasets/instcombine-small.tar.zst

echo "== camera-ready (1/2): wintersteiger-uniform-family (stratified, per-family cap $NPROBLEMS) =="
uv run ./cli.py cactus --run --plot \
    --suite wintersteiger-uniform-family \
    --guid wintersteiger-uniform-family \
    --nproblems "$NPROBLEMS" \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo "== camera-ready (2/2): instcombine-small =="
uv run ./cli.py cactus --run --plot \
    --suite instcombine-small \
    --guid instcombine-small \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo
echo "camera-ready outputs:"
echo "  runresults/wintersteiger-uniform-family/outputs/plots/cactus/  (\\WintersteigerUniformFamily... macros)"
echo "  runresults/instcombine-small/outputs/plots/cactus/             (\\InstcombineSmall... macros)"
