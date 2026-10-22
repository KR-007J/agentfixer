# AgentFixer Opaque-Box E2E Testing Infrastructure (`TEST_INFRA.md`)

## 1. Testing Philosophy & Guiding Principles

AgentFixer is an autonomous execution shield designed to protect AI coding agents from context window exhaustion, action hallucinations, and silent false passes. Testing AgentFixer requires an **opaque-box methodology** that treats the runtime shield as a black box and verifies observable behavior against public contracts and ground-truth invariants.

### 1.1 Core Principles

1. **Opaque-Box Boundary Integrity**:
   Tests must interact exclusively with public APIs and execution entry points:
   - CLI commands: `agentfix run -- <cmd>`, `agentfix demo`, `agentfix audit`, `agentfixer run -- <cmd>`, `python -m agentfixer`.
   - Core API interfaces: `TokenSieve.sieve()`, `FalsePassSentinel.inspect()`, `ScopeLock.verify()`, `PatchFuse.apply()`.
   - Standalone evaluation harnesses: `benchmarks/run_swe_bench_docker.sh`, `benchmarks/run_swe_bench.py`.
   - CI/CD integration manifests: `.pre-commit-hooks.yaml`, `action.yml`, `pyproject.toml`.
   Tests must never inspect or rely on private helper methods or mutable internal state.

2. **Ground-Truth Invariants**:
   - **Log Compression Invariant**: Passing test logs for supported adapters (Maven, Gradle, CTest, Cargo Nextest, Pytest, Jest, Cargo, Go) must achieve **$\ge 90\%$ token reduction** while retaining essential summary metrics.
   - **False-Pass Interception Invariant**: Any test command that exits with status code 0 but runs or collects 0 tests must be deterministically overridden to **exit code 101** with an unmistakable diagnostic alert.
   - **Frame Isolation Invariant**: Failing test outputs must isolate failing assertion frames with exact `file:line` accuracy and suppress surrounding passing test chatter and build tool boilerplates.
   - **SWE-bench Aggregate Invariant**: Across 20 canonical SWE-bench Lite task instances, the evaluation harness must empirically demonstrate **$\ge 85.0\%$ token reduction** and log 13 structured metric columns to `benchmarks/swe_bench_results.tsv`.
   - **Zero-Runtime-Dependency Invariant**: Core engines and CI manifests must rely strictly on standard library tooling, ensuring sub-second execution without external network calls.

3. **Progressive Testability & Isolation**:
   Every test case is self-contained, idempotent, and isolated. Tests create temporary files in isolated sandboxes (`tmp_path`) and clean up all state automatically.

---

## 2. The 4-Tier Testing Architecture

The test suite in `tests/test_e2e_expansion.py` is structured into four distinct, rigorous tiers:

```
┌────────────────────────────────────────────────────────────────────────┐
│               Tier 4: Real-World Application Scenarios                 │
│    (Polyglot Agent Loop, C++ Refactoring, Zero-Test Trap Prevention,   │
│         SWE-bench Eval Lifecycle, CI/CD Developer Workflows)           │
├────────────────────────────────────────────────────────────────────────┤
│             Tier 3: Cross-Feature Combinations (Pairwise)              │
│    (Sieve + Sentinel, ScopeLock + CLI + Sieve, Docker Fallback + TSV,  │
│             Pre-commit Hook Definitions + Action Invocation)           │
├────────────────────────────────────────────────────────────────────────┤
│                Tier 2: Boundary & Corner Cases                         │
│    (Empty Outputs, 10,000-Line Floods, Corrupted ANSI, Partial Stderr, │
│            Deep Nested Paths, Ignored vs Zero Tests, CLI Flags)        │
├────────────────────────────────────────────────────────────────────────┤
│                   Tier 1: Feature Coverage (>=5/feature)               │
│    (R1: Maven, Gradle, CTest, Nextest; R2: SWE-bench; R3: CI Hooks)   │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Tier 1: Feature Coverage ($\ge 5$ tests per feature)
Verifies the primary behavior (happy path) for every requirement:
- **Maven Adapter**: Passing log compression ($\ge 90\%$), failure frame isolation, zero-test interception (`Tests run: 0` $\to$ 101), ANSI escape removal, build noise suppression.
- **Gradle Adapter**: Passing log compression ($\ge 90\%$), assertion failure extraction, zero-test interception (`:test NO-SOURCE` / `0 tests completed` $\to$ 101), progress carriage return (`\r`) normalization, task summary preservation.
- **CTest Adapter**: Passing log compression ($\ge 90\%$), GoogleTest/CTest failure isolation with exact `file:line` coordinates, zero-test interception (`0% tests passed, 0 tests failed out of 0` $\to$ 101), multi-suite test coordination.
- **Cargo Nextest Adapter**: Passing log compression ($\ge 90\%$), panic backtrace isolation (`file:line:col`), zero-test interception (`0 tests run: 0 passed` $\to$ 101), table formatting extraction.
- **SWE-bench Harness**: Task dataset validation (20 tasks across 8 repositories), TSV schema and header validation (13 columns), aggregate token reduction ($\ge 85.0\%$), Dockerfile offline build semantics, Docker runner script existence.
- **CI/CD Integrations**: Pre-commit hook definitions (`agentfix-audit`, `agentfix-scopelock`, `agentfix-pytest`, `agentfix-run`), GitHub Action composite action (`action.yml`), dual CLI scripts (`agentfix` and `agentfixer`), module entry point `__main__.py`.

### 2.2 Tier 2: Boundary & Corner Cases ($\ge 5$ tests per feature)
Stresses the system against malformed, extreme, and unexpected inputs:
- Zero-length and whitespace-only stdout/stderr across all runners.
- Massive outputs: 10,000+ line logs to verify linear memory usage and sub-second performance.
- Corrupted ANSI escapes, unclosed bracket sequences, and mixed control characters.
- Runner failures that already exit non-zero with 0 tests run (verifying sentinel does not mask non-zero exits).
- Deeply nested relative and absolute file paths in CTest/Nextest error frames.
- Suites with all tests skipped/ignored versus suites with truly 0 tests.
- CLI execution with missing commands, empty strings, and conflicting flag combinations (`--no-sieve`, `--no-sentinel`, `--quiet`).

### 2.3 Tier 3: Cross-Feature Combinations (Pairwise Interactions)
Validates interactions between subsystems:
- `TokenSieve` + `FalsePassSentinel` synchronized handling of zero-test outputs.
- `ScopeLock` + `TokenSieve` + `Sentinel` combined in `agentfix run` CLI execution.
- Benchmark runner invoking `TokenSieve` and `Sentinel` across both pass and fail task cohorts.
- Pre-commit hooks invoking CLI with `--strict-scope` and `--quiet`.
- GitHub Action composite inputs driving dual CLI execution.

### 2.4 Tier 4: Real-World Application Scenarios (Multi-Step Workflows)
Emulates end-to-end autonomous agent lifecycles:
1. **Multi-Language Polyglot Pipeline**: Agent runs failing Maven build, receives isolated failure frame, applies surgical patch, reruns Maven to a compressed pass.
2. **C++ CTest Refactoring Loop**: GoogleTest assertion fails at `src/calc.cpp:42`, agent consumes isolated `file:line` frame, fixes logic, reruns CTest to $100\%$ pass.
3. **Agent Zero-Test Trap Prevention**: Agent invokes a misconfigured test pattern (`mvn test -Dtest=GhostTest`), Sentinel overrides exit 0 to 101, stopping false victory hallucination.
4. **SWE-bench Benchmark Lifecycle**: Runner executes 20 tasks, generates TSV, asserts $\ge 85\%$ token reduction, and verifies zero network requests.
5. **CI/CD Developer Pre-commit to GitHub Actions**: Audit workspace clutter, run pre-commit hooks, verify repository cleanliness.

---

## 3. Feature Inventory & Coverage Matrix

| Feature ID | Feature Name | Requirement | Primary Test Class / Methods | Test Tier | Invariant & Acceptance Threshold |
|:---:|:---|:---:|:---|:---:|:---|
| **F01** | Maven Adapter Compression | R1 | `TestTier1FeatureCoverage::test_maven_pass_compression` | Tier 1 | Reduction $\ge 90\%$, retains summary & duration |
| **F02** | Maven Zero-Test Interception | R1 | `TestTier1FeatureCoverage::test_maven_zero_test_interception` | Tier 1 | Exit code $0 \to 101$, diagnostic alert |
| **F03** | Gradle Adapter Compression | R1 | `TestTier1FeatureCoverage::test_gradle_pass_compression` | Tier 1 | Reduction $\ge 90\%$, retains `BUILD SUCCESSFUL` |
| **F04** | Gradle Zero-Test Interception | R1 | `TestTier1FeatureCoverage::test_gradle_zero_test_interception` | Tier 1 | `NO-SOURCE` / `0 completed` $\to$ exit 101 |
| **F05** | CTest Failure Frame Isolation | R1 | `TestTier1FeatureCoverage::test_ctest_failure_frame_isolation` | Tier 1 | Pinpoint `file:line` coordinate extracted |
| **F06** | CTest Pass & Zero-Test Handling | R1 | `TestTier1FeatureCoverage::test_ctest_pass_compression`, `test_ctest_zero_test_interception` | Tier 1 | Reduction $\ge 90\%$, `0 tests` $\to$ exit 101 |
| **F07** | Rust Cargo Nextest Adapter | R1 | `TestTier1FeatureCoverage::test_cargo_nextest_pass_compression`, `test_cargo_nextest_failure_isolation`, `test_cargo_nextest_zero_test_interception` | Tier 1 | Suppresses passes, isolates panic frame, exit 101 on 0 |
| **F08** | ANSI & Progress Bar Stripping | R1 | `TestTier1FeatureCoverage::test_ansi_and_progress_stripping_all_runners` | Tier 1 | Strips CSI/SGR codes and `\r` carriage returns |
| **F09** | SWE-bench 20-Task Catalog | R2 | `TestTier1FeatureCoverage::test_swe_bench_dataset_catalog_completeness` | Tier 1 | Exactly 20 real instances across 8 repos |
| **F10** | SWE-bench Dockerfile | R2 | `TestTier1FeatureCoverage::test_swe_bench_dockerfile_specification` | Tier 1 | `python:3.11-slim`, zero external runtime deps |
| **F11** | SWE-bench Docker Runner Script | R2 | `TestTier1FeatureCoverage::test_swe_bench_docker_runner_script_execution` | Tier 1 | Volume mount + host fallback logic present |
| **F12** | SWE-bench TSV Generation | R2 | `TestTier1FeatureCoverage::test_swe_bench_tsv_generation_and_schema` | Tier 1 | 13 columns + `TOTAL_SUMMARY` row |
| **F13** | SWE-bench $\ge 85\%$ Token Reduction | R2 | `TestTier1FeatureCoverage::test_swe_bench_token_reduction_invariant` | Tier 1 | Empirical aggregate reduction $\ge 85.0\%$ |
| **F14** | Native Pre-Commit Hooks | R3 | `TestTier1FeatureCoverage::test_pre_commit_hooks_manifest_validation` | Tier 1 | Valid YAML, ids: audit, scopelock, pytest, run |
| **F15** | 1-Line GitHub Action | R3 | `TestTier1FeatureCoverage::test_github_action_composite_manifest_validation` | Tier 1 | `runs.using: composite`, default `pytest` |
| **F16** | Dual CLI Console Scripts | R3 | `TestTier1FeatureCoverage::test_dual_cli_scripts_and_module_entrypoint` | Tier 1 | `agentfix`, `agentfixer`, and `__main__.py` |
| **F17** | Adapter Boundary Conditions | R1 | `TestTier2BoundaryCornerCases::test_adapter_empty_output_handling`, `test_adapter_massive_log_resilience`, `test_adapter_corrupted_ansi_handling`, `test_adapter_zero_test_with_nonzero_exit` | Tier 2 | No crashes, memory stable, preserved exit codes |
| **F18** | CTest Deep File Path Isolation | R1 | `TestTier2BoundaryCornerCases::test_ctest_deep_nested_and_multiple_failure_frames` | Tier 2 | Multi-file frames isolated without truncation |
| **F19** | Benchmark Boundary Conditions | R2 | `TestTier2BoundaryCornerCases::test_swe_bench_empty_or_corrupt_recovery`, `test_swe_bench_latency_measurement_precision` | Tier 2 | Sub-millisecond timing, safe fallbacks |
| **F20** | CI/CD Boundary Conditions | R3 | `TestTier2BoundaryCornerCases::test_cli_flag_interactions_and_edge_commands`, `test_action_custom_inputs_and_scope_violation` | Tier 2 | Proper flag parsing, exit code 102 on scope |
| **F21** | Sieve + Sentinel Synchronization | R1, R3 | `TestTier3CrossFeatureCombinations::test_sieve_sentinel_synchronization_all_adapters` | Tier 3 | Correct alert formatting and sieved token output |
| **F22** | ScopeLock + Sieve + Sentinel CLI | R1, R3 | `TestTier3CrossFeatureCombinations::test_cli_scopelock_sentinel_sieve_integration` | Tier 3 | End-to-end CLI execution with all shields |
| **F23** | Dual CLI Sieve Parity | R3 | `TestTier3CrossFeatureCombinations::test_dual_cli_parity_and_piping` | Tier 3 | `agentfix` and `agentfixer` yield identical output |
| **F24** | Benchmark Cross-Engine Coupling | R2 | `TestTier3CrossFeatureCombinations::test_swe_bench_cross_engine_coupling` | Tier 3 | Dual-path execution (raw baseline vs shielded) |
| **F25** | Pre-Commit to CI Pipeline | R3 | `TestTier3CrossFeatureCombinations::test_pre_commit_to_action_contract_parity` | Tier 3 | Same flags and expectations across environments |
| **F26** | Polyglot Agent Pipeline Scenario | R1, R3 | `TestTier4RealWorldScenarios::test_polyglot_agent_maven_repair_workflow` | Tier 4 | Multi-step failing test $\to$ patch $\to$ passing test |
| **F27** | CTest C++ Refactoring Scenario | R1 | `TestTier4RealWorldScenarios::test_ctest_cpp_refactoring_workflow` | Tier 4 | Isolate frame $\to$ fix $\to$ 100% passing suite |
| **F28** | Zero-Test Trap Prevention | R1, R3 | `TestTier4RealWorldScenarios::test_zero_test_trap_prevention_scenario` | Tier 4 | Agent typo test intercepted with exit 101 |
| **F29** | SWE-bench Evaluation Lifecycle | R2 | `TestTier4RealWorldScenarios::test_swe_bench_evaluation_lifecycle` | Tier 4 | End-to-end 20 tasks, TSV written, $\ge 85\%$ verified |
| **F30** | Developer Git Pre-Commit Workflow | R3 | `TestTier4RealWorldScenarios::test_developer_precommit_to_ci_workflow` | Tier 4 | Clutter purged, clean working tree, CI green |

---

## 4. Test Runner Instructions

### 4.1 Running the Full E2E Test Suite
To execute all tiers with verbose reporting:
```bash
pytest tests/test_e2e_expansion.py -v
```

### 4.2 Running Specific Test Tiers
Run tests for a single tier using pytest's `-k` expression matching:

```bash
# Run Tier 1: Feature Coverage only
pytest tests/test_e2e_expansion.py -k "TestTier1FeatureCoverage" -v

# Run Tier 2: Boundary & Corner Cases only
pytest tests/test_e2e_expansion.py -k "TestTier2BoundaryCornerCases" -v

# Run Tier 3: Cross-Feature Combinations only
pytest tests/test_e2e_expansion.py -k "TestTier3CrossFeatureCombinations" -v

# Run Tier 4: Real-World Application Scenarios only
pytest tests/test_e2e_expansion.py -k "TestTier4RealWorldScenarios" -v
```

### 4.3 Running Across All Test Modules
To run existing unit tests along with the E2E suite:
```bash
pytest -v
```

### 4.4 Running Automated SWE-bench Benchmarks
Execute the standalone evaluation container:
```bash
# Automated container execution with host fallback
bash benchmarks/run_swe_bench_docker.sh

# Or directly via host Python runtime
python3 benchmarks/run_swe_bench.py
```
This writes `benchmarks/swe_bench_results.tsv` and asserts $\ge 85.0\%$ token reduction.
