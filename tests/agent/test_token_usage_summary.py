"""Provider usage is accumulated into the task summary."""

from __future__ import annotations

from types import SimpleNamespace

from vulnclaw.agent.llm_client import _record_response_usage
from vulnclaw.agent.runtime_state import RuntimeState


def test_usage_accumulates_across_calls():
    agent = SimpleNamespace(runtime=RuntimeState())
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    )

    _record_response_usage(agent, response)
    _record_response_usage(agent, response)

    assert agent.runtime.llm_calls == 2
    assert agent.runtime.prompt_tokens == 20
    assert agent.runtime.completion_tokens == 10
    assert agent.runtime.total_tokens == 30


def test_missing_usage_still_counts_the_call():
    agent = SimpleNamespace(runtime=RuntimeState())
    _record_response_usage(agent, SimpleNamespace(usage=None))

    assert agent.runtime.llm_calls == 1
    assert agent.runtime.total_tokens == 0


def test_task_summary_accepts_flat_token_fields():
    from vulnclaw.web.schemas import TaskSummary

    summary = TaskSummary(
        target="https://example.com",
        command="recon",
        tokens_input=10,
        tokens_output=5,
        tokens_total=15,
        llm_calls=1,
    )
    assert summary.tokens_total == 15


def test_stream_usage_is_estimated_when_provider_returns_none():
    from vulnclaw.agent.llm_client import _record_estimated_usage

    agent = SimpleNamespace(runtime=RuntimeState())
    _record_estimated_usage(
        agent,
        [{"role": "user", "content": "scan example.com"}],
        None,
        "working on it",
    )

    assert agent.runtime.llm_calls == 1
    assert agent.runtime.prompt_tokens > 0
    assert agent.runtime.completion_tokens > 0
    assert agent.runtime.total_tokens == (
        agent.runtime.prompt_tokens + agent.runtime.completion_tokens
    )
