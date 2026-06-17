# CLAUDE.md

Guidance for working in this repo (the FP-Lean SMT evaluation harness).

## Always run inside the container with podman

Do **not** run the evaluation directly on the host. Always run inside the
Docker image using **podman**, via `docker-mount-script-and-run.sh`, which
bind-mounts `runresults/` so output lands back on the host:

```bash
./docker-mount-script-and-run.sh <command...>
```

The image (`localhost/practical-misplace-monarch`) is built from `Dockerfile`
and ships the extracted dataset plus the built `leanwuzla` binary. Rebuild the
image whenever `Dockerfile`, the dataset, or the Leanwuzla pin changes.

## Run scripts

- `./run-smoke.sh` — small sample run (defaults: 4 problems, 1 run, 60s timeout)
  for a quick sanity check. Assumes the dataset is already extracted (it is, in
  the image).
- `./run-all.sh` — full run over every problem in the dataset.

Both wrap `docker-mount-script-and-run.sh` and accept env overrides, e.g.
`NPROBLEMS=8 RUNS=2 ./run-smoke.sh` or `TIMEOUT_SEC=900 ./run-all.sh`.

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
