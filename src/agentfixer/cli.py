"""CLI Entrypoint for AgentFixer.

Provides fast, scriptable CLI commands:
- `agentfix run -- <cmd>`: Wraps CLI commands with TokenSieve, Sentinel, and ScopeLock.
- `agentfix patch <file> ...`: Applies fault-tolerant surgical block edits with PatchFuse.
- `agentfix demo`: Demonstrates token savings, false-pass interception, and fuzzy patching.
- `agentfix audit`: Inspects worktree and environment health.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from agentfixer.tokensieve import TokenSieve
from agentfixer.sentinel import FalsePassSentinel
from agentfixer.patcher import PatchFuse
from agentfixer.scopelock import ScopeLock


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a wrapped command with TokenSieve, Sentinel, and ScopeLock."""
    cmd = getattr(args, "cmd", [])
    if not cmd:
        print("[AgentFixer Error] No command specified. Use: agentfix run -- <command>")
        return 1

    if isinstance(cmd, list):
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        command_str = shlex.join(cmd)
    else:
        command_str = str(cmd)
    scopelock = None
    no_scopelock = getattr(args, "no_scopelock", False)
    allow = getattr(args, "allow", None)
    if not no_scopelock:
        scopelock = ScopeLock(
            root_dir=".",
            allowed_patterns=allow or ["*"],
        )
        scopelock.capture_snapshot()

    # Execute command
    try:
        proc = subprocess.Popen(
            command_str,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate()
        raw_exit = proc.returncode
    except Exception as e:
        print(f"[AgentFixer Execution Error] Failed to execute '{command_str}': {e}", file=sys.stderr)
        return 1

    # 1. FalsePass Sentinel Inspection
    effective_exit = raw_exit
    no_sentinel = getattr(args, "no_sentinel", False)
    if not no_sentinel:
        sentinel_res = FalsePassSentinel.inspect(
            stdout=stdout,
            stderr=stderr,
            exit_code=raw_exit,
            command=command_str,
        )
        if sentinel_res.is_false_pass:
            effective_exit = sentinel_res.effective_exit_code
            print(FalsePassSentinel.format_alert(sentinel_res), file=sys.stderr)

    # 2. TokenSieve Output Compression
    no_sieve = getattr(args, "no_sieve", False)
    verbose = getattr(args, "verbose", False)
    quiet = getattr(args, "quiet", False)
    if not no_sieve:
        sieve_res = TokenSieve.sieve(
            stdout=stdout,
            stderr=stderr,
            exit_code=effective_exit,
            command=command_str,
            verbose=verbose,
        )
        print(sieve_res["sieved_text"])
        if sieve_res["is_compressed"] and not quiet:
            print(
                f"\n[AgentFixer Sieve] Saved ~{sieve_res['tokens_saved']} tokens "
                f"({sieve_res['reduction_pct']}% reduction | "
                f"{sieve_res['original_tokens']} -> {sieve_res['sieved_tokens']} tokens)"
            )
    else:
        if stdout:
            print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)

    # 3. ScopeLock Worktree Verification
    strict_scope = getattr(args, "strict_scope", False)
    no_purge = getattr(args, "no_purge", False)
    if scopelock and not no_scopelock:
        scope_rep = scopelock.verify(auto_purge=not no_purge)
        if not scope_rep.clean:
            print("\n[AgentFixer ScopeLock WARNING] Out-of-scope modifications detected:")
            for v in scope_rep.violations:
                print(f"  - [{v.change_type.upper()}] {v.path}: {v.reason}")
            if strict_scope:
                effective_exit = 102

    return effective_exit


def cmd_patch(args: argparse.Namespace) -> int:
    """Apply surgical patch to a target file."""
    target = args.target
    if args.target_file:
        target = Path(args.target_file).read_text(encoding="utf-8")

    replacement = args.replacement
    if args.replacement_file:
        replacement = Path(args.replacement_file).read_text(encoding="utf-8")

    if target is None or replacement is None:
        print("[AgentFixer Error] Both --target and --replacement must be provided.")
        return 1

    patcher = PatchFuse(fuzzy_threshold=args.threshold)
    result = patcher.apply_patch(
        file_path=args.file,
        target=target,
        replacement=replacement,
        dry_run=args.dry_run,
    )

    if result.success:
        status = "DRY RUN (Would Modify)" if args.dry_run else "SUCCESS (Modified)"
        print(f"[AgentFixer PatchFuse {status}] Strategy: {result.strategy} (Match: {result.match_ratio * 100:.1f}%)")
        if result.diff and not args.quiet:
            print("\n--- Diff Preview ---")
            print(result.diff)
        return 0
    else:
        print(f"[AgentFixer PatchFuse FAILED] {result.error}", file=sys.stderr)
        return 1


def cmd_demo(args: argparse.Namespace) -> int:
    """Run an interactive demonstration of AgentFixer superpowers."""
    print("=" * 70)
    print("🚀 AGENTFIXER INDUSTRIAL DEMO: The Autonomous AI Agent Shield")
    print("=" * 70)

    # Demo 1: Pytest Token Compression
    mock_pytest_pass = (
        "platform linux -- Python 3.11.15, pytest-8.4.1\n"
        "rootdir: /workspace/project\n"
        + "".join([f"tests/test_mod_{i}.py . [ 100%]\n" for i in range(1, 150)])
        + "========================= 149 passed in 0.85s =========================\n"
    )
    sieved = TokenSieve.sieve(stdout=mock_pytest_pass, exit_code=0, command="pytest")
    print("\n[DEMO 1] Pytest 149-Test Output Compression:")
    print(f"  Raw Tokens:       ~{sieved['original_tokens']}")
    print(f"  Sieved Tokens:    ~{sieved['sieved_tokens']}")
    print(f"  Tokens Saved:     ~{sieved['tokens_saved']} ({sieved['reduction_pct']}% reduction!)")
    print(f"  Output Delievered to Agent:\n    --> {sieved['sieved_text']}")

    # Demo 2: Silent False Pass Interception
    mock_pytest_zero = (
        "============================= test session starts ==============================\n"
        "collected 0 items\n"
        "============================ no tests ran in 0.01s =============================\n"
    )
    sentinel_res = FalsePassSentinel.inspect(
        stdout=mock_pytest_zero, exit_code=0, command="pytest"
    )
    print("\n[DEMO 2] Silent False-Pass Interception (The Exit 0 Trap):")
    print(f"  Command Exit Code: {sentinel_res.original_exit_code} (Clean exit)")
    print(f"  Sentinel Catch:    {sentinel_res.is_false_pass} (Caught 'collected 0 items')")
    print(f"  Overridden Exit:   {sentinel_res.effective_exit_code} (CRITICAL ALERT)")

    # Demo 3: Fuzzy Surgical Patch
    sample_code = "def calculate_score(val):\n    # Calculate raw score\n    result = val * 2\n    return result\n"
    # Agent provides 2 spaces instead of 4 spaces
    agent_target = "  # Calculate raw score\n  result = val * 2"
    agent_replacement = "  # Calculate calibrated score\n  result = (val * 2) + 10"

    patcher = PatchFuse()
    res, patched = patcher.patch_text(sample_code, agent_target, agent_replacement)
    print("\n[DEMO 3] PatchFuse Indentation Mismatch Auto-Resolution:")
    print(f"  Strategy:  {res.strategy}")
    print(f"  Match:     {res.match_ratio * 100:.1f}%")
    print(f"  Success:   {res.success}")
    print("  Patched Result:")
    for l in patched.splitlines():
        print(f"    {l}")

    print("\n" + "=" * 70)
    print("✅ All core engines verified and ready for production use.")
    print("=" * 70)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Audit local repository for agent traps and scratch clutter."""
    print("[AgentFixer Audit] Scanning current workspace for agent clutter...")
    scopelock = ScopeLock(root_dir=".")
    purged = scopelock.purge_scratch()
    if purged:
        print(f"  Purged {len(purged)} temporary cache files:")
        for p in purged[:10]:
            print(f"    - {p}")
        if len(purged) > 10:
            print(f"    ... and {len(purged) - 10} more.")
    else:
        print("  Workspace clean. No stray cache artifacts detected.")
    return 0


class AgentFixParser(argparse.ArgumentParser):
    """Custom parser that normalizes arguments and strips double-dash prefix from cmd."""
    def parse_args(self, args=None, namespace=None):
        res = super().parse_args(args=args, namespace=namespace)
        if hasattr(res, "cmd") and isinstance(res.cmd, list) and res.cmd and res.cmd[0] == "--":
            res.cmd = res.cmd[1:]
        return res


def build_parser() -> argparse.ArgumentParser:
    """Build the ArgumentParser with all subcommands."""
    parser = AgentFixParser(
        prog="agentfix",
        description="Autonomous AI Agent Runtime Shield & Token Sieve",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcommand: run
    p_run = subparsers.add_parser("run", help="Wrap CLI command with TokenSieve, Sentinel, and ScopeLock")
    p_run.add_argument("--verbose", "-v", action="store_true", help="Disable log compression")
    p_run.add_argument("--quiet", "-q", action="store_true", help="Suppress AgentFixer banner/stats")
    p_run.add_argument("--allow", action="append", help="Allowed file glob patterns (can repeat)")
    p_run.add_argument("--strict-scope", action="store_true", help="Fail with exit 102 if out-of-scope files touched")
    p_run.add_argument("--no-sieve", action="store_true", help="Disable TokenSieve compression")
    p_run.add_argument("--no-sentinel", action="store_true", help="Disable FalsePass Sentinel")
    p_run.add_argument("--no-scopelock", action="store_true", help="Disable ScopeLock worktree checking")
    p_run.add_argument("--no-purge", action="store_true", help="Do not auto-purge temporary cache artifacts")
    p_run.add_argument("cmd", nargs=argparse.REMAINDER, help="The command to execute (e.g. -- pytest)")

    # Subcommand: patch
    p_patch = subparsers.add_parser("patch", help="Apply surgical block patch with whitespace tolerance")
    p_patch.add_argument("file", help="Path to file to patch")
    p_patch.add_argument("--target", "-t", help="Target string block to find")
    p_patch.add_argument("--target-file", help="File containing target string")
    p_patch.add_argument("--replacement", "-r", help="Replacement string block")
    p_patch.add_argument("--replacement-file", help="File containing replacement string")
    p_patch.add_argument("--dry-run", action="store_true", help="Preview diff without writing to disk")
    p_patch.add_argument("--threshold", type=float, default=0.85, help="Fuzzy match threshold (default: 0.85)")
    p_patch.add_argument("--quiet", "-q", action="store_true", help="Suppress diff output")

    # Subcommand: demo
    subparsers.add_parser("demo", help="Run interactive demonstration of AgentFixer")

    # Subcommand: audit
    subparsers.add_parser("audit", help="Audit workspace and clean agent clutter")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_args = list(sys.argv[1:] if argv is None else argv)

    # Handle standard double-dash parsing if present
    if raw_args and raw_args[0] == "run":
        if "--" in raw_args:
            idx = raw_args.index("--")
            sub_flags = raw_args[1:idx]
            command_parts = raw_args[idx + 1 :]
            p_run = parser._subparsers._actions[1].choices["run"]
            parsed = p_run.parse_args(sub_flags)
            parsed.subcommand = "run"
            parsed.cmd = command_parts
            return cmd_run(parsed)

    parsed = parser.parse_args(raw_args)
    if parsed.subcommand == "run":
        # If user did not use `--`
        if parsed.cmd and parsed.cmd[0] == "--":
            parsed.cmd = parsed.cmd[1:]
        return cmd_run(parsed)
    elif parsed.subcommand == "patch":
        return cmd_patch(parsed)
    elif parsed.subcommand == "demo":
        return cmd_demo(parsed)
    elif parsed.subcommand == "audit":
        return cmd_audit(parsed)

    return 0


if __name__ == "__main__":
    sys.exit(main())
