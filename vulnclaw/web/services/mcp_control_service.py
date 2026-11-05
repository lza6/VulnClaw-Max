"""MCP enable/disable control for the Web UI.

Changes are persisted to config and apply to the next task's MCP lifecycle.
"""

from __future__ import annotations

from vulnclaw.config.settings import load_config, set_config_value


def toggle_mcp_server(name: str, enabled: bool) -> dict[str, object] | None:
    config = load_config()
    if name not in config.mcp.servers:
        return None
    set_config_value(f"mcp.servers.{name}.enabled", "true" if enabled else "false")
    return {"name": name, "enabled": enabled, "applies_to": "next_task"}
