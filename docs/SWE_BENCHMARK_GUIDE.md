# SWE-bench & Agent Harness Integration Guide

This guide shows how to drop `AgentFixer` into any agent evaluation harness, Docker container, or developer agent (Claude Code, Google Antigravity, SWE-bench runner) with zero configuration.

---

## 1. Quick Installation (Zero Dependencies)

`AgentFixer` requires Python 3.10+ and standard library only. No external pip dependencies needed.

```bash
git clone https://github.com/KR-007J/agentfixer.git
cd agentfixer
pip install -e .
```

Or copy the single `src/agentfixer` directory directly into your harness sandbox.

---

## 2. Using with Claude Code / Antigravity

Add `agentfix` as a shell command wrapper in your system prompt or developer instructions:

```markdown
When running test suites or build commands, always prefix with `agentfix run --`:
- Example: `agentfix run -- pytest`
- Example: `agentfix run -- npm test`
- Example: `agentfix run -- cargo test`
```

### Benefits:
- **Reduces token consumption by 90%**: Prevents Claude Code / Antigravity from hitting context compaction.
- **Prevents Instruction Amnesia**: Keeps system instructions in active context for 5x more turns.
- **Catches False Passes**: Immediately warns if 0 tests were collected.

---

## 3. Integrating with SWE-bench Docker Harness

In your SWE-bench evaluation script (e.g. `eval_repo.py`), wrap the test execution invocation:

```python
import subprocess
from agentfixer import TokenSieve, FalsePassSentinel

def run_agent_test(command: str) -> dict:
    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
    )
    
    # 1. Inspect for false pass
    sentinel_res = FalsePassSentinel.inspect(
        stdout=proc.stdout,
        stderr=proc.stderr,
        exit_code=proc.returncode,
        command=command
    )
    effective_code = sentinel_res.effective_exit_code
    
    # 2. Sieve tokens
    sieved = TokenSieve.sieve(
        stdout=proc.stdout,
        stderr=proc.stderr,
        exit_code=effective_code,
        command=command
    )
    
    return {
        "exit_code": effective_code,
        "is_false_pass": sentinel_res.is_false_pass,
        "feedback_to_agent": sieved["sieved_text"],
        "tokens_saved": sieved["tokens_saved"]
    }
```

---

## 4. Programmatic Patching via PatchFuse

In custom agent environments where tool-call edits fail due to whitespace mismatches:

```python
from agentfixer import PatchFuse

patcher = PatchFuse(fuzzy_threshold=0.85)
result = patcher.apply_patch(
    file_path="src/utils.py",
    target="""    def calculate(x):
        return x * 2""",
    replacement="""    def calculate(x):
        return (x * 2) + 1""",
    dry_run=False
)

if result.success:
    print(f"Patched via {result.strategy} (Match: {result.match_ratio*100:.1f}%)")
else:
    print(f"Patch failed: {result.error}")
```
