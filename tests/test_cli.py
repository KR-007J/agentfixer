"""Unit tests for AgentFixer CLI interface."""

from agentfixer.cli import main


def test_cli_demo():
    code = main(["demo"])
    assert code == 0


def test_cli_audit():
    code = main(["audit"])
    assert code == 0


def test_cli_run_simple_echo(capsys):
    code = main(["run", "--quiet", "--", "echo", "test_output"])
    assert code == 0
    captured = capsys.readouterr()
    assert "test_output" in captured.out
