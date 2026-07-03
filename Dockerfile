# Base image
FROM ubuntu:24.04

# Install tools (e.g., Python, build-essential, sed, etc.)
RUN apt-get update && \
    apt-get install -y curl wget build-essential clang cmake curl git python3 python3-pip unzip git gettext fish

# Install uv (assuming it's Python-based, via pip)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install elan (Lean version manager)
RUN curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- -y

# Make elan available in all shells
ENV PATH="/root/.elan/bin:${PATH}"

# Make elan available in all shells
ENV PATH="/root/.local/bin:${PATH}"

# Set working directory
WORKDIR /workspace

# The project requires Python >=3.13, but ubuntu:24.04 ships 3.12. Let uv
# fetch a managed 3.13 interpreter and build the venv from it.
RUN uv venv --python 3.13 /docker-venv
ENV UV_PYTHON=/docker-venv/bin/python

# prevents CI from complaining about shared directories
# fatal: detected dubious ownership in repository at '/workspace'
# To add an exception for this directory, call: git config --global --add safe.directory /workspace
RUN git config --global --add safe.directory /workspace
# RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s  -- --default-toolchain nightly -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN apt install zsh -y
RUN apt install zstd -y
# RUN apt install fish -y
RUN apt install vim -y
RUN apt install zip unzip -y

# Bitwuzla build dependencies. Noble's GMP (6.3.0) and MPFR (4.2.1) satisfy
# bitwuzla's >=6.3 / >=4.2.1 requirements; CaDiCaL and SymFPU are fetched by
# configure.py automatically.
RUN apt-get install -y libgmp-dev libmpfr-dev meson ninja-build pkg-config

# Install the harness's Python deps. Copy only the files uv needs (not the
# harness code) so that editing the code later does not invalidate this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv run echo "setup deps"

# Build Leanwuzla (the SMT-solver CLI the harness drives as the `fplean` tool).
# It pulls fp-lean in as a Lake dependency, so no separate fp-lean checkout is needed.
COPY leanwuzla/ leanwuzla/
RUN cd leanwuzla && git clean -xf .
RUN cd leanwuzla && git checkout 
RUN cd leanwuzla && lake build

# Build Bitwuzla (the `bitwuzla` baseline tool) from source at a pinned commit.
# bench.BITWUZLA_PATH expects the binary at /bitwuzla/build/src/main/bitwuzla.
# Built after Leanwuzla so a bitwuzla bump does not bust the Lean build cache.
# --fpexp enables the non-standard FP formats (e.g. 3_5 minifloats) that make up
# most of this dataset; without it bitwuzla rejects them as unsupported.
RUN git clone https://github.com/bitwuzla/bitwuzla.git /bitwuzla && \
    cd /bitwuzla && \
    git checkout c32bd4be7a7f93529e1d3e0d9f508ae5e4c44037 && \
    ./configure.py --fpexp && \
    cd build && ninja

# Copy the harness code last: edits here are cheap and do not bust the expensive
# bitwuzla / Leanwuzla build layers above.
COPY *.py ./
COPY *.sh ./
COPY *.md ./
COPY pyproject.toml ./
COPY uv.lock ./
COPY makefile ./
COPY .git/ ./

# Copy and extract benchmarks last: this is the largest layer, so keeping it at
# the end maximizes cache reuse for the earlier build steps.
COPY datasets/*.tar.zst datasets/
RUN for f in datasets/*.tar.zst; do \
        tar --use-compress-program=unzstd -xf "$f" -C datasets/; \
    done

# The fptg-testsuite (a submodule locally) ships as a tarball whose internal
# paths are repo-root-relative (fptg-testsuite/QF_FP/tests_validated/...), so it
# is extracted to the workdir root -- matching the fptg-* suites' dataset_dir.
# Its define-const commands have been rewritten to define-fun so bitwuzla parses
# them. Kept out of datasets/ so the loop above does not mis-extract it.
COPY fptg-testsuite.tar.zst ./
RUN tar --use-compress-program=unzstd -xf fptg-testsuite.tar.zst -C .

CMD /usr/bin/fish

