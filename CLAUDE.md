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
- `run-supported-sample.sh` / `docker-run-supported-sample.sh` — bitwuzla vs
  fp-lean on a deterministic 2000-problem sample (seed 42) of the unsat,
  fplean-supported QF_FP set, with a cactus plot.
- `run-supported-all.sh` / `docker-run-supported-all.sh` — same but the full
  ~11.5k unsat supported set.

All accept env overrides, e.g. `NPROBLEMS=8 RUNS=2 ./run-smoke.sh` or
`TIMEOUT_SEC=900 ./docker-run-all.sh`.

### Suites and filtering (`SUITE` / `STATUS`)

`bench.py` picks a benchmark **suite** from the `SUITE` env var (default `pine`):

- `pine` — the one quantifier-free FP family (hard Float32 nonlinear arithmetic;
  fplean times out). Reproduces the harness's original defaults.
- `supported` — the QF_FP/wintersteiger operations fplean supports, restricted
  to unsat instances (the problems both solvers finish). The
  `run-supported-*.sh` scripts set this.

A suite bundles the dataset dir, the families under it, and a `(set-info
:status ...)` filter. The individual `FP_DATASET_DIR`, `FAMILIES`, and `STATUS`
env vars still override the suite's values. **To extend which ops count as
supported, edit the single `SUPPORTED_OPS` list in `bench.py`** — the scripts
and suites derive from it.

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
