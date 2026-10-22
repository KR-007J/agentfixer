"""Comprehensive Unit Tests for Multi-Language Test Runner Adapters (R1).

Verifies acceptance criteria:
1. Java Maven & Gradle passing logs compressed by >= 90%.
2. Java Gradle & Maven zero-test false passes intercepted with exit code 101.
3. C/C++ CTest failure frames isolated with exact file and line coordinates.
4. Rust cargo nextest pass suppression and failure isolation.
5. Strict ANSI escape stripping across all adapters.
6. Sentinel empty-output protection across all adapter commands.
7. Negative tests ensuring legitimate passing runs (>0 tests) are never intercepted.
"""

from __future__ import annotations

import pytest
from agentfixer.sentinel import FalsePassSentinel
from agentfixer.tokensieve import TokenSieve, estimate_tokens


# ==============================================================================
# 1. Java Maven Adapter Tests
# ==============================================================================

def test_sieve_maven_pass():
    raw_output = (
        "[INFO] Scanning for projects...\n"
        "[INFO] -------------------< com.example:my-app >--------------------\n"
        "[INFO] Building my-app 1.0-SNAPSHOT\n"
        + "".join([f"[INFO] Compiling module source file {i}.java\n" for i in range(40)])
        + "[INFO] --- maven-surefire-plugin:3.2.5:test (default-test) @ my-app ---\n"
        "[INFO] Running com.example.AppTest\n"
        + "".join([f"[INFO] Test case {i} executed in 0.01s\n" for i in range(25)])
        + "[INFO] Results:\n"
        "[INFO] \n"
        "[INFO] Tests run: 25, Failures: 0, Errors: 0, Skipped: 0\n"
        "[INFO] \n"
        "[INFO] ------------------------------------------------------------------------\n"
        "[INFO] BUILD SUCCESS\n"
        "[INFO] ------------------------------------------------------------------------\n"
        "[INFO] Total time:  3.456 s\n"
        "[INFO] Finished at: 2026-10-22T07:15:00Z\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="mvn test")
    assert res["is_compressed"] is True
    assert res["reduction_pct"] >= 90.0
    assert "[AgentFixer PASS] maven:" in res["sieved_text"]
    assert "Tests run: 25, Failures: 0, Errors: 0, Skipped: 0" in res["sieved_text"]
    assert "3.456 s" in res["sieved_text"]
    assert "Compiling module source file" not in res["sieved_text"]


def test_sieve_maven_failure_extracts_stack_and_summary():
    raw_output = (
        "[INFO] --- maven-surefire-plugin:3.2.5:test (default-test) @ my-app ---\n"
        "[INFO] Running com.example.CalculatorTest\n"
        "[ERROR] Tests run: 2, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 0.055 s <<< FAILURE! -- in com.example.CalculatorTest\n"
        "[ERROR] com.example.CalculatorTest.testAdd -- Time elapsed: 0.015 s <<< FAILURE!\n"
        "org.opentest4j.AssertionFailedError: expected: <5> but was: <4>\n"
        "\tat com.example.CalculatorTest.testAdd(CalculatorTest.java:18)\n"
        "\tat java.base/jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method)\n"
        "[INFO] Results:\n"
        "[INFO] \n"
        "[ERROR] Failures: \n"
        "[ERROR]   CalculatorTest.testAdd:18 expected: <5> but was: <4>\n"
        "[INFO] \n"
        "[ERROR] Tests run: 2, Failures: 1, Errors: 0, Skipped: 0\n"
        "[INFO] ------------------------------------------------------------------------\n"
        "[INFO] BUILD FAILURE\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=1, command="mvn test")
    assert "[AgentFixer FAIL: maven exit 1]" in res["sieved_text"]
    assert "CalculatorTest.java:18" in res["sieved_text"]
    assert "expected: <5> but was: <4>" in res["sieved_text"]
    assert "jdk.internal.reflect" not in res["sieved_text"]


def test_sieve_maven_ansi_stripped():
    raw_output = (
        "\x1b[1m[INFO] Scanning for projects...\x1b[m\n"
        "\x1b[1;32m[INFO] BUILD SUCCESS\x1b[m\n"
        "[INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0\n"
        "[INFO] Total time: 1.234 s\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="mvn test")
    assert "\x1b[" not in res["sieved_text"]
    assert "[AgentFixer PASS] maven:" in res["sieved_text"]


def test_sentinel_maven_zero_tests_intercepted():
    raw_output = (
        "[INFO] --- maven-surefire-plugin:3.2.5:test (default-test) @ my-app ---\n"
        "[INFO] Results:\n"
        "[INFO] \n"
        "[INFO] Tests run: 0, Failures: 0, Errors: 0, Skipped: 0\n"
        "[INFO] ------------------------------------------------------------------------\n"
        "[INFO] BUILD SUCCESS\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="mvn test")
    assert res.is_false_pass is True
    assert res.original_exit_code == 0
    assert res.effective_exit_code == 101
    assert "Maven ran 0 tests." in res.reason


def test_sentinel_maven_no_tests_to_run_intercepted():
    raw_output = (
        "[INFO] -------------------------------------------------------\n"
        "[INFO]  T E S T S\n"
        "[INFO] -------------------------------------------------------\n"
        "[INFO] There are no tests to run.\n"
        "[INFO] ------------------------------------------------------------------------\n"
        "[INFO] BUILD SUCCESS\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="./mvnw test")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


def test_sentinel_maven_empty_output_intercepted():
    res = FalsePassSentinel.inspect(stdout="", exit_code=0, command="mvn test")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


# ==============================================================================
# 2. Java Gradle Adapter Tests
# ==============================================================================

def test_sieve_gradle_pass():
    raw_output = (
        "\x1b[32m> Task :compileJava UP-TO-DATE\x1b[0m\n"
        "> Task :processResources UP-TO-DATE\n"
        "> Task :classes UP-TO-DATE\n"
        "> Task :compileTestJava UP-TO-DATE\n"
        "> Task :processTestResources NO-SOURCE\n"
        "> Task :testClasses UP-TO-DATE\n"
        "> Task :test\n"
        + "".join([f"com.example.AppTest > test{i}() \x1b[32mPASSED\x1b[0m\n" for i in range(35)])
        + "\nBUILD SUCCESSFUL in 1s\n"
        "4 actionable tasks: 1 executed, 3 up-to-date\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="gradle test")
    assert res["is_compressed"] is True
    assert res["reduction_pct"] >= 90.0
    assert "[AgentFixer PASS] gradle:" in res["sieved_text"]
    assert "BUILD SUCCESSFUL in 1s" in res["sieved_text"]
    assert "\x1b[32m" not in res["sieved_text"]
    assert "test15() PASSED" not in res["sieved_text"]


def test_sieve_gradle_failure():
    raw_output = (
        "> Task :test FAILED\n\n"
        "com.example.CalculatorTest > testMultiply() FAILED\n"
        "    org.opentest4j.AssertionFailedError: expected: <10> but was: <8>\n"
        "        at org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:38)\n"
        "        at com.example.CalculatorTest.testMultiply(CalculatorTest.java:27)\n\n"
        "1 test completed, 1 failed\n"
        "FAILURE: Build failed with an exception.\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=1, command="./gradlew test")
    assert "[AgentFixer FAIL: gradle exit 1]" in res["sieved_text"]
    assert "CalculatorTest.java:27" in res["sieved_text"]
    assert "testMultiply() FAILED" in res["sieved_text"]
    assert "1 test completed, 1 failed" in res["sieved_text"]


def test_sieve_gradle_ansi_stripped():
    raw_output = (
        "\x1b[33m> Task :compileJava UP-TO-DATE\x1b[0m\n"
        "\x1b[32mBUILD SUCCESSFUL in 850ms\x1b[0m\n"
        "2 actionable tasks: 2 up-to-date\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="gradle test")
    assert "\x1b[" not in res["sieved_text"]
    assert "[AgentFixer PASS] gradle:" in res["sieved_text"]


def test_sentinel_gradle_no_source_intercepted():
    raw_output = (
        "> Task :compileJava UP-TO-DATE\n"
        "> Task :processResources NO-SOURCE\n"
        "> Task :classes UP-TO-DATE\n"
        "> Task :compileTestJava NO-SOURCE\n"
        "> Task :processTestResources NO-SOURCE\n"
        "> Task :testClasses UP-TO-DATE\n"
        "> Task :test NO-SOURCE\n\n"
        "BUILD SUCCESSFUL in 450ms\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="gradle test")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101
    assert "Gradle ran 0 tests" in res.reason


def test_sentinel_gradle_subproject_no_source_intercepted():
    raw_output = (
        "> Task :core:test NO-SOURCE\n"
        "> Task :app:test NO-SOURCE\n\n"
        "BUILD SUCCESSFUL in 600ms\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="./gradlew test")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


def test_sentinel_gradle_zero_tests_completed_intercepted():
    raw_output = (
        "> Task :test\n"
        "0 tests completed\n\n"
        "BUILD SUCCESSFUL in 300ms\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="gradle test")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


def test_sentinel_gradle_empty_output_intercepted():
    res = FalsePassSentinel.inspect(stdout="", exit_code=0, command="./gradlew test")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


# ==============================================================================
# 3. C/C++ CTest & GoogleTest Adapter Tests
# ==============================================================================

def test_sieve_ctest_pass():
    raw_output = (
        "Test project /workspace/build\n"
        + "".join([f"    Start {i}: MathTests.Test{i}\n{i}/30 Test #{i}: MathTests.Test{i} ...............   Passed    0.01 sec\n" for i in range(1, 31)])
        + "\n100% tests passed, 0 tests failed out of 30\n\n"
        "Total Test time (real) =   0.35 sec\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="ctest")
    assert res["is_compressed"] is True
    assert res["reduction_pct"] >= 90.0
    assert "[AgentFixer PASS] ctest:" in res["sieved_text"]
    assert "100% tests passed, 0 tests failed out of 30" in res["sieved_text"]
    assert "MathTests.Test15" not in res["sieved_text"]


def test_sieve_ctest_failure_exact_file_and_line():
    raw_output = (
        "Test project /workspace/build\n"
        "    Start 1: MathTests.Division\n"
        "1/2 Test #1: MathTests.Division ...............***Failed    0.02 sec\n"
        "[==========] Running 1 test from 1 test suite.\n"
        "[ RUN      ] MathTests.Division\n"
        "/workspace/tests/test_math.cpp:42: Failure\n"
        "Expected equality of these values:\n"
        "  divide(10, 2)\n"
        "    Which is: 4\n"
        "  5\n"
        "[  FAILED  ] MathTests.Division (0 ms)\n"
        "    Start 2: MathTests.Multiply\n"
        "2/2 Test #2: MathTests.Multiply ...............   Passed    0.01 sec\n\n"
        "50% tests passed, 1 tests failed out of 2\n\n"
        "The following tests FAILED:\n"
        "\t  1 - MathTests.Division (Failed)\n"
        "Errors while running CTest\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=8, command="ctest --output-on-failure")
    assert "[AgentFixer FAIL: ctest exit 8]" in res["sieved_text"]
    assert "/workspace/tests/test_math.cpp:42" in res["sieved_text"]
    assert "divide(10, 2)" in res["sieved_text"]
    assert "MathTests.Multiply" not in res["sieved_text"]


def test_sieve_ctest_ansi_stripped():
    raw_output = (
        "\x1b[36mTest project /workspace/build\x1b[0m\n"
        "1/1 Test #1: FooTest ..... \x1b[32mPassed\x1b[0m 0.01 sec\n"
        "100% tests passed, 0 tests failed out of 1\n"
        "Total Test time (real) = 0.01 sec\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="ctest")
    assert "\x1b[" not in res["sieved_text"]
    assert "[AgentFixer PASS] ctest:" in res["sieved_text"]


def test_sentinel_ctest_zero_tests_intercepted():
    raw_output = (
        "Test project /workspace/build\n"
        "0% tests passed, 0 tests failed out of 0\n\n"
        "Total Test time (real) =   0.00 sec\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="ctest")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101
    assert "CTest/GoogleTest ran 0 tests" in res.reason


def test_sentinel_ctest_no_tests_found_intercepted():
    raw_output = (
        "Test project /workspace/build\n"
        "No tests were found!!!\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="ctest")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


def test_sentinel_gtest_zero_tests_intercepted():
    raw_output = (
        "[==========] Running 0 tests from 0 test suites.\n"
        "[==========] 0 tests from 0 test suites ran. (0 ms total)\n"
        "[  PASSED  ] 0 tests.\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="./run_unit_tests")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


def test_sentinel_ctest_empty_output_intercepted():
    res = FalsePassSentinel.inspect(stdout="", exit_code=0, command="ctest")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


# ==============================================================================
# 4. Rust Cargo Nextest Adapter Tests
# ==============================================================================

def test_sieve_cargo_nextest_pass():
    raw_output = (
        "    Compiling my_project v0.1.0 (/workspace/my_project)\n"
        "    Finished test [unoptimized + debuginfo] target(s) in 0.85s\n"
        "    Starting 30 tests across 1 binary\n"
        + "".join([f"        PASS [   0.00{i % 9}s] my_project::tests test_{i}\n" for i in range(30)])
        + "------------\n"
        "     Summary [   0.045s] 30 tests run: 30 passed, 0 skipped\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="cargo nextest run")
    assert res["is_compressed"] is True
    assert res["reduction_pct"] >= 90.0
    assert "[AgentFixer PASS] cargo-nextest:" in res["sieved_text"]
    assert "30 tests run: 30 passed" in res["sieved_text"]
    assert "PASS [   0.00" not in res["sieved_text"]


def test_sieve_cargo_nextest_failure():
    raw_output = (
        "    Starting 2 tests across 1 binary\n"
        "        PASS [   0.004s] my_crate::tests test_pass\n"
        "        FAIL [   0.006s] my_crate::tests test_fail\n\n"
        "--- FAIL: my_crate::tests test_fail ---\n"
        "thread 'tests::test_fail' panicked at src/math.rs:18:9:\n"
        "assertion `left == right` failed\n"
        "  left: 4\n"
        " right: 5\n"
        "stack backtrace:\n"
        "   0: rust_begin_unwind\n"
        "------------\n"
        "     Summary [   0.018s] 2 tests run: 1 passed, 1 failed, 0 skipped\n"
        "error: test run failed\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=1, command="cargo nextest run")
    assert "[AgentFixer FAIL: cargo-nextest exit 1]" in res["sieved_text"]
    assert "src/math.rs:18:9" in res["sieved_text"]
    assert "assertion `left == right` failed" in res["sieved_text"]
    assert "test_pass" not in res["sieved_text"]


def test_sieve_cargo_nextest_ansi_stripped():
    raw_output = (
        "    \x1b[32mStarting\x1b[0m 2 tests across 1 binary\n"
        "        \x1b[32mPASS\x1b[0m [   0.002s] my_crate::tests test_1\n"
        "------------\n"
        "     Summary [   0.010s] 2 tests run: 2 passed, 0 skipped\n"
    )
    res = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="cargo nextest run")
    assert "\x1b[" not in res["sieved_text"]
    assert "[AgentFixer PASS] cargo-nextest:" in res["sieved_text"]


def test_sentinel_cargo_nextest_zero_tests_intercepted():
    raw_output = (
        "    Starting 0 tests across 0 binaries\n"
        "------------\n"
        "     Summary [   0.001s] 0 tests run: 0 passed, 0 skipped\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="cargo nextest run")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101
    assert "Cargo nextest ran 0 tests" in res.reason


def test_sentinel_cargo_nextest_empty_output_intercepted():
    res = FalsePassSentinel.inspect(stdout="", exit_code=0, command="cargo nextest run")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


# ==============================================================================
# 5. Negative Verification (Legitimate Passes Not Intercepted)
# ==============================================================================

def test_sentinel_maven_legitimate_pass_not_intercepted():
    raw_output = (
        "[INFO] Results:\n"
        "[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0\n"
        "[INFO] BUILD SUCCESS\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="mvn test")
    assert res.is_false_pass is False
    assert res.effective_exit_code == 0


def test_sentinel_gradle_legitimate_pass_not_intercepted():
    raw_output = (
        "> Task :test\n"
        "10 tests completed\n\n"
        "BUILD SUCCESSFUL in 1s\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="gradle test")
    assert res.is_false_pass is False
    assert res.effective_exit_code == 0


def test_sentinel_ctest_legitimate_pass_not_intercepted():
    raw_output = (
        "Test project /workspace/build\n"
        "100% tests passed, 0 tests failed out of 10\n"
        "Total Test time (real) = 0.10 sec\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="ctest")
    assert res.is_false_pass is False
    assert res.effective_exit_code == 0


def test_sentinel_nextest_legitimate_pass_not_intercepted():
    raw_output = (
        "------------\n"
        "     Summary [   0.020s] 10 tests run: 10 passed, 0 skipped\n"
    )
    res = FalsePassSentinel.inspect(stdout=raw_output, exit_code=0, command="cargo nextest run")
    assert res.is_false_pass is False
    assert res.effective_exit_code == 0
