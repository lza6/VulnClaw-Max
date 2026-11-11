"""Streamed LLM calls must account for tokens exactly once."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from vulnclaw.agent.runtime_state import RuntimeState


def _agent() -> MagicMock:
    agent = MagicMock()
    agent.runtime = RuntimeState()
    agent.config.llm.provider = "openai"
    agent.config.llm.model = "gpt-4"
    agent.config.llm.max_tokens = None
    agent.config.llm.temperature = None
    agent.context.get_messages.return_value = []
    agent._build_openai_tools.return_value = []
    return agent


class _Delta:
    def __init__(self, content: str = "") -> None:
        self.content = content
        self.reasoning_content = ""


class _Choice:
    def __init__(self, delta: _Delta) -> None:
        self.delta = delta


class _Chunk:
    def __init__(self, content: str = "", usage: object | None = None) -> None:
        self.delta = _Delta(content)
        self.choices = [_Choice(self.delta)] if content else []
        self.usage = usage


class _Stream:
    def __init__(self, chunks: list[_Chunk]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._chunks:
            return self._chunks.pop(0)
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_call_llm_stream_estimates_when_provider_omits_usage(monkeypatch):
    from vulnclaw.agent import llm_client

    agent = _agent()
    monkeypatch.setattr(
        llm_client,
        "_create_streaming_response",
        lambda _agent, _kwargs: _async_value(_Stream([_Chunk("hello"), _Chunk(" world")])),
    )

    result = await llm_client.call_llm_stream(agent, "system")

    assert result == "hello world"
    assert agent.runtime.llm_calls == 1
    assert agent.runtime.prompt_tokens > 0
    assert agent.runtime.completion_tokens > 0
    assert agent.runtime.total_tokens == (
        agent.runtime.prompt_tokens + agent.runtime.completion_tokens
    )


@pytest.mark.asyncio
async def test_call_llm_stream_uses_provider_usage_when_present(monkeypatch):
    from vulnclaw.agent import llm_client

    agent = _agent()
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
    monkeypatch.setattr(
        llm_client,
        "_create_streaming_response",
        lambda _agent, _kwargs: _async_value(_Stream([_Chunk("ok", usage=usage)])),
    )

    await llm_client.call_llm_stream(agent, "system")

    assert agent.runtime.llm_calls == 1
    assert agent.runtime.prompt_tokens == 11
    assert agent.runtime.completion_tokens == 7
    assert agent.runtime.total_tokens == 18


@pytest.mark.asyncio
async def test_stream_chat_completion_message_records_estimated_usage(monkeypatch):
    from vulnclaw.agent import llm_client

    agent = _agent()
    monkeypatch.setattr(
        llm_client,
        "_create_streaming_response",
        lambda _agent, _kwargs: _async_value(_Stream([_Chunk("tool argument")])),
    )

    message = await llm_client._stream_chat_completion_message(
        agent, [{"role": "user", "content": "scan"}], [], llm_client._NullSink()
    )

    assert "tool argument" in message.content
    assert agent.runtime.llm_calls == 1
    assert agent.runtime.total_tokens > 0


async def _async_value(value):
    return value
