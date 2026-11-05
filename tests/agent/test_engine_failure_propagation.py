"""Fatal LLM errors must not be downgraded by the team planner."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from vulnclaw.agent.errors import LLMInvocationError


@pytest.mark.asyncio
async def test_team_plan_reraises_fatal_llm_error(monkeypatch):
    from vulnclaw.agent import team

    async def boom(*_args, **_kwargs):
        raise LLMInvocationError(
            "Error code: 401 - Incorrect API key provided: placeholder",
            stage="structured_call",
            fatal=True,
        )

    monkeypatch.setattr("vulnclaw.agent.solver.structured_call", boom)
    agent = SimpleNamespace(active_role=None, _get_client=lambda: object())

    with pytest.raises(LLMInvocationError):
        await team.make_team_plan(agent, "origin", "goal", [])


@pytest.mark.asyncio
async def test_team_adviser_reraises_fatal_llm_error(monkeypatch):
    from vulnclaw.agent import team

    async def boom(*_args, **_kwargs):
        raise LLMInvocationError("401", stage="structured_call", fatal=True)

    monkeypatch.setattr("vulnclaw.agent.solver.structured_call", boom)
    agent = SimpleNamespace(
        active_role=None,
        _get_client=lambda: object(),
        session_state=SimpleNamespace(research=None),
    )
    step = team.TeamStep(role="researcher", objective="probe", done_when="done")

    with pytest.raises(LLMInvocationError):
        await team.ask_adviser(agent, "origin", "goal", step, "result")

def test_team_children_disable_console_output():
    from vulnclaw.agent import team

    class FakeAgent:
        def __init__(self, config, mcp_manager, **kwargs):
            self.config = config
            self.mcp_manager = mcp_manager
            self.kwargs = kwargs

    root = FakeAgent("cfg", "mcp")
    child = team._default_agent_factory(root)()

    assert isinstance(child, FakeAgent)
    assert child.kwargs["console_output"] is False
