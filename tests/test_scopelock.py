"""Unit tests for ScopeLock boundary enforcer."""

import tempfile
from pathlib import Path
from agentfixer.scopelock import ScopeLock


def test_scopelock_detects_forbidden_file_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')")

        lock = ScopeLock(
            root_dir=tmp_path,
            allowed_patterns=["src/*"],
            forbidden_patterns=[".env*", "secrets/*"],
        )
        lock.capture_snapshot()

        # Agent creates a forbidden .env file
        (tmp_path / ".env").write_text("API_KEY=secret123")

        rep = lock.verify(auto_purge=False)
        assert rep.clean is False
        assert any(v.path == ".env" for v in rep.violations)


def test_scopelock_purges_scratch_artifacts():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "app.cpython-311.pyc").write_text("binary")
        (tmp_path / "test.tmp").write_text("scratch")

        lock = ScopeLock(root_dir=tmp_path)
        purged = lock.purge_scratch()

        assert len(purged) > 0
        assert not cache_dir.exists()
        assert not (tmp_path / "test.tmp").exists()
