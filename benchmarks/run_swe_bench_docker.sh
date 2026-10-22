#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE_NAME="agentfixer-swebench:latest"

echo "=== AgentFixer SWE-bench Docker Benchmark Runner ==="

# Check if Docker daemon is accessible
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "[Docker Mode] Building benchmark image '${IMAGE_NAME}'..."
    docker build -t "${IMAGE_NAME}" -f "${SCRIPT_DIR}/Dockerfile" "${REPO_ROOT}"

    echo "[Docker Mode] Running benchmark container with volume mount..."
    docker run --rm \
        -v "${REPO_ROOT}/benchmarks:/workspace/benchmarks" \
        "${IMAGE_NAME}"
    echo "[Docker Mode] Benchmark complete. Results written to ${REPO_ROOT}/benchmarks/swe_bench_results.tsv"
else
    echo "[Host Fallback Mode] Docker daemon unavailable. Executing benchmarks locally via Python..."
    python3 "${SCRIPT_DIR}/run_swe_bench.py"
    echo "[Host Fallback Mode] Benchmark complete. Results written to ${REPO_ROOT}/benchmarks/swe_bench_results.tsv"
fi
