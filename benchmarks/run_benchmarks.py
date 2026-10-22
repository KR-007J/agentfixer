"""Autoresearch Benchmark Harness for AgentFixer.

Following Andrej Karpathy's autoresearch methodology:
- Strict quantitative evaluation metrics (token reduction %, latency overhead ms, false-pass interception %)
- Commit hash tracking
- Append-only structured results logging (results.tsv)
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from agentfixer.tokensieve import TokenSieve
from agentfixer.sentinel import FalsePassSentinel


def get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def benchmark_token_reduction() -> tuple[float, float]:
    """Benchmark token compression on simulated 200-test pass."""
    raw_suite = (
        "platform linux -- Python 3.11.15, pytest-8.4.1\n"
        + "".join([f"tests/test_feature_{i}.py .... [ 100%]\n" for i in range(1, 201)])
        + "========================= 200 passed in 0.94s =========================\n"
    )

    t0 = time.perf_counter()
    res = TokenSieve.sieve(stdout=raw_suite, exit_code=0, command="pytest")
    t1 = time.perf_counter()

    latency_ms = (t1 - t0) * 1000.0
    return res["reduction_pct"], latency_ms


def benchmark_false_pass_detection() -> float:
    """Verify sentinel catches 100% of zero-test conditions."""
    scenarios = [
        ("collected 0 items\nno tests ran", 0, "pytest"),
        ("No tests found, exiting with code 0", 0, "npm test"),
        ("running 0 tests\ntest result: ok. 0 passed", 0, "cargo test"),
        ("", 0, "pytest"),
    ]
    caught = 0
    for stdout, exit_code, cmd in scenarios:
        res = FalsePassSentinel.inspect(stdout=stdout, exit_code=exit_code, command=cmd)
        if res.is_false_pass and res.effective_exit_code == 101:
            caught += 1
    return (caught / len(scenarios)) * 100.0


def main():
    bench_dir = Path(__file__).parent
    tsv_file = bench_dir / "results.tsv"

    if not tsv_file.exists():
        tsv_file.write_text("commit\ttoken_reduction_pct\tlatency_ms\tfalse_pass_accuracy\tstatus\tdescription\n")

    commit = get_git_commit()
    reduction_pct, latency_ms = benchmark_token_reduction()
    accuracy_pct = benchmark_false_pass_detection()

    status = "KEEP" if reduction_pct >= 90.0 and latency_ms < 15.0 and accuracy_pct == 100.0 else "DISCARD"
    desc = f"Verified baseline: {reduction_pct}% reduction in {latency_ms:.2f}ms with {accuracy_pct}% false-pass interception"

    row = f"{commit}\t{reduction_pct:.1f}%\t{latency_ms:.2f}ms\t{accuracy_pct:.1f}%\t{status}\t{desc}\n"
    with open(tsv_file, "a") as f:
        f.write(row)

    print("=" * 65)
    print("🔬 AUTORESEARCH BENCHMARK RUN COMPLETE")
    print("=" * 65)
    print(f"Commit:              {commit}")
    print(f"Token Reduction:     {reduction_pct:.1f}% (Target: >=90%)")
    print(f"Execution Latency:   {latency_ms:.2f} ms (Target: <15ms)")
    print(f"False-Pass Accuracy: {accuracy_pct:.1f}% (Target: 100%)")
    print(f"Decision Status:     {status}")
    print(f"Logged to:           {tsv_file}")
    print("=" * 65)


if __name__ == "__main__":
    main()
