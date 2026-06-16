# Makefile for the fp-lean evaluation harness.
#
# Common knobs can be overridden on the command line, e.g.
#   make run NPROBLEMS=50 RUNS=3 GUID=myrun

CLI         := ./cli.py
CONFIG      := cactus
GUID        := latest
NPROBLEMS   :=
RUNS        := 2
TIMEOUT_SEC := 600
MEMOUT_MB   := 16000
NPROC       := 4

DATASET_DIR     := datasets
DATASET_TARBALL := $(DATASET_DIR)/FP.tar.zst
DATASET_OUT     := $(DATASET_DIR)/FP

DOCKER_IMAGE := fp-lean-eval

# Assemble the optional --nproblems flag only when NPROBLEMS is set.
NPROBLEMS_FLAG := $(if $(NPROBLEMS),--nproblems $(NPROBLEMS),)

RUN_FLAGS := --guid $(GUID) $(NPROBLEMS_FLAG) --runs $(RUNS) \
             --timeout-sec $(TIMEOUT_SEC) --memout-mb $(MEMOUT_MB) --nproc $(NPROC)

.PHONY: help dataset run plot all docker-build clean

plot: ## Plot results for an existing run (override GUID=…)
	$(CLI) $(CONFIG) --plot --guid $(GUID)

$(DATASET_OUT): $(DATASET_TARBALL)
	tar --use-compress-program=unzstd -xf $(DATASET_TARBALL) -C $(DATASET_DIR)

dataset: $(DATASET_OUT) ## Extract the benchmark dataset (datasets/FP/)

run: dataset ## Run the benchmark configuration (override CONFIG=…)
	$(CLI) $(CONFIG) --run $(RUN_FLAGS)


all: dataset ## Run and plot in one invocation
	$(CLI) $(CONFIG) --run --plot $(RUN_FLAGS)

docker-build: ## Build the Docker image
	docker build -t $(DOCKER_IMAGE) .

clean: ## Remove run outputs
	rm -rf runresults/*
