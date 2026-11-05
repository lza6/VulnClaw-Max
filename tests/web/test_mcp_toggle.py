"""MCP toggle persists a boolean and rejects unknown servers."""

from __future__ import annotations

from types import SimpleNamespace


def test_toggle_known_server(monkeypatch):
    import vulnclaw.web.services.mcp_control_service as service

    config = SimpleNamespace(mcp=SimpleNamespace(servers={"fetch": object()}))
    calls = []
    monkeypatch.setattr(service, "load_config", lambda: config)
    monkeypatch.setattr(service, "set_config_value", lambda key, value: calls.append((key, value)))

    result = service.toggle_mcp_server("fetch", False)

    assert result == {"name": "fetch", "enabled": False, "applies_to": "next_task"}
    assert calls == [("mcp.servers.fetch.enabled", "false")]


def test_toggle_unknown_server(monkeypatch):
    import vulnclaw.web.services.mcp_control_service as service

    config = SimpleNamespace(mcp=SimpleNamespace(servers={}))
    monkeypatch.setattr(service, "load_config", lambda: config)
    monkeypatch.setattr(service, "set_config_value", lambda *_args: None)

    assert service.toggle_mcp_server("missing", True) is None
