"""Unit tests for FalsePass Sentinel."""

from agentfixer.sentinel import FalsePassSentinel, SentinelResult


def test_sentinel_normal_pass():
    stdout = "========================= 10 passed in 0.12s ========================="
    res = FalsePassSentinel.inspect(stdout=stdout, exit_code=0, command="pytest")
    assert res.is_false_pass is False
    assert res.effective_exit_code == 0


def test_sentinel_normal_failure():
    stdout = "========================= 1 failed in 0.12s ========================="
    res = FalsePassSentinel.inspect(stdout=stdout, exit_code=1, command="pytest")
    assert res.is_false_pass is False
    assert res.effective_exit_code == 1


def test_sentinel_intercepts_pytest_zero_collection():
    stdout = "collected 0 items\nno tests ran in 0.01s"
    res = FalsePassSentinel.inspect(stdout=stdout, exit_code=0, command="pytest")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101
    assert "Pytest collected 0 test items." in res.reason


def test_sentinel_intercepts_jest_zero_tests():
    stdout = "No tests found, exiting with code 0"
    res = FalsePassSentinel.inspect(stdout=stdout, exit_code=0, command="npm test")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


def test_sentinel_intercepts_cargo_zero_tests():
    stdout = "running 0 tests\ntest result: ok. 0 passed; 0 failed"
    res = FalsePassSentinel.inspect(stdout=stdout, exit_code=0, command="cargo test")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


def test_sentinel_intercepts_empty_test_output():
    res = FalsePassSentinel.inspect(stdout="", exit_code=0, command="pytest")
    assert res.is_false_pass is True
    assert res.effective_exit_code == 101


def test_sentinel_format_alert():
    stdout = "collected 0 items\n"
    res = FalsePassSentinel.inspect(stdout=stdout, exit_code=0, command="pytest")
    alert = FalsePassSentinel.format_alert(res)
    assert "[AgentFixer CRITICAL FALSE-PASS INTERCEPTED]" in alert
    assert "Overridden: 101" in alert
