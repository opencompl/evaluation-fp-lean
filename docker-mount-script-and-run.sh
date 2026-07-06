#!/usr/bin/env bash
# Mount runresults/ into the container and run the given command inside it.
#
# Forwards the harness tuning knobs (GUID, NPROBLEMS, ...) into the container
# when they are set, so `NPROBLEMS=8 ./docker-run-smoke.sh` works end to end.
cd "$(dirname "$0")"

envargs=()
for var in GUID NPROBLEMS SMTLIB_RAND_NPROBLEMS RUNS TIMEOUT_SEC MEMOUT_MB NPROC FILE SUITE TOOLS; do
    if [ -n "${!var:-}" ]; then
        envargs+=(-e "$var=${!var}")
    fi
done

# --init: run a real init (catatonit/tini) as PID 1 so that orphaned grandchildren
#   of timed-out solver invocations (leanwuzla spawns lake -> lean -> cadical; on a
#   wall-timeout the tree is SIGKILLed but the grandchildren reparent to PID 1) get
#   REAPED instead of piling up as zombies. Without it, a long sweep (e.g.
#   run-full-smtlib-*, ~160k invocations with thousands of timeouts) accumulates
#   defunct processes until it hits the pids cgroup limit and every further spawn
#   fails with "Resource temporarily unavailable".
# --pids-limit=0: also lift podman's default 2048 pids cap (host pid_max is millions),
#   belt-and-suspenders so a transient spike can't wedge the run.
podman run --init --pids-limit=0 \
    --mount type=bind,src="$(pwd)/runresults",dst=/workspace/runresults \
    ${envargs[@]+"${envargs[@]}"} -it localhost/fp-lean-eval "$@"
