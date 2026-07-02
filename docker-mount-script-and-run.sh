#!/usr/bin/env bash
# Mount runresults/ into the container and run the given command inside it.
#
# Forwards the harness tuning knobs (GUID, NPROBLEMS, ...) into the container
# when they are set, so `NPROBLEMS=8 ./docker-run-smoke.sh` works end to end.
cd "$(dirname "$0")"

envargs=()
for var in GUID NPROBLEMS RUNS TIMEOUT_SEC MEMOUT_MB NPROC FILE \
           SUITE STATUS FP_DATASET_DIR FAMILIES; do
    if [ -n "${!var:-}" ]; then
        envargs+=(-e "$var=${!var}")
    fi
done

podman run --mount type=bind,src="$(pwd)/runresults",dst=/workspace/runresults \
    ${envargs[@]+"${envargs[@]}"} -it localhost/fp-lean-eval "$@"
