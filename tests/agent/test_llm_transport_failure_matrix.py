"""Wire-level LLM failure matrix: the real SDK against a local mock provider.

Each case drives ``_call_with_persistent_retries_unbudgeted`` through the same
HTTP error payloads a provider returns, so failure classification (fail-fast
auth, retry-then-raise transient, cancellation) is verified against the SDK's
actual exception types instead of hand-built stand-ins.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from scripts.mock_llm_server import start_mock_llm_server
from vulnclaw.agent.errors import LLMInvocationError
from vulnclaw.agent.llm_client import _call_with_persistent_retries_unbudgeted

STAGE = "single turn"
MOCK_SECRET = "sk-mock-secret-123456"


@pytest.fixture
def mock_llm():
    server = start_mock_llm_server(timeout_seconds=0.8)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def no_retry_delay(monkeypatch):
    """Drop the 5 s backoff so retry-exhaustion cases stay fast."""

    async def _no_delay(*_args, **_kwargs):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_delay)


def _client(server, *, timeout: float = 2.0):
    from openai import OpenAI

    return OpenAI(
        api_key="sk-test",
        base_url=server.base_url,
        timeout=timeout,
        max_retries=0,
    )


def _agent(client):
    return SimpleNamespace(
        config=SimpleNamespace(llm=SimpleNamespace(provider="openai")),
        _client=client,
        _key_pool=[],
        _key_index=0,
    )


async def _call(agent, scenario: str, *, max_retries: int = 2):
    def request():
        return agent._client.chat.completions.create(
            model=f"mock-{scenario}",
            messages=[{"role": "user", "content": "ping"}],
        )

    return await _call_with_persistent_retries_unbudgeted(
        agent, request, STAGE, max_retries=max_retries
    )


@pytest.mark.parametrize("scenario", ["401", "403"])
async def test_auth_errors_fail_fast_and_redact_the_key(
    mock_llm, no_retry_delay, scenario
):
    agent = _agent(_client(mock_llm))

    with pytest.raises(LLMInvocationError) as caught:
        await _call(agent, scenario, max_retries=5)

    assert caught.value.fatal is True
    assert caught.value.stage == STAGE
    assert MOCK_SECRET not in str(caught.value)
    assert len(mock_llm.requests) == 1


@pytest.mark.parametrize(
    ("scenario", "timeout"),
    [
        ("429", 2.0),
        ("500", 2.0),
        ("malformed", 2.0),
        ("empty_choices", 2.0),
        ("drop", 2.0),
        ("timeout", 0.2),
    ],
)
async def test_transient_errors_retry_then_raise(
    mock_llm, no_retry_delay, scenario, timeout
):
    agent = _agent(_client(mock_llm, timeout=timeout))

    with pytest.raises(LLMInvocationError) as caught:
        await _call(agent, scenario, max_retries=2)

    assert caught.value.fatal is True
    assert caught.value.stage == STAGE
    assert len(mock_llm.requests) == 2


async def test_retry_then_ok_returns_the_response_and_attempt_count(
    mock_llm, no_retry_delay
):
    mock_llm.retry_failures = 2
    agent = _agent(_client(mock_llm))

    response, retries = await _call(agent, "retry_then_ok", max_retries=5)

    assert response.choices[0].message.content == "mock ok"
    assert retries == 2
    assert len(mock_llm.requests) == 3


async def test_cancellation_is_not_converted_to_an_llm_error(mock_llm):
    agent = _agent(_client(mock_llm, timeout=5.0))

    task = asyncio.create_task(_call(agent, "hang", max_retries=3))
    await asyncio.sleep(0.2)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


async def test_single_turn_chat_surfaces_typed_auth_failure(mock_llm, tmp_path):
    from vulnclaw.agent.core import AgentCore
    from vulnclaw.config.schema import VulnClawConfig

    config = VulnClawConfig()
    config.llm.provider = "custom"
    config.llm.base_url = mock_llm.base_url
    config.llm.api_key = "sk-test"
    config.llm.model = "mock-401"
    config.session.output_dir = tmp_path
    agent = AgentCore(config, console_output=False)
    agent._client = _client(mock_llm)

    with pytest.raises(LLMInvocationError) as caught:
        await agent.chat("probe", target="127.0.0.1:1", raise_on_error=True)

    assert MOCK_SECRET not in str(caught.value)
    assert "401" in str(caught.value)
