"""Agent package public surface.

Exports are lazy so importing a lightweight submodule (for example
``vulnclaw.agent.errors`` from the CLI entrypoint) does not pull in the full
agent state/model stack and slow down ``vulnclaw --help``.
"""

from __future__ import annotations

__all__ = [
    "AgentState",
    "EvidenceRecord",
    "PinnedFact",
    "ProgressSignal",
    "ToolCallRecord",
    "ToolHealth",
]


def __getattr__(name: str):
    if name in __all__:
        from vulnclaw.agent import agent_state

        return getattr(agent_state, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
