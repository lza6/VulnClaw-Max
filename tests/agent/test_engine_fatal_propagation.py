"""Every task engine must let a fatal LLM error escape to the task layer.

Transient failures retry inside ``llm_client``; once that layer raises
``LLMInvocationError``, solve/team/rounds/persistent must not downgrade it to
text. ``run_agent_task`` then records ``failed``/exit 1 and re-raises so the CLI
and Web task layers can report the failure.
"""

from __future__ import annotations

import pytest

from scripts.mock_llm_server import start_mock_llm_server
from vulnclaw.agent.core import AgentCore
from vulnclaw.agent.errors import LLMInvocationError
from vulnclaw.config.schema import VulnClawConfig
from vulnclaw.orchestrator import run_agent_task

TARGET = "127.0.0.1:1"


@pytest.fixture
def mock_llm():
    server = start_mock_llm_server()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def failing_agent(mock_llm, tmp_path):
    from openai import OpenAI

    config = VulnClawConfig()
    config.llm.provider = "custom"
    config.llm.base_url = mock_llm.base_url
    config.llm.api_key = "sk-test"
    config.llm.model = "mock-401"
    config.session.output_dir = tmp_path
    agent = AgentCore(config, console_output=False)
    agent._client = OpenAI(
        api_key="sk-test",
        base_url=mock_llm.base_url,
        timeout=2.0,
        max_retries=0,
    )
    return agent


async def test_solve_propagates_fatal_llm_error(failing_agent):
    with pytest.raises(LLMInvocationError):
        await failing_agent.solve("probe", target=TARGET, max_steps=1)


async def test_rounds_propagates_fatal_llm_error(failing_agent):
    with pytest.raises(LLMInvocationError):
        await failing_agent.auto_pentest(
            "probe", target=TARGET, max_rounds=1, engine="rounds"
        )


async def test_team_propagates_fatal_llm_error(failing_agent):
    from vulnclaw.agent.team import run_team_pentest

    with pytest.raises(LLMInvocationError):
        await run_team_pentest(
            failing_agent,
            user_input="probe",
            target=TARGET,
            max_steps=1,
            max_parallel=1,
        )


async def test_persistent_propagates_fatal_llm_error(failing_agent):
    with pytest.raises(LLMInvocationError):
        await failing_agent.persistent_pentest(
            "probe",
            target=TARGET,
            rounds_per_cycle=1,
            max_cycles=1,
            auto_report=False,
        )


async def test_run_agent_task_marks_failed_and_reraises(
    failing_agent, monkeypatch
):
    recorded: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "vulnclaw.orchestrator.mark_run_status",
        lambda _ctx, status, **kwargs: recorded.append((status, kwargs)),
    )

    with pytest.raises(LLMInvocationError):
        await run_agent_task(
            agent=failing_agent,
            command="run",
            target=TARGET,
            resume=False,
            runner=lambda agent: agent.solve("probe", target=TARGET, max_steps=1),
        )

    assert recorded, "run status was never recorded"
    status, kwargs = recorded[-1]
    assert status == "failed"
    assert kwargs["exit_code"] == 1
