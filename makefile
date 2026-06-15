.PHONY: run-on-host podman run cleanplot cleandata lint camera-ready plot-camera-ready

camera-ready: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./run-camera-ready.sh'

plot-camera-ready: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./plot-camera-ready.sh'

paper-plots: podman make-alive make-sextzext make-rover make-everybench

run-all: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./run-all.sh'

plot-all: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./plot-all.sh'

make-everybench: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-everybench.sh'

make-bmc-delta: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-bmc.sh && cd debug && ./compare-bmc-mono-and-naive.sh'

make-kick-the-tires: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-kick-the-tires.sh'

make-hero: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-hero.sh'

make-naivebmc-all: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-naivebmc-all.sh'

make-dry-run: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-dry-run.sh'

shell: podman
	./docker-mount-script-and-run.sh fish

make-test-timeout-memout:
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-test-timeout-memout.sh'

make-sextzext: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-sextzext.sh'

make-alive: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-alive.sh'

make-rover: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./make-rover.sh'

plot-alive: podman
	./docker-mount-script-and-run.sh fish -c 'cd scripts && ./plot-alive.sh'

podman:
	podman build . -t practical-misplace-monarch


