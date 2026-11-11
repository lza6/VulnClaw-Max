"""MCP toggle persists config and applies to the live control plane."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_toggle_known_server(monkeypatch):
    import vulnclaw.web.services.mcp_control_service as service

    server = SimpleNamespace(enabled=True, allowed_tools=[])
    config = SimpleNamespace(mcp=SimpleNamespace(servers={"fetch": server}))
    saved = []
    manager = SimpleNamespace(
        config=config,
        restart_server=AsyncMock(return_value=True),
        astop_server=AsyncMock(),
        registry=SimpleNamespace(
            get_all_servers=lambda: {},
            get_server_tools=lambda name: ["fetch", "memory"],
        ),
    )
    monkeypatch.setattr(service, "load_config", lambda: config)
    monkeypatch.setattr(service, "save_config", lambda item: saved.append(item))
    monkeypatch.setattr(service, "get_control_manager", lambda: manager)

    result = await service.toggle_mcp_server("fetch", False)

    assert result is not None
    assert result["name"] == "fetch"
    assert result["enabled"] is False
    assert result["applies_to"] == "control_plane_and_next_task"
    assert saved == [config]
    manager.astop_server.assert_awaited_once_with("fetch")


@pytest.mark.asyncio
async def test_toggle_updates_allowed_tools(monkeypatch):
    import vulnclaw.web.services.mcp_control_service as service

    server = SimpleNamespace(enabled=False, allowed_tools=[])
    config = SimpleNamespace(mcp=SimpleNamespace(servers={"fetch": server}))
    manager = SimpleNamespace(
        config=config,
        restart_server=AsyncMock(return_value=True),
        astop_server=AsyncMock(),
        registry=SimpleNamespace(
            get_all_servers=lambda: {},
            get_server_tools=lambda name: ["fetch"],
        ),
    )
    monkeypatch.setattr(service, "load_config", lambda: config)
    monkeypatch.setattr(service, "save_config", lambda _item: None)
    monkeypatch.setattr(service, "get_control_manager", lambda: manager)

    result = await service.toggle_mcp_server("fetch", True, allowed_tools=["fetch", " "])

    assert server.allowed_tools == ["fetch"]
    assert result is not None
    assert result["allowed_tools"] == ["fetch"]
    manager.restart_server.assert_awaited_once_with("fetch")


@pytest.mark.asyncio
async def test_toggle_unknown_server(monkeypatch):
    import vulnclaw.web.services.mcp_control_service as service

    config = SimpleNamespace(mcp=SimpleNamespace(servers={}))
    monkeypatch.setattr(service, "load_config", lambda: config)

    assert await service.toggle_mcp_server("missing", True) is None


@pytest.mark.asyncio
async def test_tool_whitelist_rejects_unlisted_tool(monkeypatch, tmp_path):
    from vulnclaw.mcp.lifecycle import MCPLifecycleManager

    server = SimpleNamespace(allowed_tools=["allowed"])
    config = SimpleNamespace(mcp=SimpleNamespace(servers={"fetch": server}))
    manager = MCPLifecycleManager(config)  # type: ignore[arg-type]
    manager.registry.register_server("fetch")
    manager.registry.register_tool(
        "fetch", {"name": "blocked", "inputSchema": {"type": "object", "properties": {}}}
    )
    monkeypatch.setattr("vulnclaw.config.settings.CONFIG_DIR", tmp_path)

    with pytest.raises(PermissionError, match="allowed_tools"):
        await manager.call_tool("blocked", {})
    assert (tmp_path / "mcp_audit.jsonl").read_text(encoding="utf-8").count("mcp_tool_denied") == 1
