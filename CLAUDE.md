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

- `fplean` is the **Leanwuzla** CLI (`Leanwuzla/.lake/build/bin/leanwuzla`),
  invoked as `lake env leanwuzla --timeout <wall-limit> <problem.smt2>` from the
  Leanwuzla project root. (It replaced the old Blase `blasewuzla` backend.)
- `bitwuzla` is the upstream solver baseline (`BITWUZLA_PATH`).
