"""PatchFuse: Fault-tolerant surgical block patcher for AI coding agents.

Eliminates repetitive patch failures caused by subtle whitespace mismatches,
indentation shifts, line ending differences, and single-character comment drift.
Uses standard library difflib and structural line alignment.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List


@dataclass
class PatchResult:
    """Outcome of a surgical patch application."""
    success: bool
    modified: bool
    strategy: str  # "exact", "whitespace_normalized", "fuzzy_alignment", "none"
    match_ratio: float
    diff: str = ""
    error: str = ""
    line_start: int = -1
    line_end: int = -1


def normalize_newlines(text: str) -> str:
    """Normalize CRLF or mixed line endings to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_trailing_ws(lines: List[str]) -> List[str]:
    """Strip trailing whitespace from each line."""
    return [l.rstrip() for l in lines]


class PatchFuse:
    """Surgical patcher supporting exact, normalized, and fuzzy block replacement."""

    def __init__(self, fuzzy_threshold: float = 0.85):
        self.fuzzy_threshold = fuzzy_threshold

    def apply_patch(
        self,
        file_path: str | Path,
        target: str,
        replacement: str,
        dry_run: bool = False,
    ) -> PatchResult:
        """Apply a replacement block to file_path with multi-tier fallback."""
        path = Path(file_path)
        if not path.exists():
            return PatchResult(
                success=False,
                modified=False,
                strategy="none",
                match_ratio=0.0,
                error=f"File not found: {file_path}",
            )

        try:
            original_content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                original_content = path.read_text(encoding="latin-1")
            except Exception as e:
                return PatchResult(
                    success=False,
                    modified=False,
                    strategy="none",
                    match_ratio=0.0,
                    error=f"Failed to read {file_path}: {e}",
                )

        result, patched_content = self.patch_text(original_content, target, replacement)

        if result.success and not dry_run and result.modified:
            path.write_text(patched_content, encoding="utf-8")

        return result

    def patch_text(
        self,
        content: str,
        target: str,
        replacement: str,
    ) -> Tuple[PatchResult, str]:
        """Patch in-memory string content using progressive matching strategies."""
        norm_content = normalize_newlines(content)
        norm_target = normalize_newlines(target)
        norm_replacement = normalize_newlines(replacement)

        # 1. Tier 1: Exact substring match
        if norm_target in norm_content:
            occurrences = norm_content.count(norm_target)
            if occurrences == 1:
                idx = norm_content.find(norm_target)
                line_start = norm_content[:idx].count("\n") + 1
                line_end = line_start + norm_target.count("\n")
                new_content = norm_content.replace(norm_target, norm_replacement, 1)
                diff = self._make_diff(norm_content, new_content)
                return (
                    PatchResult(
                        success=True,
                        modified=True,
                        strategy="exact",
                        match_ratio=1.0,
                        diff=diff,
                        line_start=line_start,
                        line_end=line_end,
                    ),
                    new_content,
                )

        content_lines = norm_content.splitlines(keepends=True)
        target_lines = norm_target.splitlines(keepends=True)

        if not target_lines:
            return (
                PatchResult(
                    success=False,
                    modified=False,
                    strategy="none",
                    match_ratio=0.0,
                    error="Target text is empty.",
                ),
                content,
            )

        # 2. Tier 2: Whitespace-normalized line matching (trailing whitespace & indentation shift)
        tier2_res, patched_t2 = self._match_normalized(content_lines, target_lines, norm_replacement)
        if tier2_res.success:
            return tier2_res, patched_t2

        # 3. Tier 3: Fuzzy window search (Levenshtein sequence alignment)
        tier3_res, patched_t3 = self._match_fuzzy(content_lines, target_lines, norm_replacement)
        if tier3_res.success:
            return tier3_res, patched_t3

        return (
            PatchResult(
                success=False,
                modified=False,
                strategy="none",
                match_ratio=0.0,
                error="Target block could not be matched even with fuzzy tolerance.",
            ),
            content,
        )

    def _match_normalized(
        self,
        content_lines: List[str],
        target_lines: List[str],
        replacement: str,
    ) -> Tuple[PatchResult, str]:
        """Try matching by stripping trailing whitespace and calculating indentation delta."""
        stripped_target = [l.strip() for l in target_lines if l.strip()]
        if not stripped_target:
            return PatchResult(success=False, modified=False, strategy="none", match_ratio=0.0), ""

        target_len = len(target_lines)
        num_content = len(content_lines)

        for i in range(num_content - target_len + 1):
            window = content_lines[i : i + target_len]
            # Compare non-empty lines with stripped whitespace
            window_stripped = [l.strip() for l in window if l.strip()]
            if window_stripped == stripped_target:
                # Found normalized match! Compute indentation difference
                orig_lead = self._get_indent(window[0])
                target_lead = self._get_indent(target_lines[0])
                indent_delta = len(orig_lead) - len(target_lead)

                adjusted_replacement = self._adjust_indent(replacement, indent_delta)
                rep_lines = (
                    [adjusted_replacement]
                    if not adjusted_replacement.endswith("\n")
                    else [adjusted_replacement]
                )
                if not rep_lines[0].endswith("\n"):
                    rep_lines[0] += "\n"

                new_lines = content_lines[:i] + rep_lines + content_lines[i + target_len :]
                orig_text = "".join(content_lines)
                new_text = "".join(new_lines)
                diff = self._make_diff(orig_text, new_text)

                return (
                    PatchResult(
                        success=True,
                        modified=True,
                        strategy="whitespace_normalized",
                        match_ratio=0.98,
                        diff=diff,
                        line_start=i + 1,
                        line_end=i + target_len,
                    ),
                    new_text,
                )

        return PatchResult(success=False, modified=False, strategy="none", match_ratio=0.0), ""

    def _match_fuzzy(
        self,
        content_lines: List[str],
        target_lines: List[str],
        replacement: str,
    ) -> Tuple[PatchResult, str]:
        """Sliding window fuzzy matching using difflib SequenceMatcher."""
        target_len = len(target_lines)
        target_str = "".join(target_lines).strip()
        num_content = len(content_lines)

        best_ratio = 0.0
        best_idx = -1

        # Search windows of length target_len - 1 to target_len + 2
        for w_len in (target_len, target_len - 1, target_len + 1):
            if w_len <= 0:
                continue
            for i in range(num_content - w_len + 1):
                window_str = "".join(content_lines[i : i + w_len]).strip()
                ratio = difflib.SequenceMatcher(None, target_str, window_str).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_idx = i
                    best_w_len = w_len

        if best_ratio >= self.fuzzy_threshold and best_idx != -1:
            orig_lead = self._get_indent(content_lines[best_idx])
            target_lead = self._get_indent(target_lines[0])
            indent_delta = len(orig_lead) - len(target_lead)

            adjusted_replacement = self._adjust_indent(replacement, indent_delta)
            if not adjusted_replacement.endswith("\n"):
                adjusted_replacement += "\n"

            new_lines = (
                content_lines[:best_idx]
                + [adjusted_replacement]
                + content_lines[best_idx + best_w_len :]
            )
            orig_text = "".join(content_lines)
            new_text = "".join(new_lines)
            diff = self._make_diff(orig_text, new_text)

            return (
                PatchResult(
                    success=True,
                    modified=True,
                    strategy="fuzzy_alignment",
                    match_ratio=round(best_ratio, 3),
                    diff=diff,
                    line_start=best_idx + 1,
                    line_end=best_idx + best_w_len,
                ),
                new_text,
            )

        return PatchResult(
            success=False,
            modified=False,
            strategy="none",
            match_ratio=round(best_ratio, 3),
            error=f"Best fuzzy match ratio ({best_ratio:.2f}) below threshold ({self.fuzzy_threshold})",
        ), ""

    @staticmethod
    def _get_indent(line: str) -> str:
        return line[: len(line) - len(line.lstrip())]

    @staticmethod
    def _adjust_indent(text: str, delta: int) -> str:
        if delta == 0:
            return text
        lines = text.splitlines(keepends=True)
        adjusted = []
        for line in lines:
            if not line.strip():
                adjusted.append(line)
            elif delta > 0:
                adjusted.append((" " * delta) + line)
            else:
                remove = min(-delta, len(line) - len(line.lstrip()))
                adjusted.append(line[remove:])
        return "".join(adjusted)

    @staticmethod
    def _make_diff(orig: str, modified: str) -> str:
        orig_lines = orig.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile="original",
            tofile="patched",
        )
        return "".join(diff)
