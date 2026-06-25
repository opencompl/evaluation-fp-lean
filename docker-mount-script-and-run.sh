#!/usr/bin/env bash
# Shell script to mount the scripts directory and run the results.

podman run --mount type=bind,src="$(pwd)/runresults",dst=/workspace/runresults  -it localhost/fp-lean-eval "$@"

