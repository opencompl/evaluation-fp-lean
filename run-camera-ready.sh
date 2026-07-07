#!/usr/bin/env bash
# Camera-ready run: regenerate the paper's two headline result sets, each with a
# cactus plot and a suite-prefixed cactus.tex (so both can be \input together):
#
#   (a) smtlib-rand -- a uniform sample across ALL 8 top-level SMT-LIB QF_FP
#       families (not just wintersteiger): it is STRATIFIED, so NPROBLEMS is a
#       PER-FAMILY cap (default 4000 -> 4412 files), giving every family equal
#       representation. Only wintersteiger exceeds the cap (~40k files, capped at
#       4000); the other 7 families are all included in full (412 files: griggio
#       214, Vector 91, schanda 44, ramalho 36, UA2019 24, Heizmann 2, UA2023 1).
#       Keeps sat/unsat/unknown; the cactus counts every solve (sat OR unsat that
#       doesn't contradict the oracle). bitwuzla vs the fp-lean pair (kernel +
#       no-kernel). At NPROC=14 (the trustworthy-timing ceiling on a 16-core box)
#       this leg runs in ~1 h.
#   (b) instcombine-small -- all 100 tiny-width InstCombine identities (E5M2/E5M4/
#       isoslow/bf16), a 4-way comparison including exhaustive-enumeration.
#
# Runs on the current machine; for the container use ./docker-run-camera-ready.sh.
# Locally, pass host solver paths. NOTE: instcombine-small uses non-standard
# minifloats, so bitwuzla must parse those -- the qfbv / container build does:
#   BITWUZLA_PATH=/path/to/bitwuzla LEANWUZLA_DIR=leanwuzla ./run-camera-ready.sh
#
# Override knobs via env, e.g.  NPROBLEMS=100 TIMEOUT_SEC=60 ./run-camera-ready.sh
set -euo pipefail
cd "$(dirname "$0")"

# smtlib-rand (a) is stratified, so NPROBLEMS is a PER-FAMILY cap; 4000 -> 4412
# files across the 8 QF_FP families. (b) always runs all 100.
NPROBLEMS="${NPROBLEMS:-4000}"
RUNS="${RUNS:-1}"
TIMEOUT_SEC="${TIMEOUT_SEC:-60}"
MEMOUT_MB="${MEMOUT_MB:-8000}"
# NPROC=14: below the 16 physical cores of the Ryzen 9 9950X (uncontended, so
# recorded per-problem timings stay trustworthy) yet high enough that the cap-4000
# smtlib-rand leg finishes in ~1 h.
NPROC="${NPROC:-14}"

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

# smtlib-rand reads every family under datasets/non-incremental/QF_FP. Sentinel on
# a NON-wintersteiger family (griggio): a checkout may have only wintersteiger
# extracted, which would leave the parent dir present but the other 7 families
# missing -- checking griggio forces a full extract in that case.
ensure_dataset datasets/non-incremental/QF_FP/griggio datasets/QF_FP.tar.zst
# instcombine-small reads datasets/instcombine-small.
ensure_dataset datasets/instcombine-small datasets/instcombine-small.tar.zst

echo "== camera-ready (1/2): smtlib-rand (stratified across all QF_FP families, per-family cap $NPROBLEMS) =="
uv run ./cli.py cactus --run --plot \
    --suite smtlib-rand \
    --guid smtlib-rand \
    --nproblems "$NPROBLEMS" \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo "== camera-ready (2/2): instcombine-small =="
uv run ./cli.py cactus --run --plot \
    --suite instcombine-small \
    --guid instcombine-small \
    --runs "$RUNS" --timeout-sec "$TIMEOUT_SEC" --memout-mb "$MEMOUT_MB" --nproc "$NPROC"

echo
echo "camera-ready outputs:"
echo "  runresults/smtlib-rand/outputs/plots/cactus/        (\\SmtlibRand... macros)"
echo "  runresults/instcombine-small/outputs/plots/cactus/  (\\InstcombineSmall... macros)"
