# Base image
FROM ubuntu:24.04

# Install tools (e.g., Python, build-essential, sed, etc.)
RUN apt-get update && \
    apt-get install -y curl wget build-essential clang cmake curl git python3 python3-pip unzip git gettext

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

RUN uv venv /docker-venv
ENV UV_PYTHON=/docker-venv/bin/python

# prevents CI from complaining about shared directories
# fatal: detected dubious ownership in repository at '/workspace'
# To add an exception for this directory, call: git config --global --add safe.directory /workspace
RUN git config --global --add safe.directory /workspace
# RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s  -- --default-toolchain nightly -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN apt install zsh -y
RUN apt install zstd -y
RUN apt install fish -y
RUN apt install vim -y
RUN apt install zip unzip -y

COPY pyproject.toml uv.lock README.md *.py .
COPY datasets/ datasets/
RUN uv run echo "setup deps"


# RUN rm -rf /var/lib/apt/lists/*
# Build Leanwuzla (the SMT-solver CLI the harness drives as the `fplean` tool).
# It pulls fp-lean in as a Lake dependency, so no separate fp-lean checkout is needed.
RUN git clone https://github.com/opencompl/Leanwuzla.git && \
    cd Leanwuzla && git checkout 908b037964d9e51020f65ef8a70a909c717ba5ae
RUN cd Leanwuzla && lake build

# Copy and extract benchmarks last: this is the largest layer, so keeping it at
# the end maximizes cache reuse for the earlier build steps.
COPY datasets/*.tar.zst datasets/
RUN for f in datasets/*.tar.zst; do \
        tar --use-compress-program=unzstd -xf "$f" -C datasets/; \
    done

CMD /usr/bin/fish

