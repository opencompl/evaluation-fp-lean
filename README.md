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
| `RUNS`               |        1 | timing runs per (tool, problem); geomean-averaged if >1        |
| `TIMEOUT_SEC`        |       60 | wall-clock limit per solve (also passed to leanwuzla `--timeout`) |
| `MEMOUT_MB`          |     8000 | per-solve memory limit (8 GB); an active watchdog kills on breach |
| `NPROC`              |        6 | problems solved in parallel (harness process pool)             |
| `SEED` (`bench.SEED`)|       42 | the SMT-LIB / SMT-COMP sampling seed (fixes suite (a)'s sample) |

The two suites, run back to back:

**(a) `wintersteiger-supported-family`** — `--guid
wintersteiger-supported-family-sample`, `--nproblems 2000` (`NPROBLEMS`, the
default). A deterministic **2000-problem sample (seed 42)** of the **11,464**
unsat, fplean-supported QF_FP `wintersteiger` problems (the 8 operators `abs`,
`add`, `div`, `eq`, `gt`, `lt`, `mul`, `sub`, unsat instances — see **Benchmarks**).
Tools: **bitwuzla, fplean, fplean-nokernel** (3 tools × 2000 = 6000 datapoints).

**(b) `instcombine-small`** — `--guid instcombine-small`, **all 50 problems**
(this suite ignores `NPROBLEMS`): the 25 constant-free, width-parametric LLVM
InstCombine identities reparametrized to two tiny minifloat widths, **E5M2**
(`FloatingPoint 5 3`, 256 values/var) and **E5M4** (`FloatingPoint 5 5`, 1024
values/var), 25 each. Each is an `unsat` equivalence check (`:status unsat`), so
they double as a **soundness** test. Tools: **bitwuzla, fplean, fplean-nokernel,
exhaustive-enumeration** (4 tools × 50 = 200 datapoints); this is the only paper
suite where `exhaustive-enumeration` runs, since ≤2 free FP variables make brute
enumeration feasible (3-variable E5M4 cases time out).

### How each tool is invoked

- **bitwuzla** — `bitwuzla <problem.smt2>` (image build uses `./configure.py
  --fpexp`, required to parse the E5M2/E5M4 minifloats and other non-standard
  formats).
- **fplean** — `lake env leanwuzla --timeout <TIMEOUT_SEC> --maxHeartbeats
  9999999 <problem.smt2>`, from the `leanwuzla` project root. Bit-blasts to SAT
  via `bv_decide` and re-checks the reflection proof in the Lean kernel.
- **fplean-nokernel** — same, plus `--disableKernel`: only the LRAT certificate
  is verified, skipping the kernel re-check (`decideSmtNoKernel`).
- **exhaustive-enumeration** — same, plus `--exhaustive-enumeration`: decides the
  goal by native-evaluating a `Decidable` instance over *all* FP values instead
  of `bv_decide` (only feasible for tiny bit-widths).

### Outputs

Each suite writes to `runresults/<guid>/`:

- `data/*.jsonl` — one raw record per (tool, run, problem); `data/manifest.json`
  records the run parameters, git hash, and timestamp.
- `outputs/config.tex`, `outputs/triple.tex` — LaTeX macros for the config knobs
  and the machine specs.
- `outputs/plots/cactus/cactus.{pdf,png}` — the cactus plot (cumulative solve
  time vs. # problems solved, log-x).
- `outputs/plots/cactus/cactus.tex` — per-tool LaTeX macros, **prefixed with the
  suite name** (`\WintersteigerSupportedFamily…`, `\InstcombineSmall…`) so both
  files can be `\input` together. Macros include `Num{Unsat,Sat,Timeout,Memout,
  Errors,Checked}<Tool>`, `NumDisagreementsWithExpectedStatus<Tool>` and
  `PercentDisagreementsWithExpectedStatus<Tool>` (the unsoundness rate: a definite
  verdict contradicting the oracle `:status`), `GeomeanTime<Tool>`, and pairwise
  `Speedup<A>Over<B>`.

Concretely:

```
runresults/wintersteiger-supported-family-sample/outputs/plots/cactus/
runresults/instcombine-small/outputs/plots/cactus/
```

### Latest measured results

Regenerated by the run above (git `f973a7a`, seed 42, TIMEOUT_SEC 60, MEMOUT_MB
8000, NPROC 6, RUNS 1) on an **AMD Ryzen 9 9950X 16-Core** (32 threads, 123.5 GB,
inside the container). `unsat` = solved (all these problems are unsat);
`err` = ran but gave no verdict (fplean abstracts an unsupported subterm, or
enumeration is infeasible); `t/o` = hit the 60 s wall limit; `unsound` = a
definite verdict that contradicts the oracle `:status`. These are the numbers
the `cactus.tex` macros encode.

**(a) `wintersteiger-supported-family`** — 2000-problem sample, 3 tools:

| tool             | unsat | err | t/o | unsound     | geomean |
| ---------------- | ----: | --: | --: | ----------- | ------: |
| bitwuzla         |  2000 |   0 |   0 | 0 (0.00 %)  |    58 ms |
| fplean           |  1999 |   1 |   0 | 0 (0.00 %)  |   1.38 s |
| fplean-nokernel  |  1999 |   0 |   0 | **1 (0.05 %)** |   1.08 s |

**(b) `instcombine-small`** — all 50 problems (25 E5M2 + 25 E5M4), 4 tools:

| tool                   | unsat | err | t/o | unsound    | geomean |
| ---------------------- | ----: | --: | --: | ---------- | ------: |
| bitwuzla               |    50 |   0 |   0 | 0 (0.00 %) |    57 ms |
| fplean                 |    44 |   6 |   0 | 0 (0.00 %) |   1.00 s |
| fplean-nokernel        |    46 |   4 |   0 | 0 (0.00 %) |   822 ms |
| exhaustive-enumeration |    44 |   4 |   2 | 0 (0.00 %) |   2.13 s |

bitwuzla is ~18–38× faster (geomean) but the fp-lean tools are *proof-producing*.
`fplean` solves fewer than `fplean-nokernel` on the instcombine identities only
because more of its abstracted-counterexample cases surface as errors rather than
as (unsound) answers.

**Soundness finding — the kernel re-check catches a real unsound answer.** On the
one wintersteiger problem `div/div-has-no-other-solution-10409.smt2`, the
no-kernel path emits an unsound `sat` (deterministically), whereas the
kernel-checked `fplean` *detects the counterexample is spurious* — it abstracted
unsupported significand/exponent subterms — and safely errors out instead. This
is the sole disagreement in the whole run and is the concrete cost of
`--disableKernel`: 1/2000 unsound here (`\WintersteigerSupportedFamilyPercent
DisagreementsWithExpectedStatusFpleannokernel` = 0.05). Every other tool/suite is
0.00 % unsound.

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

fplean does **not** support `fp.min`, `fp.max`, `fp.sqrt`, `fp.roundToIntegral`
(explicit "not supported, yet"), times out on `fp.rem`, and does not finish
`fp.fma`.

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
