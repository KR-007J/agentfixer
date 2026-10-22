"""ScopeLock: Anti-Collateral Damage and Worktree Sentinel for AI Coding Agents.

Ensures the agent strictly modifies files within allowed boundaries, prevents
unintended configuration corruption, and auto-purges stray temporary files.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set, Dict, Optional


@dataclass
class ScopeViolation:
    """Represents an unauthorized file modification or creation."""
    path: str
    change_type: str  # "modified", "created", "deleted"
    reason: str


@dataclass
class ScopeReport:
    """Summary of worktree state before and after command execution."""
    clean: bool
    violations: List[ScopeViolation] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    purged_artifacts: List[str] = field(default_factory=list)


# Commonly littered temporary artifacts that should be auto-purged
SCRATCH_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
    "npm-debug.log*",
    "yarn-debug.log*",
    "yarn-error.log*",
    "*.tmp",
    "*.scratch",
    "*.log",
    "*_dump.log",
    "*temp_scratch*",
]


class _PurgeScratchDescriptor:
    """Descriptor enabling ScopeLock.purge_scratch(...) on both class and instances."""
    def __get__(self, instance, owner=None):
        if instance is None:
            def _class_purge(*args, workspace: Optional[str | Path] = None, **kwargs) -> List[str]:
                target = workspace or (args[0] if args else None) or "."
                return ScopeLock._do_purge_scratch(target)
            return _class_purge
        else:
            def _instance_purge(*args, workspace: Optional[str | Path] = None, **kwargs) -> List[str]:
                target = workspace or (args[0] if args else None) or instance.root
                return ScopeLock._do_purge_scratch(target)
            return _instance_purge


class ScopeLock:
    """Guards worktree boundaries against agent hallucinations and scope creep."""

    def __init__(
        self,
        root_dir: str | Path = ".",
        allowed_patterns: Optional[List[str]] = None,
        forbidden_patterns: Optional[List[str]] = None,
        target_files: Optional[List[str]] = None,
    ):
        self.root = Path(root_dir).resolve()
        self.allowed_patterns = target_files or allowed_patterns or ["*"]
        self.forbidden_patterns = forbidden_patterns or [
            ".git/*",
            ".env*",
            "id_rsa*",
            "*.pem",
            "package-lock.json",
            "poetry.lock",
        ]
        self.pre_snapshot: Dict[str, str] = {}

    def capture_snapshot(self) -> Dict[str, str]:
        """Capture SHA-256 fingerprint of files in the worktree."""
        snapshot = {}
        for root, dirs, files in os.walk(self.root):
            # Skip .git directory
            if ".git" in dirs:
                dirs.remove(".git")
            for f in files:
                full_path = Path(root) / f
                try:
                    rel = str(full_path.relative_to(self.root))
                    snapshot[rel] = self._hash_file(full_path)
                except (PermissionError, FileNotFoundError):
                    continue
        self.pre_snapshot = snapshot
        return snapshot

    def verify(self, auto_purge: bool = True) -> ScopeReport:
        """Compare current worktree against pre_snapshot and enforce allowed scope."""
        post_snapshot = {}
        purged = []

        if auto_purge:
            purged = self.purge_scratch()

        for root, dirs, files in os.walk(self.root):
            if ".git" in dirs:
                dirs.remove(".git")
            for f in files:
                full_path = Path(root) / f
                try:
                    rel = str(full_path.relative_to(self.root))
                    post_snapshot[rel] = self._hash_file(full_path)
                except (PermissionError, FileNotFoundError):
                    continue

        violations = []
        modified = []

        # Check modified and created files
        for rel_path, new_hash in post_snapshot.items():
            old_hash = self.pre_snapshot.get(rel_path)
            if old_hash is None:
                # File created
                modified.append(rel_path)
                violation = self._check_path_allowed(rel_path, "created")
                if violation:
                    violations.append(violation)
            elif old_hash != new_hash:
                # File modified
                modified.append(rel_path)
                violation = self._check_path_allowed(rel_path, "modified")
                if violation:
                    violations.append(violation)

        # Check deleted files
        for rel_path in self.pre_snapshot:
            if rel_path not in post_snapshot:
                modified.append(rel_path)
                violation = self._check_path_allowed(rel_path, "deleted")
                if violation:
                    violations.append(violation)

        clean = len(violations) == 0
        return ScopeReport(
            clean=clean,
            violations=violations,
            modified_files=sorted(list(set(modified))),
            purged_artifacts=purged,
        )

    purge_scratch = _PurgeScratchDescriptor()

    @staticmethod
    def _do_purge_scratch(target_dir: str | Path) -> List[str]:
        """Purge known temporary cache files and directories."""
        target_root = Path(target_dir).resolve()
        purged = []
        for root, dirs, files in os.walk(target_root, topdown=False):
            if ".git" in dirs:
                dirs.remove(".git")
            for d in list(dirs):
                if any(fnmatch.fnmatch(d, pat) for pat in SCRATCH_PATTERNS):
                    dir_path = Path(root) / d
                    try:
                        shutil.rmtree(dir_path)
                        purged.append(str(dir_path.relative_to(target_root)))
                        dirs.remove(d)
                    except Exception:
                        pass
            for f in files:
                if any(fnmatch.fnmatch(f, pat) for pat in SCRATCH_PATTERNS):
                    file_path = Path(root) / f
                    try:
                        file_path.unlink()
                        purged.append(str(file_path.relative_to(target_root)))
                    except Exception:
                        pass
        return purged

    def detect_violations(self, workspace: Optional[str | Path] = None) -> List[ScopeViolation]:
        """Directly scan workspace directory for files matching forbidden or unallowed patterns."""
        target_root = Path(workspace or self.root).resolve()
        violations = []
        for root, dirs, files in os.walk(target_root):
            if ".git" in dirs:
                dirs.remove(".git")
            for f in files:
                full_path = Path(root) / f
                rel_path = str(full_path.relative_to(target_root))
                v = self._check_path_allowed(rel_path, "modified")
                if v:
                    violations.append(v)
        return violations

    def _check_path_allowed(self, rel_path: str, change: str) -> Optional[ScopeViolation]:
        # Check forbidden first
        for pat in self.forbidden_patterns:
            if fnmatch.fnmatch(rel_path, pat):
                return ScopeViolation(
                    path=rel_path,
                    change_type=change,
                    reason=f"Path matches forbidden pattern '{pat}'",
                )

        # Check allowed
        is_allowed = any(fnmatch.fnmatch(rel_path, pat) for pat in self.allowed_patterns)
        if not is_allowed:
            return ScopeViolation(
                path=rel_path,
                change_type=change,
                reason=f"Path does not match any allowed pattern {self.allowed_patterns}",
            )
        return None

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
