# Evaluation for fp-lean

One entry point, two subcommands: `./main.py run …` and `./main.py plot …`.
`run.py` and `plot.py` are just the modules holding each subcommand's logic;
shared stuff (solver tables, tool dispatch, dataset walk, sampling) lives in
`benchgod.py`.

## Running benchmarks

```
./main.py run <config-name> [--guid latest] [--nproblems N] [--runs 2]
              [--timeout-sec 600] [--memout-mb 16000] [--nproc 4]
```

Writes one jsonl file per datapoint into `runresults/<guid>/`. Default `--guid`
is `latest`. Existing `runresults/<guid>/` is wiped before a new run.

Each jsonl file contains raw fields only: `stdout`, `stderr`, `returncode`,
`wall_elapsed_ms`, `is_timeout`, `is_memout`, `is_exception`. No derived
fields — those are computed by the plot subcommand.

## Plotting

```
./main.py plot <plot-name> [--guid latest] [--outdir DIR]
```

Reads every jsonl in `runresults/<guid>/`, parses the raw data (computes
`is_success`, `is_unsound`, solver-specific `elapsed_ms`), and writes plots +
`cactus.tex` to `runresults/<guid>/plots/<plot-name>/` (unless `--outdir`).

## Configurations and plots

Defined in `benchgod.py`:

- `CONFIGURATIONS["cactus"]` — both solvers × 2 runs × a deterministically
  sampled subset of `datasets/FP/` (seed = `benchgod.SEED`).
- `PLOTS["cactus"]` — cactus plot, geomean-averaged over runs.

## Solvers

Two: `bitwuzla` (external binary) and `fplean` (lean-based). Paths in
`benchgod.py` (`BITWUZLA_PATH`, `FPLEAN_PATH`).

## Dataset

`datasets/FP.tar.zst` — extract with
`tar --use-compress-program=unzstd -xf datasets/FP.tar.zst -C datasets/`
before running. Expected layout: `datasets/FP/<family>/<problem>.smt2`.
