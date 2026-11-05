"""Executor early-return paths and source extraction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from vulnclaw.agent.builtin_tools import (
    execute_brute_force,
    execute_evidence_tool,
    execute_http_probe_batch,
    execute_mcp_tool,
    execute_nmap,
    execute_python,
    execute_source_extract,
    execute_vault_tool,
)


def _agent(*, enable_python=False, safety=None):
    if safety is None:
        safety = SimpleNamespace(
            enable_python_execute=enable_python,
            python_execute_mode="safe",
            python_execute_max_lines=2,
            python_execute_show_warning=False,
            python_execute_max_output_chars=100,
            python_execute_audit_enabled=False,
            python_execute_restricted=False,
        )
    return SimpleNamespace(
        config=SimpleNamespace(safety=safety),
        session_state=SimpleNamespace(target="example.com", task_constraints=None, agent_state=None),
        _subagent_ctx=SimpleNamespace(depth=0),
        mcp_manager=None,
        context=SimpleNamespace(state=SimpleNamespace(findings=[]), vault=SimpleNamespace()),
    )


@pytest.mark.asyncio
async def test_execute_python_early_returns(monkeypatch):
    agent = _agent(enable_python=False)
    assert "empty" in await execute_python(agent, {"code": "  "})
    assert "disabled" in await execute_python(agent, {"code": "print(1)"})

    agent = _agent(enable_python=True)
    assert "max line" in await execute_python(agent, {"code": "a\nb\nc"})
    assert "blocked" in await execute_python(agent, {"code": "import os; os.system('id')"})
    assert "blocked" in await execute_python(agent, {"code": "eval('1')"})


@pytest.mark.asyncio
async def test_execute_nmap_early_returns(monkeypatch):
    agent = _agent()
    assert "target" in await execute_nmap(agent, {})
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setattr("socket.getaddrinfo", lambda *_a, **_k: [])
    assert "nmap" in await execute_nmap(agent, {"target": "example.com"})


@pytest.mark.asyncio
async def test_source_extract_and_unknown_tools():
    agent = _agent()
    text = await execute_source_extract(agent, {"text": "highlight_file($x); <form action='/a'></form>"})
    assert "source_extract" in text and "/a" in text
    assert "requires" in await execute_source_extract(agent, {})
    assert execute_evidence_tool(agent, "unknown_tool", {})
    assert await execute_vault_tool(agent, "unknown_tool", {})
    assert "MCP" in await execute_mcp_tool(agent, "fetch", {})
    assert await execute_http_probe_batch(agent, {"targets": []})
    assert await execute_brute_force(agent, {})
