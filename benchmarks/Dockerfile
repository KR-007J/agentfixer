FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and source tree to install agentfixer
COPY pyproject.toml /workspace/
COPY src/ /workspace/src/
COPY benchmarks/ /workspace/benchmarks/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pytest -e /workspace

ENTRYPOINT ["python3", "/workspace/benchmarks/run_swe_bench.py"]
