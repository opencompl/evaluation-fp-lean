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

Writes one jsonl file per datapoint into `runresults/<guid>/`. Default `--guid`
is `latest`. An existing `runresults/<guid>/` is wiped before a new run.

Each jsonl record contains raw fields only: `stdout`, `stderr`, `returncode`,
`wall_elapsed_ms`, `is_timeout`, `is_memout`, `is_exception`. No derived fields —
those are computed at plot time.

Alongside the records, `--run` also writes `manifest.json` (run parameters, git
hash, timestamp) and `config.tex` / `triple.tex` (LaTeX macros for the paper).

## Plotting

```
./cli.py <plot-name> --plot [--guid latest] [--outdir DIR]
```

Reads every jsonl in `runresults/<guid>/`, parses the raw data (computes
`is_unsat`, `is_sat`, and the solver-specific `elapsed_ms`), and writes the plot
plus `cactus.tex` to `runresults/<guid>/plots/<plot-name>/` (unless `--outdir`).

`--run` and `--plot` may be combined to do both in one invocation.

## Configurations and plots

Defined in `cli.py`:

- `cactus` — both solvers × `--runs` × a deterministically sampled subset of
  `datasets/FP/` (seed = `bench.SEED`). Produces a cactus plot, geomean-averaged
  over runs.

## Solvers

Two: `bitwuzla` (external binary) and `fplean` (lean-based). Paths in `bench.py`
(`BITWUZLA_PATH`, `FPLEAN_PATH`).

## Dataset

`datasets/FP.tar.zst` — extract with

```
tar --use-compress-program=unzstd -xf datasets/FP.tar.zst -C datasets/
```

before running. Expected layout: `datasets/FP/<family>/<problem>.smt2`.
