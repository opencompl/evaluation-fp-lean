#!/usr/bin/env bash
# Camera-ready run: regenerate the paper's three headline result sets, each with
# a cactus plot and a suite-prefixed cactus.tex (so all can be \input together):
#
#   (a) wintersteiger-supported-family -- 2000-problem sample (seed 42), bitwuzla
#       vs the fp-lean pair on the unsat supported QF_FP set.
#   (b) instcombine-small -- all 50 tiny-width (E5M2/E5M4) InstCombine identities,
#       a 4-way comparison including exhaustive-enumeration.
#   (c) smtlib-rand -- a stratified sample across ALL 8 QF_FP families (not just
#       wintersteiger), all four tools. NPROBLEMS here is a PER-FAMILY cap.
#
# Runs on the current machine; for the container use ./docker-run-camera-ready.sh.
# Locally, pass host solver paths. NOTE: instcombine-small uses the non-standard
# E5M2/E5M4 minifloats, so bitwuzla must parse those -- the qfbv / container build
# does (the earlier "--fpexp" worry was actually a define-const issue, now fixed):
#   BITWUZLA_PATH=/path/to/bitwuzla LEANWUZLA_DIR=leanwuzla ./run-camera-ready.sh
#
# Override knobs via env, e.g.  NPROBLEMS=500 TIMEOUT_SEC=120 ./run-camera-ready.sh
set -euo pipefail
cd "$(dirname "$0")"

NPROBLEMS="${NPROBLEMS:-2000}"   # sample size for (a); (b) always runs all 50
# smtlib-rand (c) is stratified, so its --nproblems is a PER-FAMILY cap, not a
# total; keep it separate from (a)'s total sample size.
SMTLIB_RAND_NPROBLEMS="${SMTLIB_RAND_NPROBLEMS:-300}"
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

# wintersteiger-supported-family and smtlib-rand both read datasets/non-incremental/QF_FP.
ensure_dataset datasets/non-incremental/QF_FP datasets/QF_FP.tar.zst
# instcombine-small reads datasets/instcombine-small.
ensure_dataset datasets/instcombine-small datasets/instcombine-small.tar.zst

echo "== camera-ready (1/3): wintersteiger-supported-family sample =="
uv run ./cli.py cactus --run --plot \
    --suite wintersteiger-supported-family \
    --guid wintersteiger-supported-family-sample \
    --nproblems "$NPROBLEMS" \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo "== camera-ready (2/3): instcombine-small =="
uv run ./cli.py cactus --run --plot \
    --suite instcombine-small \
    --guid instcombine-small \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo "== camera-ready (3/3): smtlib-rand (stratified, per-family cap $SMTLIB_RAND_NPROBLEMS) =="
uv run ./cli.py cactus --run --plot \
    --suite smtlib-rand \
    --guid smtlib-rand \
    --nproblems "$SMTLIB_RAND_NPROBLEMS" \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo
echo "camera-ready outputs:"
echo "  runresults/wintersteiger-supported-family-sample/outputs/plots/cactus/  (\\WintersteigerSupportedFamily... macros)"
echo "  runresults/instcombine-small/outputs/plots/cactus/                      (\\InstcombineSmall... macros)"
echo "  runresults/smtlib-rand/outputs/plots/cactus/                            (\\SmtlibRand... macros)"
