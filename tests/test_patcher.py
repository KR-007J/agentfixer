"""Unit tests for PatchFuse fault-tolerant surgical block patcher."""

import tempfile
from pathlib import Path
from agentfixer.patcher import PatchFuse, PatchResult


def test_patch_exact_match():
    content = "def foo():\n    return 42\n"
    patcher = PatchFuse()
    res, patched = patcher.patch_text(content, "return 42", "return 100")
    assert res.success is True
    assert res.strategy == "exact"
    assert "return 100" in patched


def test_patch_whitespace_normalized_indent():
    # File uses 4 spaces
    content = "class Greeter:\n    def greet(self):\n        msg = 'hello'\n        return msg\n"
    # Agent provides 2 spaces
    target = "  msg = 'hello'\n  return msg"
    replacement = "  msg = 'hello world'\n  return msg.upper()"

    patcher = PatchFuse()
    res, patched = patcher.patch_text(content, target, replacement)
    assert res.success is True
    assert res.strategy == "whitespace_normalized"
    # Verify the patched text preserved the original 8-space indentation!
    assert "        msg = 'hello world'" in patched
    assert "        return msg.upper()" in patched


def test_patch_fuzzy_sequence_alignment():
    # Original has a slight comment drift
    content = "def compute(a, b):\n    # compute the sum of values\n    val = a + b\n    return val\n"
    # Agent target had typo in comment
    target = "# compute sum of values\nval = a + b"
    replacement = "# compute sum and product\nval = (a + b) * 2"

    patcher = PatchFuse(fuzzy_threshold=0.75)
    res, patched = patcher.patch_text(content, target, replacement)
    assert res.success is True
    assert res.strategy == "fuzzy_alignment"
    assert "val = (a + b) * 2" in patched


def test_patch_file_on_disk():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".py") as tf:
        tf.write("x = 10\ny = 20\n")
        temp_path = tf.name

    try:
        patcher = PatchFuse()
        res = patcher.apply_patch(temp_path, "x = 10", "x = 99")
        assert res.success is True
        content = Path(temp_path).read_text()
        assert "x = 99" in content
    finally:
        Path(temp_path).unlink(missing_ok=True)
