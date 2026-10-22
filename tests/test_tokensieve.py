"""Unit tests for TokenSieve CLI output compression."""

from agentfixer.tokensieve import TokenSieve, strip_ansi, estimate_tokens


def test_strip_ansi_codes():
    raw = "\x1b[32mPASS\x1b[0m \x1b[1mtests/test_foo.py\x1b[0m"
    clean = strip_ansi(raw)
    assert clean == "PASS tests/test_foo.py"


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") == 3
    assert estimate_tokens("a" * 100) == 25


def test_sieve_pytest_pass():
    raw_output = (
        "platform linux -- Python 3.11.15, pytest-8.4.1\n"
        "rootdir: /repo\n"
        "tests/test_1.py ... [ 50%]\n"
        "tests/test_2.py ... [100%]\n"
        "========================= 6 passed in 0.05s =========================\n"
    )
    result = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="pytest")
    assert result["is_compressed"] is True
    assert "6 passed in 0.05s" in result["sieved_text"]
    assert "[AgentFixer PASS]" in result["sieved_text"]
    assert result["reduction_pct"] > 50.0


def test_sieve_pytest_failure_preserves_traceback():
    raw_output = (
        "platform linux -- Python 3.11.15, pytest-8.4.1\n"
        "tests/test_1.py .F [100%]\n"
        "=================================== FAILURES ===================================\n"
        "_________________________________ test_divide __________________________________\n"
        "def test_divide():\n"
        ">       assert 1 / 0 == 1\n"
        "E       ZeroDivisionError: division by zero\n"
        "tests/test_1.py:12: ZeroDivisionError\n"
        "=========================== 1 failed, 1 passed in 0.08s ========================\n"
    )
    result = TokenSieve.sieve(stdout=raw_output, exit_code=1, command="pytest")
    assert "[AgentFixer FAIL: pytest exit 1]" in result["sieved_text"]
    assert "ZeroDivisionError: division by zero" in result["sieved_text"]
    assert "assert 1 / 0 == 1" in result["sieved_text"]


def test_sieve_jest_pass():
    raw_output = (
        "PASS src/sum.test.js\n"
        "PASS src/sub.test.js\n"
        "Test Suites: 2 passed, 2 total\n"
        "Tests:       10 passed, 10 total\n"
        "Snapshots:   0 total\n"
        "Time:        1.25s\n"
    )
    result = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="npm test")
    assert result["is_compressed"] is True
    assert "10 passed, 10 total" in result["sieved_text"]


def test_sieve_cargo_pass():
    raw_output = (
        "   Compiling my_crate v0.1.0\n"
        "    Finished test [unoptimized + debuginfo] target(s) in 0.42s\n"
        "     Running unittests src/lib.rs\n"
        "test tests::test_add ... ok\n"
        "test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s\n"
    )
    result = TokenSieve.sieve(stdout=raw_output, exit_code=0, command="cargo test")
    assert "[AgentFixer PASS] cargo: test result: ok." in result["sieved_text"]


def test_sieve_git_status():
    raw = "On branch main\nnothing to commit, working tree clean\n"
    res = TokenSieve.sieve(stdout=raw, exit_code=0, command="git status")
    assert res["sieved_text"] == "[AgentFixer] git: Working tree clean."
