# Evaluation for fp-lean

One entry point, `./cli.py`, which runs and/or plots an experiment. The logic is
split across three modules:

- `bench.py` — runner primitives: domain types, tool dispatch, dataset walk,
  deterministic sampling, and the parallel runner.
- `plot.py` — pure analysis over a runresults directory: parses raw records and
  emits plots + LaTeX.
- `lib.py` — shared helpers (system specs, plotting/formatting utilities).

## Running benchmarks

```
./cli.py <config-name> --run [--guid latest] [--nproblems N] [--runs 2]
         [--timeout-sec 600] [--memout-mb 16000] [--nproc 4]
```

Writes one jsonl file per datapoint into `runresults/<guid>/data/`. Default
`--guid` is `latest`. An existing `runresults/<guid>/` is wiped before a new run.

Each jsonl record contains raw fields only: `stdout`, `stderr`, `returncode`,
`wall_elapsed_ms`, `is_timeout`, `is_memout`, `is_exception`. No derived fields —
those are computed at plot time.

Alongside the records, `--run` also writes `manifest.json` (run parameters, git
hash, timestamp) into `runresults/<guid>/data/`, and `config.tex` / `triple.tex`
(LaTeX macros for the paper) into `runresults/<guid>/outputs/`. `manifest.json`
is also copied into `outputs/` for convenience.

## Plotting

```
./cli.py <plot-name> --plot [--guid latest] [--outdir DIR]
```

Reads every jsonl in `runresults/<guid>/data/`, parses the raw data (computes
`is_unsat`, `is_sat`, and the solver-specific `elapsed_ms`), and writes the plot
plus `cactus.tex` to `runresults/<guid>/outputs/plots/<plot-name>/` (unless
`--outdir`).

`--run` and `--plot` may be combined to do both in one invocation.

## Configurations and plots

Defined in `cli.py`:

- `cactus` — both solvers × `--runs` × a deterministically sampled subset (seed
  = `bench.SEED`) of the `--suite`'s problems (see **Benchmarks** below).
  Produces a cactus plot, geomean-averaged over runs.
- `debug` — both solvers against a single user-specified file (`--file PATH`),
  for quickly checking one problem. Defaults to `--runs 1` and `--guid debug`.

## Camera-ready run (paper headline results)

`docker-run-camera-ready.sh` regenerates the paper's two headline result sets in
one shot, inside the container (so the pinned `--fpexp` bitwuzla and the built
`leanwuzla` are used, and the extracted datasets are present). It is a thin
podman wrapper around `run-camera-ready.sh`, which invokes `cli.py cactus
--run --plot` twice — once per suite.

```
./docker-run-camera-ready.sh                        # full paper config (defaults below)
NPROBLEMS=500 TIMEOUT_SEC=120 ./docker-run-camera-ready.sh   # override any knob
```

### Precise configuration (what the paper should cite)

Both suites share these settings (the `run-camera-ready.sh` defaults; each is an
overridable env var). These are the exact numbers to report in the paper:

| knob                 | value    | meaning                                                        |
| -------------------- | -------: | -------------------------------------------------------------- |
| `RUNS`               |        1 | timing runs per (tool, problem); per-problem geomean-averaged if >1, and a problem must solve in *every* run to count |
| `TIMEOUT_SEC`        |       60 | wall-clock limit per solve (also passed to leanwuzla `--timeout`) |
| `MEMOUT_MB`          |     8000 | per-solve memory limit (8 GB); an active watchdog kills on breach |
| `NPROC`              |       14 | problems solved in parallel (harness process pool). ≤ the 16 physical cores of the Ryzen 9 9950X, so recorded per-problem timings stay uncontended/trustworthy |
| `SEED` (`bench.SEED`)|       42 | the SMT-LIB sampling seed (fixes suite (a)'s stratified sample) |

The two suites, run back to back:

**(a) `smtlib-rand`** — `--guid smtlib-rand`, `--nproblems 4000` (`NPROBLEMS`, the
default). A **stratified, uniform-per-family** sample across **all 8 top-level
SMT-LIB `QF_FP` families**, not just `wintersteiger`. QF_FP is ~99 %
`wintersteiger` (39,994 of 40,406 files), so a flat sample would miss the small
real-world families; stratification makes `NPROBLEMS` a **per-family cap**, i.e.
each family contributes `min(4000, family-size)`. Only `wintersteiger` exceeds the
cap (capped at 4000); the other 7 families are taken **in full** (412 files:
griggio 214, 20210211-Vector 91, schanda 44, ramalho 36,
20190429-UltimateAutomizer 24, 20170501-Heizmann 2, 20230321-UltimateAutomizer 1),
for **4,412 files** total. The sample keeps **sat, unsat, and unknown** instances
(it is a coverage survey, not an unsat-only oracle set), so the cactus counts every
solve — sat *or* unsat — that does not contradict the declared `(set-info :status)`.
Deterministic (seed 42). Tools: **bitwuzla, fplean, fplean-nokernel**
(3 tools × 4,412 = 13,236 datapoints).

**(b) `instcombine-small`** — `--guid instcombine-small`, **all 100 problems**
(this suite ignores `NPROBLEMS`): the 25 constant-free, width-parametric LLVM
InstCombine identities reparametrized to **four** minifloat width tiers, 25 each —
**E5M2** (`FloatingPoint 5 3`, 256 values/var), **E5M4** (`FloatingPoint 5 5`,
1024 values/var), **isoslow** (a per-identity width calibrated so every identity's
enumeration is slow-but-terminating), and **bf16** (`FloatingPoint 8 8`, 65 536
values/var — a uniform harder-enum tier that blows up on the 2-/3-variable
identities). Each is an `unsat` equivalence check (`:status unsat`), so they double
as a **soundness** test. Tools: **bitwuzla, fplean, fplean-nokernel,
exhaustive-enumeration** (the 3 SMT tools run all 100; this is the only paper suite
where `exhaustive-enumeration` runs, and it solves the tiers where brute
enumeration over the value domain is feasible).

### Sound SAT handling (fp-lean)

fp-lean is fundamentally a *proof / unsat* solver: it bit-blasts via `bv_decide`,
which on a **sat** goal returns a candidate counterexample. Because `bv_decide`
abstracts the FP field projections (`.sign/.ex/.sig`) it cannot bit-blast, that
model is flagged "potentially spurious" and it cannot itself certify `sat`. Earlier
these ~all surfaced as *errors*. As of leanwuzla `fp`-branch commit `2c7cf25`,
`fplean` instead **reconstructs** a concrete assignment for each goal binder from
the counterexample and **validates** it by native-evaluating the *proven-correct*
fp-lean semantics at that point (the same `Decidable`/`native_decide` machinery the
exhaustive enumerator uses): a model that genuinely satisfies the asserts is
reported as sound `sat`, a spurious one stays `unknown`. This is what lets `fplean`
score real `sat` solves on suite (a), and it **cannot produce an unsound `sat`**
(the witness is checked, modulo `Lean.ofReduceBool`). The feature is entirely in
leanwuzla — **no fp-lean changes** — and headline profiles keep the unproven
NaN-canonicalization axiom **off** (`--disable-fp-normalize`).

### How each tool is invoked

- **bitwuzla** — `bitwuzla <problem.smt2>` (image build uses `./configure.py
  --fpexp`, required to parse the E5M2/E5M4/isoslow/bf16 minifloats and other
  non-standard formats).
- **fplean** — `lake env leanwuzla --timeout <TIMEOUT_SEC> --maxHeartbeats
  9999999 --maxRecDepth 100000 --disable-fp-normalize <problem.smt2>`, from the
  `leanwuzla` project root. Bit-blasts via `bv_decide` and **re-checks the
  reflection proof in the Lean kernel**; `--disable-fp-normalize` keeps the
  unproven NaN-canonicalization axiom off (headline results must not rest on a new
  axiom). On a sat goal it reconstructs+validates the counterexample (see **Sound
  SAT handling**).
- **fplean-nokernel** — same, plus `--disableKernel`: only the LRAT certificate
  is verified, skipping the kernel re-check (`decideSmtNoKernel`). Runs
  informationally — it has a known `fp.fma` soundness bug, so `fplean` is the
  blocking/reported profile.
- **exhaustive-enumeration** — same, plus `--exhaustive-enumeration`: decides the
  goal by native-evaluating a `Decidable` instance over *all* FP values instead
  of `bv_decide` (axiom-free by construction; only feasible for tiny bit-widths,
  so it runs on suite (b) only).

### Outputs

Each suite writes to `runresults/<guid>/`:

- `data/*.jsonl` — one raw record per (tool, run, problem); `data/manifest.json`
  records the run parameters, git hash, and timestamp.
- `outputs/config.tex`, `outputs/triple.tex` — LaTeX macros for the config knobs
  and the machine specs.
- `outputs/plots/cactus/cactus.{pdf,png}` — the cactus plot (cumulative solve
  time vs. # problems solved, log-x).
- `outputs/plots/cactus/cactus.tex` — per-tool LaTeX macros, **prefixed with the
  suite name** (`\SmtlibRand…`, `\InstcombineSmall…`) so both files can be `\input`
  together. Macros include `NumSolved<Tool>` and `Num{Unsat,Sat,Timeout,Memout,
  Errors,Checked}<Tool>`, `NumDisagreementsWithExpectedStatus<Tool>` and
  `PercentDisagreementsWithExpectedStatus<Tool>` (the unsoundness rate: a definite
  verdict contradicting the oracle `:status`), `GeomeanTime<Tool>`, and pairwise
  `Speedup<A>Over<B>`. `NumSolved` = sat **or** unsat verdicts that do not
  contradict the oracle.

Concretely:

```
runresults/smtlib-rand/outputs/plots/cactus/
runresults/instcombine-small/outputs/plots/cactus/
```

### Latest measured results

Regenerated by the run above (git `6aa707b`, seed 42, per-family cap 4000,
TIMEOUT_SEC 60, MEMOUT_MB 8000, NPROC 14, RUNS 1) on an **AMD Ryzen 9 9950X
16-Core** (32 threads, 123.5 GB, inside the container). `solved` = a definite
verdict (**sat or unsat**) that does not contradict the oracle `:status`; the
`sat`/`unsat` columns split it. `err` = ran but gave no verdict (fplean abstracts
an unsupported subterm, a parse/unsupported-op failure, or a spurious
counterexample that stays `unknown`); `t/o` = hit the 60 s wall limit; `unsound` =
a definite verdict that contradicts the oracle. These are the numbers the
`cactus.tex` macros encode.

**(a) `smtlib-rand`** — 4,412-file stratified sample (sat + unsat, all 8 QF_FP
families), 3 tools:

| tool             | solved | unsat |  sat  | err | t/o | unsound    | geomean |
| ---------------- | -----: | ----: | ----: | --: | --: | ---------- | ------: |
| bitwuzla         |  4,345 | 2,152 | 2,193 |   0 |  67 | 0 (0.00 %) |   54 ms |
| **fplean**       |  4,005 | 1,906 | 2,099 | 172 | 235 | 0 (0.00 %) |  1.83 s |
| fplean-nokernel  |  4,151 | 2,044 | 2,107 | 164 |  97 | 0 (0.00 %) |  1.72 s |

**(b) `instcombine-small`** — all 100 problems (25 each E5M2 / E5M4 / isoslow /
bf16; all `unsat` equivalence checks), 4 tools:

| tool                   | solved | unsat | err | t/o | unsound    | geomean |
| ---------------------- | -----: | ----: | --: | --: | ---------- | ------: |
| bitwuzla               |    100 |   100 |   0 |   0 | 0 (0.00 %) |   25 ms |
| fplean                 |    100 |   100 |   0 |   0 | 0 (0.00 %) |  1.35 s |
| fplean-nokernel        |    100 |   100 |   0 |   0 | 0 (0.00 %) |  1.06 s |
| exhaustive-enumeration |     81 |    81 |   0 |  19 | 0 (0.00 %) |  3.33 s |

Takeaways for the evaluation text:

- **Sound SAT at scale.** `fplean` solves **4,005 / 4,412 (91 %)** of the stratified
  QF_FP sample, of which **2,099 are sound `sat`** solves — landing just behind
  bitwuzla's 4,345 and tracking it closely on *both* sat and unsat. Before the
  countermodel-reconstruction work these sat cases were errors; the feature is what
  makes fp-lean competitive on the sat half of a real-world QF_FP distribution.
- **Zero unsound verdicts** across all 4,512 problems (both suites, every tool):
  every `sat`/`unsat` that fp-lean commits to agrees with the oracle. fp-lean's
  soundness is a *proof* obligation (kernel-checked bvDecide reflection for unsat;
  native-validated witness for sat), not an empirical observation.
- **Cost of the kernel re-check.** `fplean` (kernel on) vs `fplean-nokernel` (kernel
  off) is the price of full verification: ~146 fewer solves (4,005 vs 4,151, from a
  slightly larger timeout tail) and ~6 % higher geomean (1.83 s vs 1.72 s) on
  suite (a). `fplean-nokernel` is reported informationally only (known `fp.fma`
  soundness bug), so the *sound* headline solver is `fplean`.
- **bitwuzla vs fp-lean.** bitwuzla is ~34× faster by geomean (54 ms vs 1.83 s) and
  solves more, but the fp-lean tools are *proof-producing* against a mechanized
  IEEE-754 semantics — a different point on the trust/speed trade-off.
- **Enumeration's wall.** On suite (b), the three SMT tools solve all 100 identities;
  `exhaustive-enumeration` solves 81 and times out on the 19 multi-variable bf16
  (E8M8, 65 536 values/var) cases — the intended demonstration that brute
  enumeration is exponential in the value domain while the SMT tools are not.

## Solvers

Two: `bitwuzla` (external binary) and `fplean` (lean-based). Paths in `bench.py`
(`BITWUZLA_PATH`, `FPLEAN_PATH`). Both are built from source in the Docker image
(see `Dockerfile`).

> **Paper note — Bitwuzla is built with `--fpexp` (experimental FP formats).**
> The benchmark suite is dominated by non-standard floating-point formats (e.g.
> `3_5` minifloats). Bitwuzla only supports `Float16/32/64/128` unless built with
> `./configure.py --fpexp`, which enables *all* formats. Upstream documents these
> experimental formats as "use at your own risk" due to known issues in SymFPU,
> so bitwuzla results on non-standard formats carry that soundness caveat and
> should be reported as such.

## Benchmarks (SMT-LIB floating point)

Benchmarks come from the SMT-LIB 2025 release
([zenodo.org/records/15493090](https://zenodo.org/records/15493090)), grouped by
logic. Two logics are relevant, each shipped as a `datasets/*.tar.zst` tarball
that unpacks to `datasets/non-incremental/<LOGIC>/<family>/<problem>.smt2`:

```
tar --use-compress-program=unzstd -xf datasets/FP.tar.zst          -C datasets/
tar --use-compress-program=unzstd -xf datasets/QF_FP.tar.zst       -C datasets/
tar --use-compress-program=unzstd -xf datasets/instcombine.tar.zst -C datasets/
```

(`instcombine.tar.zst` is a separate, non-SMT-LIB set described at the end.)

A benchmark's expected answer is embedded as `(set-info :status sat|unsat)`, and
`FP` vs `QF_FP` is the quantified vs quantifier-free split. `fplean` bit-blasts
to SAT, so it **cannot handle quantifiers at all**, and in practice it only
solves the **unsat** instances of a handful of operators (on `sat` instances it
abstracts unsupported subterms and returns a spurious counterexample). `bitwuzla`
solves essentially every quantifier-free instance instantly.

### `FP` division — 2,669 problems (mostly quantified)

| family                                 | total | QF  | quantified |
| -------------------------------------- | ----: | --: | ---------: |
| 2019-Preiner                           |  2415 |   0 |       2415 |
| 20200911-Pine                          |   245 | 245 |          0 |
| 20190429-UltimateAutomizerSvcomp2019   |     8 |   0 |          8 |
| 20170501-Heizmann-UltimateAutomizer    |     1 |   0 |          1 |

`20200911-Pine` is the only quantifier-free family, but all 245 are `Float32`
(`FloatingPoint 8 24`) with heavy nonlinear arithmetic (16–24 `fp.mul` each), so
fplean times out on every one. Everything else is quantified. **We effectively
support none of the `FP` division**, so no suite targets it — the harness only
runs `QF_FP` (below). The `FP` division is enumerated here only for context.

### `QF_FP` division — 40,406 problems (all quantifier-free)

| family                                 | total | unsat |  sat |
| -------------------------------------- | ----: | ----: | ---: |
| wintersteiger                          | 39994 | 19997 | 19997 |
| griggio                                |   214 |    66 |   93 |
| 20210211-Vector                        |    91 |     0 |    0 |
| schanda                                |    44 |    25 |   18 |
| ramalho                                |    36 |    21 |    3 |
| 20190429-UltimateAutomizerSvcomp2019   |    24 |     0 |   24 |
| 20170501-Heizmann-UltimateAutomizer    |     2 |     0 |    2 |
| 20230321-UltimateAutomizerSvcomp2023   |     1 |     0 |    0 |

(`0/0` means the family declares no `:status` / `unknown`.) The `wintersteiger`
family — small crafted per-operator testcases, mostly `double` (`11 53`) —
dominates and is where fplean has a chance.

### `wintersteiger` by operator

Each operator directory splits evenly into `has-no-other-solution` (unsat) and
`has-solution` (sat) instances. `supported` marks the operators fplean solves:

| op         | total | unsat |  sat | supported |
| ---------- | ----: | ----: | ---: | :-------: |
| abs        |  2856 |  1428 | 1428 |    yes    |
| add        |  3024 |  1512 | 1512 |    yes    |
| div        |  2792 |  1396 | 1396 |    yes    |
| eq         |  2776 |  1388 | 1388 |    yes    |
| gt         |  2904 |  1452 | 1452 |    yes    |
| lt         |  2848 |  1424 | 1424 |    yes    |
| mul        |  2938 |  1469 | 1469 |    yes    |
| sub        |  2790 |  1395 | 1395 |    yes    |
| fma        |  2864 |  1432 | 1432 |    no     |
| max        |  2854 |  1427 | 1427 |    no     |
| min        |  2852 |  1426 | 1426 |    no     |
| rem        |  2804 |  1402 | 1402 |    no     |
| sqrt       |  2828 |  1414 | 1414 |    no     |
| toIntegral |  2864 |  1432 | 1432 |    no     |

fplean now bit-blasts `fp.min`, `fp.max`, `fp.sqrt`, `fp.roundToIntegral`, and
`fp.fma` (all pass on the FP8 oracle suite, see `run-fptg-oracle-tests.sh`). On
the wide wintersteiger formats it still times out on `fp.rem` and does not always
finish `fp.fma`, so the timing comparison below stays on the eight operators
where both solvers reliably terminate.

### What we run: the `wintersteiger-supported-family` suite

The set fplean has any hope of solving — and where both solvers agree — is the
**unsat** instances of the eight supported operators:

> `wintersteiger` × {`abs`, `add`, `div`, `eq`, `gt`, `lt`, `mul`, `sub`} × unsat
> = **11,464 problems**

That is the `wintersteiger-supported-family` suite
(`--suite wintersteiger-supported-family`), whose supported-operator list lives
directly in `bench.SUITES` — widen it there as fplean gains support. The full
family (every operator, sat and unsat) is `--suite wintersteiger-all-family`.

## InstCombine fp-problems (not SMT-LIB)

`datasets/instcombine.tar.zst` holds **101** QF_FP problems extracted from the
LLVM InstCombine test suite by
[`llvm-fp-bv-smt-extractor`](https://github.com/opencompl/llvm-fp-bv-smt-extractor).
Each encodes an InstCombine peephole as an equivalence check (`(distinct lhs
rhs)`) over `Float32`/`double`; `unsat` means the optimization is sound. They
carry no `(set-info :status)` (all `unknown`) and no `set-logic`, and use a mix
of fp operators (some fplean supports, some it does not).

Run all of them with `--suite instcombine-fp-problems` (or
`./run-instcombine-fp-problems.sh`).
