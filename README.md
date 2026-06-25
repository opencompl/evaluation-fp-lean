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

- `cactus` — both solvers × `--runs` × a deterministically sampled subset of
  `datasets/non-incremental/FP/` (seed = `bench.SEED`). Produces a cactus plot,
  geomean-averaged over runs.
- `debug` — both solvers against a single user-specified file (`--file PATH`),
  for quickly checking one problem. Defaults to `--runs 1` and `--guid debug`.

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

## Dataset

`datasets/FP.tar.zst` — extract with

```
tar --use-compress-program=unzstd -xf datasets/FP.tar.zst -C datasets/
```

The tarball unpacks to `datasets/non-incremental/FP/<family>/<problem>.smt2`,
which is what `bench.FP_DATASET_DIR` points at.
