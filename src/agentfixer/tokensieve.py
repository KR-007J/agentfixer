"""TokenSieve: Intelligent CLI output filter and token compressor for AI coding agents.

Reduces raw CLI and test logs by 80%–98% to prevent context window saturation
and avoid catastrophic instruction erosion / agent amnesia.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Tuple

# Comprehensive regex to strip ANSI color codes, cursor movement, and styles
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from the string."""
    return ANSI_ESCAPE_RE.sub("", text)


def clean_progress_bars(text: str) -> str:
    """Normalize carriage returns (\r) often produced by spinners and progress bars."""
    lines = []
    for raw_line in text.split("\n"):
        if "\r" in raw_line:
            parts = [p for p in raw_line.split("\r") if p.strip()]
            line = parts[-1] if parts else ""
        else:
            line = raw_line
        lines.append(line)
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """Fast, accurate token estimation heuristic (1 token ~ 4 characters)."""
    if not text:
        return 0
    # Average LLM BPE tokenization is ~4 characters per token in technical text
    return max(1, (len(text) + 3) // 4)


class TokenSieve:
    """Filters, compresses, and surfaces high-signal test and build logs."""

    @classmethod
    def sieve(
        cls,
        stdout: str,
        stderr: str = "",
        exit_code: int = 0,
        command: str = "",
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Sieve raw CLI execution output.

        Returns a dictionary with:
            - sieved_text: High-signal token-compressed output
            - original_tokens: Estimated raw tokens
            - sieved_tokens: Estimated compressed tokens
            - tokens_saved: Raw - Sieved
            - reduction_pct: Percentage token reduction
            - is_compressed: True if output was compressed
        """
        if isinstance(stderr, int):
            command = exit_code if isinstance(exit_code, str) else command
            exit_code = stderr
            stderr = ""

        raw_combined = (stdout + ("\n" + stderr if stderr else "")).strip()
        cleaned = clean_progress_bars(strip_ansi(raw_combined))
        orig_tokens = estimate_tokens(raw_combined)

        if verbose or not raw_combined:
            return {
                "sieved_text": cleaned,
                "original_tokens": orig_tokens,
                "sieved_tokens": estimate_tokens(cleaned),
                "tokens_saved": 0,
                "reduction_pct": 0.0,
                "is_compressed": False,
            }

        cmd_lower = command.lower()
        cleaned_lower = cleaned.lower()
        if "cargo nextest" in cmd_lower or "cargo-nextest" in cmd_lower or "nextest" in cmd_lower or ("summary [" in cleaned_lower and "tests run:" in cleaned_lower):
            sieved = cls._compress_nextest(cleaned, exit_code)
        elif "ctest" in cmd_lower or "gtest" in cmd_lower or "test project" in cleaned_lower or "[==========] running" in cleaned_lower or ("tests passed," in cleaned_lower and "tests failed out of" in cleaned_lower):
            sieved = cls._compress_ctest(cleaned, exit_code)
        elif "mvn" in cmd_lower or "maven" in cmd_lower or "maven-surefire-plugin" in cleaned_lower or "t e s t s" in cleaned_lower:
            sieved = cls._compress_maven(cleaned, exit_code)
        elif "gradle" in cmd_lower or "gradlew" in cmd_lower or "task :test" in cleaned_lower:
            sieved = cls._compress_gradle(cleaned, exit_code)
        elif "pytest" in cmd_lower or "python -m unittest" in cmd_lower or "pytest" in cleaned_lower:
            sieved = cls._compress_pytest(cleaned, exit_code)
        elif "npm test" in cmd_lower or "jest" in cmd_lower or "vitest" in cmd_lower:
            sieved = cls._compress_jest(cleaned, exit_code)
        elif "cargo test" in cmd_lower:
            sieved = cls._compress_cargo(cleaned, exit_code)
        elif "go test" in cmd_lower:
            sieved = cls._compress_go(cleaned, exit_code)
        elif "git status" in cmd_lower:
            sieved = cls._compress_git_status(cleaned, exit_code)
        else:
            sieved = cls._compress_generic(cleaned, exit_code)

        sieved_tokens = estimate_tokens(sieved)
        tokens_saved = max(0, orig_tokens - sieved_tokens)
        reduction_pct = round((tokens_saved / orig_tokens * 100.0) if orig_tokens > 0 else 0.0, 1)

        return {
            "sieved_text": sieved,
            "original_tokens": orig_tokens,
            "sieved_tokens": sieved_tokens,
            "tokens_saved": tokens_saved,
            "reduction_pct": reduction_pct,
            "is_compressed": tokens_saved > 0,
        }

    @staticmethod
    def _compress_pytest(text: str, exit_code: int) -> str:
        lines = [line.rstrip() for line in text.splitlines()]
        if exit_code == 0:
            # Look for summary line: e.g. "=== 42 passed in 0.12s ==="
            summary_match = None
            for line in reversed(lines):
                if "passed" in line and ("in " in line or "=" in line):
                    summary_match = line.strip("= ")
                    break
            summary = summary_match if summary_match else "All tests passed successfully."
            return f"[AgentFixer PASS] pytest: {summary} | Full passing log suppressed."

        # Exit code != 0: Extract failures, errors, and traceback
        failure_lines = []
        capture = False
        for line in lines:
            if line.startswith("=" * 5) and ("FAILURES" in line or "ERRORS" in line):
                capture = True
            if capture:
                # Omit verbose root test runner internal traces if possible
                if "_pytest/" in line or "pluggy/" in line:
                    continue
                failure_lines.append(line)

        if not failure_lines:
            # Fallback to last 40 lines where failure summaries typically sit
            failure_lines = lines[-40:]

        extracted = "\n".join(failure_lines).strip()
        return (
            f"[AgentFixer FAIL: pytest exit {exit_code}]\n"
            f"{extracted}\n"
            f"[AgentFixer Note: Passing tests stripped to conserve agent context window.]"
        )

    @staticmethod
    def _compress_jest(text: str, exit_code: int) -> str:
        lines = [line.rstrip() for line in text.splitlines()]
        if exit_code == 0:
            summary = []
            for line in lines:
                if any(k in line for k in ("Tests:", "Snapshots:", "Time:", "Ran all test suites.")):
                    summary.append(line.strip())
            summary_str = " | ".join(summary) if summary else "All tests passed."
            return f"[AgentFixer PASS] jest/vitest: {summary_str} | Verbose output suppressed."

        # Failures: keep FAIL lines, stack traces, and summary
        failure_lines = []
        for line in lines:
            if "PASS " in line and ("ms)" in line or "s)" in line):
                continue
            failure_lines.append(line)
        return f"[AgentFixer FAIL: jest exit {exit_code}]\n" + "\n".join(failure_lines[-50:]).strip()

    @staticmethod
    def _compress_cargo(text: str, exit_code: int) -> str:
        lines = [line.rstrip() for line in text.splitlines()]
        if exit_code == 0:
            for line in reversed(lines):
                if "test result: ok." in line:
                    return f"[AgentFixer PASS] cargo: {line.strip()} | Individual test passes suppressed."
            return "[AgentFixer PASS] cargo test completed successfully."

        # Failures: keep failures block
        fail_blocks = []
        record = False
        for line in lines:
            if "failures:" in line or "error[E" in line:
                record = True
            if record:
                fail_blocks.append(line)
        output = "\n".join(fail_blocks if fail_blocks else lines[-35:]).strip()
        return f"[AgentFixer FAIL: cargo exit {exit_code}]\n{output}"

    @staticmethod
    def _compress_go(text: str, exit_code: int) -> str:
        lines = [line.rstrip() for line in text.splitlines()]
        if exit_code == 0:
            passes = [l.strip() for l in lines if l.startswith("ok  \t") or l == "PASS"]
            summary = ", ".join(passes) if passes else "PASS"
            return f"[AgentFixer PASS] go test: {summary}"

        fails = [l for l in lines if "FAIL" in l or "\tpanic:" in l or "\tError:" in l]
        return f"[AgentFixer FAIL: go exit {exit_code}]\n" + "\n".join(fails if fails else lines[-30:]).strip()

    @staticmethod
    def _compress_git_status(text: str, exit_code: int) -> str:
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if "nothing to commit, working tree clean" in text:
            return "[AgentFixer] git: Working tree clean."
        return "\n".join(lines)

    @staticmethod
    def _compress_generic(text: str, exit_code: int) -> str:
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if len(lines) <= 25:
            return text

        if exit_code == 0:
            head = "\n".join(lines[:4])
            tail = "\n".join(lines[-4:])
            omitted = len(lines) - 8
            return (
                f"{head}\n"
                f"... [AgentFixer: {omitted} lines of repetitive stdout suppressed (Exit 0)] ...\n"
                f"{tail}"
            )

        # On error: keep head and tail of failure
        head = "\n".join(lines[:5])
        tail = "\n".join(lines[-30:])
        return (
            f"[AgentFixer Command Failed (Exit Code {exit_code})]\n"
            f"{head}\n"
            f"... [Middle output elided] ...\n"
            f"{tail}"
        )

    @staticmethod
    def _compress_maven(text: str, exit_code: int) -> str:
        cleaned = strip_ansi(text)
        lines = [line.rstrip() for line in cleaned.splitlines()]

        if exit_code == 0:
            summary_match = re.search(
                r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)",
                cleaned,
            )
            time_match = re.search(r"Total time:\s*([^\n\r]+)", cleaned)
            time_str = f" (Total time: {time_match.group(1).strip()})" if time_match else ""
            if summary_match:
                run, fail, err, skip = summary_match.groups()
                return (
                    f"[AgentFixer PASS] maven: Tests run: {run}, Failures: {fail}, "
                    f"Errors: {err}, Skipped: {skip}{time_str} | Build and test logs suppressed."
                )
            elif "BUILD SUCCESS" in cleaned:
                return f"[AgentFixer PASS] maven: BUILD SUCCESS{time_str} | Build and test logs suppressed."
            return "[AgentFixer PASS] maven: Build and tests passed successfully."

        # Exit code != 0: Extract failures, errors, stack frames, and summary
        filtered_lines = []
        capture_failure = False
        in_failures_block = False

        INTERNAL_FRAMES = (
            "org.apache.maven.surefire.",
            "org.junit.platform.",
            "org.junit.jupiter.",
            "org.junit.vintage.",
            "jdk.internal.reflect.",
            "java.base/jdk.internal",
            "java.base/java.lang.reflect",
            "sun.reflect.",
            "org.testng.",
        )

        for line in lines:
            stripped = line.strip()

            # Capture compiler errors
            if "[ERROR]" in line and (".java:[" in line or "COMPILATION ERROR" in line):
                filtered_lines.append(line)
                continue

            # Detect start of Surefire failure / error banner
            if "<<< FAILURE!" in line or "<<< ERROR!" in line:
                capture_failure = True
                filtered_lines.append(line)
                continue

            # Detect Failures: / Errors: block in Results section
            if re.search(r"\[ERROR\]\s+(Failures|Errors):\s*$", line):
                in_failures_block = True
                filtered_lines.append(line)
                continue

            if in_failures_block:
                if stripped.startswith("[ERROR]   ") or stripped.startswith("  "):
                    filtered_lines.append(line)
                    continue
                elif stripped.startswith("[INFO]") or not stripped:
                    in_failures_block = False

            if capture_failure:
                if any(exc in line for exc in ("Exception", "Error", "AssertionFailedError", "expected:", "but was:")):
                    filtered_lines.append(line)
                    continue
                if stripped.startswith("at "):
                    if not any(fr in line for fr in INTERNAL_FRAMES):
                        filtered_lines.append(line)
                    continue
                if stripped.startswith("[INFO]") or stripped.startswith("[ERROR] -------------------") or not stripped:
                    capture_failure = False

            # Keep Surefire summary line
            if re.search(r"Tests run:\s*\d+,\s*Failures:\s*\d+,\s*Errors:\s*\d+", line):
                if line not in filtered_lines:
                    filtered_lines.append(line)

        if not filtered_lines:
            filtered_lines = [l for l in lines if "[ERROR]" in l][-25:] or lines[-25:]

        body = "\n".join(filtered_lines).strip()
        return f"[AgentFixer FAIL: maven exit {exit_code}]\n{body}"

    @staticmethod
    def _compress_gradle(text: str, exit_code: int) -> str:
        cleaned = clean_progress_bars(strip_ansi(text))
        lines = [line.rstrip() for line in cleaned.splitlines()]

        if exit_code == 0:
            build_match = re.search(r"BUILD SUCCESSFUL in\s+([^\n\r]+)", cleaned)
            action_match = re.search(r"(\d+\s+actionable tasks?:[^\n\r]+)", cleaned)
            time_str = build_match.group(1).strip() if build_match else ""
            action_str = f" ({action_match.group(1).strip()})" if action_match else ""

            if build_match:
                return f"[AgentFixer PASS] gradle: BUILD SUCCESSFUL in {time_str}{action_str} | Passing task output suppressed."
            elif "BUILD SUCCESSFUL" in cleaned:
                return "[AgentFixer PASS] gradle: BUILD SUCCESSFUL | Passing task output suppressed."
            return "[AgentFixer PASS] gradle: Build and tests passed successfully."

        # Exit code != 0: Extract failing tasks, failed tests, stack traces, and summary
        filtered_lines = []
        in_failure = False

        INTERNAL_FRAMES = (
            "org.gradle.",
            "org.junit.platform.",
            "org.junit.jupiter.api.AssertionUtils",
            "jdk.internal.",
            "java.base/jdk.internal",
            "java.base/java.lang.reflect",
            "sun.reflect.",
        )

        for line in lines:
            stripped = line.strip()

            if "UP-TO-DATE" in line or "NO-SOURCE" in line:
                continue
            if stripped.endswith("PASSED"):
                continue
            if stripped.startswith("> Task :") and "FAILED" not in stripped:
                continue

            if stripped.startswith("> Task :") and "FAILED" in stripped:
                filtered_lines.append(line)
                continue

            if " > " in line and "FAILED" in line:
                in_failure = True
                filtered_lines.append(line)
                continue

            if in_failure:
                if any(term in line for term in ("AssertionFailedError", "AssertionError", "Exception", "expected:", "but was:")):
                    filtered_lines.append(line)
                    continue
                if stripped.startswith("at "):
                    if not any(fr in line for fr in INTERNAL_FRAMES):
                        filtered_lines.append(line)
                    continue
                if stripped.startswith("> Task") or re.search(r"\d+\s+tests?\s+completed", stripped) or not stripped:
                    in_failure = False

            if re.search(r"\d+\s+tests?\s+completed", line):
                filtered_lines.append(line)
                continue

            if stripped.startswith("FAILURE: Build failed") or stripped.startswith("* What went wrong:"):
                filtered_lines.append(line)
                continue
            if stripped.startswith("Execution failed for task"):
                filtered_lines.append(line)
                continue

            if re.search(r"\.java:\d+:\s+error:", line):
                filtered_lines.append(line)

        if not filtered_lines:
            filtered_lines = [l for l in lines if "FAILED" in l or "FAILURE" in l or "error:" in l][-25:] or lines[-25:]

        body = "\n".join(filtered_lines).strip()
        return f"[AgentFixer FAIL: gradle exit {exit_code}]\n{body}"

    @staticmethod
    def _compress_ctest(text: str, exit_code: int) -> str:
        """Compress CTest / GoogleTest output.

        Suppresses passing tests by >= 90% while preserving summary.
        On failure, isolates failure frames with exact file and line accuracy.
        """
        text = strip_ansi(text)
        lines = [line.rstrip() for line in text.splitlines()]
        if exit_code == 0:
            summary_match = None
            time_match = None
            for line in lines:
                if "tests passed," in line and "tests failed out of" in line:
                    summary_match = line.strip()
                elif "Total Test time" in line:
                    time_match = line.strip()
                elif "[  PASSED  ]" in line:
                    summary_match = line.strip()

            if summary_match and time_match:
                summary_str = f"{summary_match} ({time_match})"
            elif summary_match:
                summary_str = summary_match
            else:
                summary_str = "All tests passed."
            return f"[AgentFixer PASS] ctest: {summary_str} | Individual test logs suppressed."

        # Failure isolation with exact file and line accuracy
        FRAME_RE = re.compile(r"(?P<file>.+\.(?:cpp|cc|cxx|c|h|hpp)):(?P<line>\d+):")
        SUMMARY_RE = re.compile(r"\d+%\s*tests passed,\s*\d+\s*tests failed out of\s*\d+")

        kept: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            m = FRAME_RE.search(line)
            if m:
                kept.append(line)
                i += 1
                # Capture following assertion lines until next test runner marker
                while i < len(lines):
                    sub = lines[i]
                    if (
                        any(sub.startswith(k) for k in ("[  FAILED  ]", "[ RUN      ]", "[----------]", "Test #", "The following tests FAILED:"))
                        or SUMMARY_RE.search(sub)
                    ):
                        break
                    kept.append(sub)
                    i += 1
                continue

            if "[  FAILED  ]" in line or "***Failed" in line:
                kept.append(line)
            elif "The following tests FAILED:" in line:
                kept.append(line)
                i += 1
                while i < len(lines) and (
                    lines[i].strip().startswith(tuple("0123456789"))
                    or "\t" in lines[i]
                    or lines[i].strip().endswith("(Failed)")
                ):
                    kept.append(lines[i])
                    i += 1
                continue
            elif SUMMARY_RE.search(line):
                kept.append(line)
            elif "Errors while running CTest" in line:
                kept.append(line)
            elif line.strip().startswith("[ RUN      ]"):
                lookahead_fail = False
                for j in range(i + 1, min(i + 25, len(lines))):
                    if lines[j].startswith("[       OK ]"):
                        break
                    if lines[j].startswith("[  FAILED  ]") or FRAME_RE.search(lines[j]):
                        lookahead_fail = True
                        break
                if lookahead_fail:
                    kept.append(line)
            i += 1

        if not kept:
            kept = [l for l in lines if not any(k in l for k in ("[       OK ]", "   Passed "))][-40:]

        return f"[AgentFixer FAIL: ctest exit {exit_code}]\n" + "\n".join(kept).strip()

    @staticmethod
    def _compress_nextest(text: str, exit_code: int) -> str:
        """Compress Rust cargo nextest output.

        Suppresses individual PASS lines while preserving summary.
        On failure, isolates failure frames, panics, and crate backtraces.
        """
        text = strip_ansi(text)
        lines = [line.rstrip() for line in text.splitlines()]
        if exit_code == 0:
            for line in reversed(lines):
                if "Summary [" in line or ("tests run:" in line and "passed" in line):
                    return f"[AgentFixer PASS] cargo-nextest: {line.strip()} | Individual test passes suppressed."
            return "[AgentFixer PASS] cargo-nextest: All tests passed."

        kept: list[str] = []
        skip_backtrace = False
        has_compiler_error = any("error[" in l or "error: could not compile" in l for l in lines)

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("PASS ["):
                continue
            if not has_compiler_error:
                if stripped.startswith("Compiling ") or stripped.startswith("Finished "):
                    continue
                if stripped.startswith("Starting ") and "tests across" in stripped:
                    continue

            if "stack backtrace:" in line:
                kept.append(line)
                skip_backtrace = True
                continue

            if skip_backtrace:
                if stripped.startswith("---") or stripped.startswith("Summary") or stripped.startswith("error:") or stripped.startswith("------------"):
                    skip_backtrace = False
                else:
                    if "/rustc/" in line or "core::panicking" in line or "rust_begin_unwind" in line:
                        continue
                    kept.append(line)
                    continue

            kept.append(line)

        if not kept:
            kept = [l for l in lines if not l.strip().startswith("PASS [")][-40:]

        return f"[AgentFixer FAIL: cargo-nextest exit {exit_code}]\n" + "\n".join(kept).strip()

    # Alias for compatibility with callers expecting either naming convention
    _compress_cargo_nextest = _compress_nextest
