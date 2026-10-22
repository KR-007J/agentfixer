"""Sentinel: False-Pass and Silent Failure Interceptor for AI Coding Agents.

Detects scenarios where test runners or scripts exit with status 0 despite
zero tests being executed, silent mocking, or swallowed errors. Overrides
the exit status to prevent agent action hallucinations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class SentinelResult:
    """Outcome of false-pass inspection."""
    is_false_pass: bool
    original_exit_code: int
    effective_exit_code: int
    reason: str = ""
    remediation_hint: str = ""
    hint: str = ""

    def __post_init__(self):
        if not self.hint and self.remediation_hint:
            self.hint = self.remediation_hint
        elif not self.remediation_hint and self.hint:
            self.remediation_hint = self.hint


class FalsePassSentinel:
    """Inspects stdout/stderr against known silent failure patterns."""

    PATTERNS = [
        # Pytest zero collection
        (
            re.compile(r"collected 0 items|no tests ran", re.IGNORECASE),
            "Pytest collected 0 test items.",
            "Verify test discovery path, test file naming (test_*.py or *_test.py), or test function prefixes."
        ),
        # Python unittest zero tests
        (
            re.compile(r"Ran 0 tests in [\d\.]+s", re.IGNORECASE),
            "Python unittest ran 0 tests.",
            "Ensure test cases inherit from unittest.TestCase and module/class names match discovery."
        ),
        # Jest / Vitest zero tests
        (
            re.compile(r"no tests found|ran 0 test suites|0 passed, 0 total", re.IGNORECASE),
            "Jest/Vitest found no tests to run.",
            "Check jest.config or test regex pattern. Do not assume tests passed."
        ),
        # Cargo test zero tests
        (
            re.compile(r"running 0 tests", re.IGNORECASE),
            "Cargo ran 0 tests.",
            "Ensure test functions are decorated with #[test] or check harness configuration."
        ),
        # Go test zero tests
        (
            re.compile(r"\[no test files\]|\[no tests to run\]", re.IGNORECASE),
            "Go found no test files or tests to run.",
            "Check package directory and verify file names end in _test.go."
        ),
        # Maven zero tests
        (
            re.compile(
                r"Tests run:\s*0,\s*Failures:\s*0,\s*Errors:\s*0|There are no tests to run|No tests to run\.|No tests were executed",
                re.IGNORECASE
            ),
            "Maven ran 0 tests.",
            "Ensure test classes match Surefire patterns (*Test.java, Test*.java, *TestCase.java) or check -Dtest parameter."
        ),
        # Gradle zero tests
        (
            re.compile(
                r"Task\s+:\S*test\S*\s+NO-SOURCE|\b0 tests completed\b|No tests found for given includes",
                re.IGNORECASE
            ),
            "Gradle ran 0 tests (:test NO-SOURCE or 0 tests completed).",
            "Check test source directory (src/test/java or src/test/kotlin) and test class naming."
        ),
        # CTest / GoogleTest zero tests
        (
            re.compile(
                r"\b0% tests passed,\s*0 tests failed out of\s*0\b|No tests were found!!!|\b0 tests from 0 test suites ran|\[\s*PASSED\s*\]\s*0 tests\b",
                re.IGNORECASE
            ),
            "CTest/GoogleTest ran 0 tests.",
            "Verify CMakeLists.txt enable_testing(), add_test(), or gtest_discover_tests() configuration."
        ),
        # Cargo nextest zero tests
        (
            re.compile(
                r"\b0 tests run:\s*0 passed|Starting\s+0\s+tests across",
                re.IGNORECASE
            ),
            "Cargo nextest ran 0 tests.",
            "Verify test functions have #[test] attribute or check nextest filter arguments (-E / filter)."
        ),
    ]

    @classmethod
    def inspect(
        cls,
        stdout: str,
        stderr: str = "",
        exit_code: int = 0,
        command: str = "",
        allow_empty: bool = False,
    ) -> SentinelResult:
        """Inspect command execution for false-pass anomalies.

        If exit_code is 0 but tests did not execute, effective_exit_code becomes 101.
        """
        combined = f"{stdout}\n{stderr}".strip()

        # If already non-zero, it is a real failure, not a false pass
        if exit_code != 0:
            return SentinelResult(
                is_false_pass=False,
                original_exit_code=exit_code,
                effective_exit_code=exit_code,
            )

        cmd_lower = command.lower()
        is_test_command = any(
            t in cmd_lower for t in (
                "test", "pytest", "jest", "vitest", "cargo", "unittest", "eval",
                "mvn", "mvnw", "maven", "gradle", "gradlew", "ctest", "gtest", "nextest"
            )
        )

        # Check for empty output on explicit test commands
        if is_test_command and not combined and not allow_empty:
            return SentinelResult(
                is_false_pass=True,
                original_exit_code=0,
                effective_exit_code=101,
                reason="Test command exited with code 0 but produced zero output.",
                remediation_hint="Command may have been short-circuited or swallowed. Verify harness execution."
            )

        # Check known regex false-pass signatures
        for pattern, reason, hint in cls.PATTERNS:
            if pattern.search(combined):
                return SentinelResult(
                    is_false_pass=True,
                    original_exit_code=0,
                    effective_exit_code=101,
                    reason=reason,
                    remediation_hint=hint,
                )

        return SentinelResult(
            is_false_pass=False,
            original_exit_code=0,
            effective_exit_code=0,
        )

    @classmethod
    def format_alert(cls, result: SentinelResult) -> str:
        """Format an unmistakable alert block for the agent context."""
        if not result.is_false_pass:
            return ""
        return (
            f"\n"
            f"======================================================================\n"
            f"[AgentFixer CRITICAL FALSE-PASS INTERCEPTED]\n"
            f"Original Exit Code: {result.original_exit_code} -> Overridden: {result.effective_exit_code}\n"
            f"Detection: {result.reason}\n"
            f"Remediation: {result.remediation_hint}\n"
            f"WARNING: Do NOT treat this task as passing. The test suite did not execute.\n"
            f"======================================================================\n"
        )
