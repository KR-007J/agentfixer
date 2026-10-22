"""AgentFixer: Autonomous AI Agent Runtime Shield & Token Sieve.

High-performance, zero-dependency reliability layer designed to eliminate
context pollution, prevent silent false-passes, and resolve fuzzy patch thrashing.
"""

from agentfixer.tokensieve import TokenSieve, strip_ansi, estimate_tokens
from agentfixer.sentinel import FalsePassSentinel, SentinelResult
from agentfixer.patcher import PatchFuse, PatchResult
from agentfixer.scopelock import ScopeLock, ScopeReport

__version__ = "0.1.0"
__author__ = "Krish Joshi <krishjoshi507@gmail.com>"

__all__ = [
    "TokenSieve",
    "strip_ansi",
    "estimate_tokens",
    "FalsePassSentinel",
    "SentinelResult",
    "PatchFuse",
    "PatchResult",
    "ScopeLock",
    "ScopeReport",
    "__version__",
]
