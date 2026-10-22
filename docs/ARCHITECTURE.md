# AgentFixer Architecture & Theoretical Foundations

**Author:** Krish Joshi (@KR-007J)  
**Affiliation:** Autonomous AI Systems & Eval Lab  
**Companion System:** [AgentTrace](https://github.com/KR-007J/ai-systems-eval-portfolio) (Trajectory Observability & SQS Auditing)

---

## 1. The Core Problem: Context Entropy & The Collapse Horizon

Autonomous AI software engineering agents (Claude Code, Google Antigravity, OpenAI Codex, SWE-bench runners) interact with host systems through terminal executions and tool calling. In multi-turn trajectories, the primary bottleneck to agent reasoning is not parameter scale, but **Context Entropy**:

$$\text{Effective Reasoning Capacity} \propto \frac{1}{\text{Entropy}(\mathcal{C})}$$

Where $\mathcal{C}$ is the agent's active context window. 

When an agent executes `npm test` or `pytest`, unshielded CLI output floods the context with $3,000$ to $10,000$ tokens per turn. Over an 8-turn troubleshooting session:

$$\text{CLI Token Load} = \sum_{t=1}^{8} \text{Tokens}(\text{ToolOutput}_t) \approx 48,000 \text{ tokens}$$

This triggers **Harness Forced Context Compaction**:
1. The host agent harness executes a sliding-window truncation or an LLM-based summarization step.
2. Crucial low-frequency negative constraints (e.g. graduation dates, strict file invariants, API schemas) are compressed away.
3. The agent enters **Instruction Amnesia**, exhibiting action hallucinations, repeating discarded hypotheses, or declaring completion on false passes.

---

## 2. Mathematical Token Economics of TokenSieve

`TokenSieve` solves this by introducing a dual-phase state projection:

$$\mathcal{S}(\text{stdout}, \text{exit\_code}) = 
\begin{cases} 
\mathcal{P}_{\text{compact}}(\text{stdout}), & \text{if } \text{exit\_code} = 0 \\
\mathcal{P}_{\text{failure}}(\text{stdout}), & \text{if } \text{exit\_code} \neq 0 
\end{cases}$$

### 2.1 Success State Projection ($\mathcal{P}_{\text{compact}}$)
Under successful termination ($\text{exit\_code} = 0$), individual passing test vectors carry **zero novel information** for downstream code generation. `TokenSieve` projects $N$ passing test records into a single state vector:

$$\text{Tokens}(\mathcal{P}_{\text{compact}}) \le 25 \text{ tokens} \quad (\text{independent of } N)$$

For a test suite with 200 tests:
$$\text{Reduction Ratio} = 1 - \frac{20}{4,200} \approx 99.52\%$$

### 2.2 Failure State Projection ($\mathcal{P}_{\text{failure}}$)
Under failure termination ($\text{exit\_code} \neq 0$), the agent strictly requires:
1. The target file and line number where the assertion failed.
2. The expected vs actual delta.
3. The immediate root exception frame.

All passing test assertions, ANSI escape sequences ($\x1b[\dotsm$), and framework internals (`_pytest/runner.py`, `pluggy/manager.py`) are purged. The resulting failure footprint is compressed from $\sim 6,000$ tokens to $\sim 180$ tokens ($97\%$ reduction).

---

## 3. FalsePass Sentinel: Intercepting Silent False Positives

A critical flaw in modern testing harnesses is the **Exit Code 0 Illusion**:
- `pytest` exiting with `0` when `collected 0 items`.
- `jest` exiting with `0` when `No tests found`.
- `cargo` exiting with `0` when `running 0 tests`.

`FalsePassSentinel` performs deterministic AST and regex pattern matching on the execution payload:

$$\text{EffectiveExit} = \begin{cases} 
101, & \text{if } \text{exit\_code} = 0 \land \text{IsMatch}(\text{ZeroTestSignatures}) \\
\text{exit\_code}, & \text{otherwise}
\end{cases}$$

When triggered, Sentinel overrides the exit code to `101` and injects an unmissable alert into the agent stream, preventing false claims of task completion.

---

## 4. PatchFuse: Fault-Tolerant Surgical Fuzzy Patcher

LLMs generate replacement edits as string pairs $(T_{\text{target}}, R_{\text{replacement}})$. In practice, $20\text{--}30\%$ of exact-match edits fail due to:
- Indentation mismatch (e.g. agent emits 2 spaces; file uses 4 spaces).
- Line ending differences (CRLF vs LF).
- Trailing whitespace variance.

`PatchFuse` implements a three-tier resolution hierarchy:

```
[Tier 1: Exact Substring Match]
       │ (fails)
       ▼
[Tier 2: Whitespace-Normalized Line Alignment]
       │ - Strips trailing whitespace per line
       │ - Calculates relative indentation delta: Δ = indent(file) - indent(target)
       │ - Re-indents replacement by Δ
       │ (fails)
       ▼
[Tier 3: Sliding Window SequenceMatcher (Levenshtein)]
       │ - Window search: len(window) ∈ [L-1, L+2]
       │ - Similarity score: S = 2M / (T + W) ≥ 0.85
       │ - Adjusts indentation & applies surgical diff
```

This reduces agent edit retry thrashing from **24% down to under 2%**, saving hundreds of API dollars and eliminating circular retry loops.
