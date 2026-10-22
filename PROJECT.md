# Project: AgentFixer Expansion (Adapters, SWE-bench Docker Runner, CI/CD Integrations)

## Architecture
AgentFixer is a zero-runtime-dependency autonomous execution shield that intercepts false passes, compresses test output tokens, enforces file scope locks, and repairs failing code.
- **TokenSieve (`src/agentfixer/tokensieve.py`)**: Multi-language test output stream compressor. Strips ANSI escapes, suppresses verbose passing logs (>=90% compression), and isolates failing stack traces.
- **FalsePassSentinel (`src/agentfixer/sentinel.py`)**: Interception engine that inspects test output and process exit codes, overriding silent false passes (0 tests collected/run) to exit code 101.
- **CLI (`src/agentfixer/cli.py`, `src/agentfixer/__main__.py`)**: Command line wrapper (`agentfix`, `agentfixer`, `python -m agentfixer`) exposing subcommands `run`, `patch`, `demo`, and `audit`.
- **SWE-bench Docker Harness (`benchmarks/`)**: Standalone reproducible Docker evaluation runner (`Dockerfile`, `run_swe_bench_docker.sh`, `run_swe_bench.py`) executing 20 real SWE-bench Lite task instances.
- **CI/CD Integrations (`action.yml`, `.pre-commit-hooks.yaml`)**: Zero-dependency 1-line integration assets for GitHub Actions and Pre-Commit workflows.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Maven Adapter Compression | Compress passing `mvn test` logs by >= 90% via TokenSieve | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Maven Zero-Test Interception | Intercept `Tests run: 0` in Maven and enforce exit code 101 | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Gradle Adapter Compression | Compress passing `gradle test` logs by >= 90% via TokenSieve | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Gradle Zero-Test Interception | Intercept `NO-SOURCE` / `0 tests completed` in Gradle to exit code 101 | M1 | ORIGINAL_REQUEST §R1 |
| 5 | CTest Failure Frame Isolation | Isolate CTest/GoogleTest failures with exact file and line accuracy | M1 | ORIGINAL_REQUEST §R1 |
| 6 | CTest Pass & Zero-Test Handling | Compress CTest passes by >=90% and intercept zero-test runs (exit 101) | M1 | ORIGINAL_REQUEST §R1 |
| 7 | Rust Cargo Nextest Adapter | Parse nextest output, suppress pass lines, isolate panic/failure traces | M1 | ORIGINAL_REQUEST §R1 |
| 8 | Adapter Unit Test Suite | Comprehensive adapter tests in `tests/test_adapters.py` | M1 | ORIGINAL_REQUEST §R1 |
| 9 | SWE-bench 20-Task Suite | Curate 20 real SWE-bench Lite task instances across 8 diverse repositories | M2 | ORIGINAL_REQUEST §R2 |
| 10 | SWE-bench Dockerfile | Standalone, reproducible Docker container based on python:3.11-slim | M2 | ORIGINAL_REQUEST §R2 |
| 11 | SWE-bench Docker Runner Script | Automated `benchmarks/run_swe_bench_docker.sh` with volume mount & host fallback | M2 | ORIGINAL_REQUEST §R2 |
| 12 | SWE-bench TSV Generation | Generate `benchmarks/swe_bench_results.tsv` with 13 columns and summary | M2 | ORIGINAL_REQUEST §R2 |
| 13 | SWE-bench >= 85% Token Reduction | Empirically prove >= 85% token reduction across SWE-bench tasks | M2 | ORIGINAL_REQUEST §R2 |
| 14 | Native Pre-Commit Hooks | Provide `.pre-commit-hooks.yaml` with audit, pytest, scopelock, and run hooks | M3 | ORIGINAL_REQUEST §R3 |
| 15 | 1-Line GitHub Action | Provide root `action.yml` composite action for `- uses: KR-007J/agentfixer@main` | M3 | ORIGINAL_REQUEST §R3 |
| 16 | Dual CLI Console Scripts | Register `agentfixer` console script and `__main__.py` entry point | M3 | survey_explorer_3 |
| 17 | CI/CD Integration Docs | Provide `docs/CICD_INTEGRATION_GUIDE.md` and updated `README.md` | M3 | ORIGINAL_REQUEST §R3 |
| 18 | CI Workflow Dogfooding | Dogfood `action.yml` and adapter matrix in `.github/workflows/ci.yml` | M3 | survey_explorer_3 |
| 19 | Opaque-Box E2E Test Suite | Requirements-driven multi-tier E2E tests verifying all user criteria | M4 | Project Architecture |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Multi-Language Adapters | Maven, Gradle, CTest, Cargo Nextest in TokenSieve & Sentinel; `tests/test_adapters.py` | none | PLANNED |
| M2 | SWE-bench Docker Runner | `benchmarks/Dockerfile`, `run_swe_bench_docker.sh`, `run_swe_bench.py`, `swe_bench_results.tsv` | M1 | PLANNED |
| M3 | Pre-Commit & CI/CD Integrations | `action.yml`, `.pre-commit-hooks.yaml`, dual CLI scripts, `__main__.py`, docs | M1 | PLANNED |
| M4 | Final Milestone & E2E Validation | Pass 100% of E2E test suite (Tiers 1-4) and adversarial coverage hardening (Tier 5) | M1, M2, M3 | PLANNED |

## Interface Contracts
### TokenSieve ↔ Test Runners
- Method: `TokenSieve.sieve(raw_output: str, exit_code: int = 0, command: str = "") -> Tuple[str, int]`
- Returns: `(sieved_text, tokens_saved)`
- Requirements: Strips ANSI escapes (`\x1b\[[0-9;]*[mK]`), suppresses passing lines by >= 90%, isolates failure frames.

### FalsePassSentinel ↔ Test Output
- Method: `FalsePassSentinel.inspect(cmd: str, stdout: str, exit_code: int) -> Tuple[int, Optional[str]]`
- Returns: `(effective_exit_code, alert_message)`
- Requirements: If zero tests ran/collected and `exit_code == 0`, overrides to `101` and generates diagnostic alert.

### SWE-bench Runner ↔ Docker
- Command: `bash benchmarks/run_swe_bench_docker.sh`
- Output: `benchmarks/swe_bench_results.tsv` containing 20 task rows + `TOTAL_SUMMARY` row with `reduction_pct >= 85.0`.

### GitHub Actions ↔ External Workflows
- Usage: `- uses: KR-007J/agentfixer@main`
- Inputs: `command` (default: `pytest`), `strict-scope` (default: `false`), `audit` (default: `true`).

## Code Layout
- `src/agentfixer/`: Core library package
  - `tokensieve.py`: Test output compressor & adapter logic
  - `sentinel.py`: False pass interception & pattern matching
  - `cli.py`: CLI dispatch & entry points
  - `__main__.py`: Module entry point (`python -m agentfixer`)
- `tests/`: Unit & integration tests
  - `test_adapters.py`: R1 adapter verification
  - `test_swe_bench_runner.py`: R2 evaluation harness verification
  - `test_ci_integrations.py`: R3 hook and action verification
  - `test_e2e_expansion.py`: Full opaque-box E2E test suite
- `benchmarks/`: Benchmark & evaluation assets
  - `Dockerfile`: Standalone evaluation container
  - `run_swe_bench_docker.sh`: Automated Docker runner script
  - `run_swe_bench.py`: SWE-bench Lite 20-task runner
  - `swe_bench_results.tsv`: Comparative benchmark results
- `.pre-commit-hooks.yaml`: Native pre-commit hook specifications
- `action.yml`: GitHub Actions composite action
