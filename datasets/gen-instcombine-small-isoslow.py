#!/usr/bin/env -S uv run
"""Generate the `isoslow` family of the instcombine-small dataset and repack.

The instcombine-small identities are constant-free and width-parametric: an
E<eb>M<sb> variant is just the token `(_ FloatingPoint eb sb)` substituted on the
`declare-fun` lines (the e5m2 and e5m4 families differ by nothing else). This adds
a third family, `isoslow`, whose whole point is to make `exhaustive-enumeration`
*slow but still terminating* (seconds to ~15s single-run), so the cactus shows
enumeration's exponential wall against the fast SMT tools.

Enumeration cost is (values per var)^(#vars), but the native-eval cost PER value
tuple varies ~40x across these identities (an fp.sub-of-fp.sub is ~80us/eval; an
fp.neg is ~2us), and throughput also drops with the variable count. So neither a
single width nor a per-variable-count width can equalize them -- picking a width
per variable-count left 14 of 25 timing out. Instead each identity gets its OWN
width, calibrated from its measured throughput.

Calibration (frozen in WIDTH_BY_IDENTITY below): each identity was enumerated once
at a small reference width (~2^20-2^21 evals) to measure its throughput r
(evals/s); its width is then the largest whose total evaluations (2^bits)^nvars
keep the single-run wall under ~15s (r * 15s), floored to whole bits per variable.
That ~15s single-run budget leaves margin for the ~2-2.5x slowdown seen under the
14-way parallel harness run (memory-bandwidth contention), so every identity still
terminates well under a 60s timeout. Re-derive by re-running the reference sweep
(see the repo's calibration notes) if the identities or the enumerator change.

The bit-widths are non-standard FloatingPoint sorts, same as e5m2/e5m4; the
container bitwuzla (qfbv build) and leanwuzla both parse arbitrary (eb, sb).

Run from the repo root:  ./datasets/gen-instcombine-small-isoslow.py
It rebuilds datasets/instcombine-small.tar.zst in place (e5m2 + e5m4 + isoslow).
"""
import pathlib
import re
import shutil
import subprocess
import tempfile

# Per-identity FloatingPoint width (eb, sb), calibrated so exhaustive-enumeration
# runs ~2-15s single-run (heavier identities get narrower floats). See module
# docstring for the derivation.
WIDTH_BY_IDENTITY: dict[str, tuple[int, int]] = {
    "2008-07-16-fsub.ll--test.smt2":                          (8, 13),
    "fabs-copysign.ll--fabs_copysign_commuted_mismatch.smt2": (8, 2),
    "fabs-copysign.ll--fabs_copysign_mismatch.smt2":          (8, 2),
    "fabs-fneg-fold.ll--fabs_fneg_basic.smt2":                (8, 14),
    "fabs-fneg-fold.ll--fabs_fneg_f64.smt2":                  (8, 14),
    "fabs-fneg-fold.ll--fabs_fneg_multi_use.smt2":            (8, 14),
    "fabs-fneg-fold.ll--fabs_fneg_no_fabs.smt2":              (8, 14),
    "fabs.ll--square_fabs_intrinsic_f32.smt2":                (8, 12),
    "fabs.ll--square_fabs_intrinsic_f64.smt2":                (8, 12),
    "fdiv-sqrt.ll--sqrt_div.smt2":                            (4, 2),
    "fdiv.ll--fabs_fabs.smt2":                                (8, 2),
    "fdiv.ll--fabs_same_op.smt2":                             (8, 11),
    "fdiv.ll--fdiv_unary_fneg1.smt2":                         (8, 2),
    "fdiv.ll--unary_fneg_unary_fneg.smt2":                    (7, 2),
    "fmul-sqrt.ll--sqrt_a_sqrt_b.smt2":                       (8, 2),
    "fmul.ll--fabs_fabs.smt2":                                (8, 2),
    "fmul.ll--fabs_squared.smt2":                             (8, 11),
    "fmul.ll--unary_neg_mul.smt2":                            (8, 2),
    "fmul.ll--unary_neg_mul_multi_use.smt2":                  (7, 2),
    "fneg.ll--fneg_fneg.smt2":                                (8, 14),
    "fsub.ll--fneg_fsub.smt2":                                (7, 2),
    "fsub.ll--fsub_fsub.smt2":                                (4, 2),
    "fsub.ll--test1_unary.smt2":                              (7, 2),
    "fsub.ll--test2.smt2":                                    (7, 2),
    "fsub.ll--unary_neg_op1.smt2":                            (7, 2),
}

_FP_TOKEN = re.compile(r"\(_ FloatingPoint \d+ \d+\)")

REPO = pathlib.Path(__file__).resolve().parent.parent
TARBALL = REPO / "datasets" / "instcombine-small.tar.zst"


def reparametrize(text: str, eb: int, sb: int) -> str:
    """Replace every FloatingPoint width token with (_ FloatingPoint eb sb)."""
    return _FP_TOKEN.sub(f"(_ FloatingPoint {eb} {sb})", text)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        subprocess.run(
            ["tar", "--use-compress-program=unzstd", "-xf", str(TARBALL), "-C", str(work)],
            check=True)
        root = work / "instcombine-small"
        src = root / "e5m2"          # the reference family; isoslow is derived from it
        dst = root / "isoslow"
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir()

        src_names = {f.name for f in src.glob("*.smt2")}
        missing = src_names ^ WIDTH_BY_IDENTITY.keys()
        if missing:
            raise SystemExit(f"WIDTH_BY_IDENTITY out of sync with e5m2/: {sorted(missing)}")

        for f in sorted(src.glob("*.smt2")):
            eb, sb = WIDTH_BY_IDENTITY[f.name]
            (dst / f.name).write_text(reparametrize(f.read_text(), eb, sb))

        # Also derive a uniform bf16 (E8M8) tier: 2^16 values/var, so
        # exhaustive-enumeration is feasible for the 1-var identities (~1s) and
        # blows up on the 2-/3-var ones -- a harder enumeration tier than e5m2/e5m4.
        bf16 = root / "bf16"
        if bf16.exists():
            shutil.rmtree(bf16)
        bf16.mkdir()
        for f in sorted(src.glob("*.smt2")):
            (bf16 / f.name).write_text(reparametrize(f.read_text(), 8, 8))

        # Repack the tarball in place with all four families.
        tmp_tar = work / "instcombine-small.tar.zst"
        subprocess.run(
            ["tar", "--use-compress-program=zstd", "-cf", str(tmp_tar),
             "-C", str(work), "instcombine-small"],
            check=True)
        shutil.copyfile(tmp_tar, TARBALL)

    n = len(WIDTH_BY_IDENTITY)
    print(f"wrote isoslow ({n} files, per-identity widths) + bf16 ({n} files, E8M8)")
    print(f"repacked {TARBALL.relative_to(REPO)}")


if __name__ == "__main__":
    main()
