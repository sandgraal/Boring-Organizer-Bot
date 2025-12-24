"""Agent tools module for B.O.B.

Provides a stable API for AI agents to interact with B.O.B functionality.
These wrappers isolate agents from internal implementation changes.
"""

from bob.agents.tools import (
    AgentResult,
    ask,
    explain_sources,
    index,
    run_eval,
)

__all__ = [
    "AgentResult",
    "ask",
    "explain_sources",
    "index",
    "run_eval",
]
