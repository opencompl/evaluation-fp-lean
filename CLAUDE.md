# CLAUDE.md

Guidance for working in this repo (the FP-Lean SMT evaluation harness).

## Run scripts: local vs. docker

Each test comes in two flavors:

- `run-<name>.sh` — runs the test **directly on the current machine**. Assumes
  the dataset is already extracted and `uv` is available.
- `docker-run-<name>.sh` — runs the same `run-<name>.sh` **inside the container**
  via podman (`docker-mount-script-and-run.sh`), which bind-mounts `runresults/`
  so output lands back on the host and forwards the env knobs into the container.

The tests:

- `run-smoke.sh` / `docker-run-smoke.sh` — small sample run (defaults: 4
  problems, 1 run, 60s timeout) for a quick sanity check.
- `run-all.sh` / `docker-run-all.sh` — full run over every problem in the dataset.
- `run-debug.sh` / `docker-run-debug.sh` — single `.smt2` file against both
  solvers, printing raw records.
- `run-wintersteiger-supported-family-sample.sh` /
  `docker-run-wintersteiger-supported-family-sample.sh` — bitwuzla vs fp-lean on a
  deterministic 2000-problem sample (seed 42) of the unsat, fplean-supported
  wintersteiger QF_FP set, with a cactus plot.
- `run-wintersteiger-supported-family.sh` /
  `docker-run-wintersteiger-supported-family.sh` — same but the full ~11.5k set.
- `run-wintersteiger-all-family.sh` / `docker-run-wintersteiger-all-family.sh` —
  the full wintersteiger family (every operator, sat and unsat; ~40k). Pair with
  `NPROBLEMS` to sample, since fplean cannot solve most of it.
- `run-instcombine-fp-problems.sh` / `docker-run-instcombine-fp-problems.sh` —
  all ~101 InstCombine fp-problems (QF_FP optimization-equivalence checks).
- `run-camera-ready.sh` / `docker-run-camera-ready.sh` — the paper's three
  headline suites back to back (`wintersteiger-supported-family` 2000-sample,
  then `instcombine-small`, then `smtlib-rand`), each with a cactus plot and
  suite-prefixed `cactus.tex`. `smtlib-rand` is stratified, so its per-family cap
  is a separate `SMTLIB_RAND_NPROBLEMS` knob (default 300) distinct from the
  `NPROBLEMS` total that sizes the wintersteiger sample.
- `run-fptg-oracle-tests.sh` / `docker-run-fptg-oracle-tests.sh` — the FPTG oracle
  **soundness gate**: run fp-lean over an fptg suite (default `fptg-float8`) and
  fail (exit 1) if any verdict disagrees with the MPFR/PyMPF oracle
  `(set-info :status)`. Errors on unimplemented ops (fp.max/min/sqrt/
  roundToIntegral) are tolerated (xfail) and reported per op. Overridable via
  `SUITE`/`TOOLS`/`NPROBLEMS`. This wraps the `cli.py fptg-oracle-tests`
  subcommand and is what CI runs (`.github/workflows/fptg-oracle-tests.yml`; the
  kernel-checked `fplean` path is the blocking gate, `fplean-nokernel` runs
  informationally because it has a known fp.fma soundness bug).
- `run-smtlib-rand.sh` / `docker-run-smtlib-rand.sh` — all four tools on a
  **stratified** sample across **every** QF_FP family (not just wintersteiger,
  which is ~99% of QF_FP). Because the `smtlib-rand` suite is stratified,
  `NPROBLEMS` here is a **per-family cap** (not a total): each family contributes
  `min(NPROBLEMS, family-size)` problems, so the small real-world families are
  represented. `NPROBLEMS=300` -> 712 files. Deterministic (seed 42).
- `run-full-smtlib-fast.sh` / `docker-run-full-smtlib-fast.sh` — a **soundness
  sweep over the entire QF_FP set** (all 8 families, ~40,406 problems), all four
  tools, with a short `TIMEOUT_SEC=10` so the full run finishes in a few hours
  and can be looped. Reuses the stratified `smtlib-rand` suite with a per-family
  cap of 40000 (>= the largest family, so "take everything" = all of QF_FP, not
  a sample). Not a timing measurement — the point is to catch soundness
  regressions across all of QF_FP (`plot.py` grades every verdict against the
  declared `(set-info :status)`). Defaults to `NPROC=24`.

All accept env overrides, e.g. `NPROBLEMS=8 RUNS=2 ./run-smoke.sh` or
`TIMEOUT_SEC=900 ./docker-run-all.sh`.

### Suites (`--suite`)

`cli.py` takes a `--suite <name>` option (default
`wintersteiger-supported-family`) that fully fixes which problems run — the
dataset tree, the families under it, and an optional `(set-info :status ...)`
filter. We only target `QF_FP` (fplean cannot handle the quantifiers in the `FP`
division). The suites are the `bench.SUITES` registry (each a frozen
`bench.Suite` dataclass); `--suite` threads the chosen `Suite` down through
`cactus_configs → sampled_problems → fp_problems`.

- `wintersteiger-supported-family` — the QF_FP/wintersteiger operations fplean
  supports, restricted to unsat instances (the problems both solvers finish;
  ~11.5k). The `run-wintersteiger-supported-family*.sh` scripts pass this suite.
- `wintersteiger-all-family` — the whole wintersteiger family: every operator,
  sat and unsat (~40k). fplean can only solve a fraction.
- `instcombine-fp-problems` — ~101 QF_FP equivalence checks extracted from LLVM
  InstCombine tests (`datasets/instcombine.tar.zst`; not SMT-LIB).
- `fptg-float8` / `fptg-float16` / `fptg-bfloat16` — Schanda's `fp_test_generator`
  suite (`datasets/fptg-testsuite.tar.zst`, derived from the `fptg-testsuite`
  submodule with `define-const` rewritten to `define-fun` so bitwuzla parses it):
  ground QF_FP tests whose `(set-info :status)` is an MPFR/PyMPF **oracle** ground
  truth, so they measure soundness.
  `fptg-float8` (8-bit, 256 values) adds `exhaustive-enumeration` to its tools;
  the 16-bit ones run bitwuzla vs the fplean pair only. (These are ground
  problems, so enumeration just evaluates -- it does not enumerate a domain.)
- `instcombine-small` — the 25 constant-free (width-parametric) InstCombine
  identities reparametrized to tiny widths E5M2 (`5 3`) and E5M4 (`5 5`), 50 total
  (`datasets/instcombine-small.tar.zst`). These have 1-3 free FP variables, so
  `exhaustive-enumeration` genuinely enumerates (feasible for ≤2 vars, times out
  beyond). All four tools run.
- `smtlib-rand` — a sample across **all 8** top-level QF_FP families
  (`datasets/non-incremental/QF_FP`: wintersteiger + griggio, ramalho, schanda,
  20210211-Vector and the three UltimateAutomizer sets), not just wintersteiger.
  QF_FP is ~99% wintersteiger (39,994 of 40,406 files), so this suite is the only
  **stratified** one (`Suite.stratified=True`): `--nproblems` is a **per-family
  cap**, so `sampled_problems` takes `min(cap, family-size)` per family and every
  family is represented (`cap=300` -> 712 files). `status=None` keeps sat/unsat/
  unknown (a coverage survey, not an oracle set); all four tools run. The
  non-wintersteiger families are small real-world float32/float64 verification
  problems — mostly fplean-operator-compatible but hard, so fplean often times
  out (informative for coverage). To make a suite stratified, set
  `stratified=True` on its `bench.Suite`.

Each benchmark's declared `(set-info :status ...)` is recorded per problem as
`expected_status` and threaded into the records. `plot.py` grades every solver
against it: `NumErrors` (ran, no verdict), `NumDisagreementsWithExpectedStatus`
and `PercentDisagreementsWithExpectedStatus` (gave a definite verdict that
contradicts the oracle = unsound), printed in the summary and emitted as LaTeX
macros. Every `cactus.tex` macro is prefixed with the suite name (via
`_texprefix`, which spells digits out so `fptg-float8`/`fptg-float16` stay
distinct) so multiple runs' tex files can be `\input` together without clashing.

`run-smoke.sh` and `run-all.sh` accept a `SUITE` env var that maps to `--suite`.

**To extend which ops count as supported, edit the `families` list of the
`wintersteiger-supported-family` entry in `bench.SUITES`.**

The container image (`localhost/fp-lean-eval`) is built from `Dockerfile` and
ships the extracted dataset plus the built `leanwuzla` binary. Rebuild the image
whenever `Dockerfile`, the dataset, or the Leanwuzla pin changes.

## Harness layout

- `cli.py` — entry point (`cactus` experiment); dispatches `--run` / `--plot`.
- `bench.py` — problem discovery, per-tool command construction, the runner.
- `lib.py`, `runwithlimits.py`, `plot.py` — helpers (system specs, time/mem
  limits, plotting). `cli_old.py` is the legacy driver; prefer `cli.py`.

## Tools under test

`bench.TOOLS = ["bitwuzla", "fplean"]`.

- `fplean` is the **Leanwuzla** CLI (`leanwuzla/.lake/build/bin/leanwuzla`),
  invoked as `lake env leanwuzla --timeout <wall-limit> <problem.smt2>` from the
  `leanwuzla` project root (`$LEANWUZLA_DIR`, default `leanwuzla` -- the
  lowercase submodule dir; the container pins it via `ENV LEANWUZLA_DIR`). (It
  replaced the old Blase `blasewuzla` backend.)
- `bitwuzla` is the upstream solver baseline (`BITWUZLA_PATH`).
