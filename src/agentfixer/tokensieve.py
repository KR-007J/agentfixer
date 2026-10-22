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
    for raw_line in text.splitlines():
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
        if "pytest" in cmd_lower or "python -m unittest" in cmd_lower or "pytest" in cleaned.lower():
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
