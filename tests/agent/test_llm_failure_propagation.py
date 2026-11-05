"""LLM failures must reach task callers instead of being downgraded to text."""

from __future__ import annotations

import pytest

from vulnclaw.agent.errors import LLMInvocationError


@pytest.mark.asyncio
async def test_chat_raises_when_requested(monkeypatch):
    from vulnclaw.agent.core import AgentCore
    from vulnclaw.config.schema import VulnClawConfig

    agent = AgentCore(VulnClawConfig(), console_output=False)

    async def boom(*_args, **_kwargs):
        raise LLMInvocationError(
            "Error code: 401 - Incorrect API key provided: sk-secret123456",
            stage="single turn",
            provider="openai",
        )

    monkeypatch.setattr("vulnclaw.agent.core.call_llm", boom)

    with pytest.raises(LLMInvocationError) as caught:
        await agent.chat("hello", raise_on_error=True)

    assert "sk-secret123456" not in str(caught.value)
    assert "401" in str(caught.value)


@pytest.mark.asyncio
async def test_chat_keeps_legacy_text_when_not_requested(monkeypatch):
    from vulnclaw.agent.core import AgentCore
    from vulnclaw.config.schema import VulnClawConfig

    agent = AgentCore(VulnClawConfig(), console_output=False)

    async def boom(*_args, **_kwargs):
        raise LLMInvocationError("Error code: 401 - bad key", stage="single turn")

    monkeypatch.setattr("vulnclaw.agent.core.call_llm", boom)

    result = await agent.chat("hello")

    assert "[!]" in result.output
    assert "401" in result.output


@pytest.mark.asyncio
async def test_auth_error_from_retry_loop_is_typed_and_redacted():
    from types import SimpleNamespace

    from vulnclaw.agent.llm_client import _call_with_persistent_retries_unbudgeted

    agent = SimpleNamespace(
        config=SimpleNamespace(llm=SimpleNamespace(provider="openai")),
        _key_pool=[],
        _key_index=0,
    )

    def request():
        raise RuntimeError(
            "Error code: 401 - Incorrect API key provided: sk-secret123456"
        )

    with pytest.raises(LLMInvocationError) as caught:
        await _call_with_persistent_retries_unbudgeted(agent, request, "single turn")

    assert "401" in str(caught.value)
    assert "sk-secret123456" not in str(caught.value)
    assert caught.value.provider == "openai"
