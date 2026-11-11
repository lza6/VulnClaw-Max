"""MCP enable/disable control and live diagnostics for the Web UI.

The Web process keeps one control-plane ``MCPLifecycleManager`` alive. Toggling
a server in Settings applies to that manager immediately (start/stop/restart)
and persists the same setting for task-scoped managers. Task managers still
snapshot config when they start, so a running task keeps the toolset it began
with; the next task sees the updated config.
"""

from __future__ import annotations

from typing import Optional

from vulnclaw.config.settings import load_config, save_config
from vulnclaw.mcp.diagnostics import get_mcp_diagnostics
from vulnclaw.mcp.lifecycle import MCPLifecycleManager
from vulnclaw.mcp.schemas import MCPDiagnosticsView

_control_manager: MCPLifecycleManager | None = None


def get_control_manager() -> MCPLifecycleManager:
    """Return the process-wide control-plane manager, starting it on demand."""
    global _control_manager
    if _control_manager is None:
        config = load_config()
        manager = MCPLifecycleManager(config)
        manager.start_enabled_servers()
        _control_manager = manager
    return _control_manager


def reset_control_manager() -> None:
    """Stop and drop the live manager (tests and process shutdown)."""
    global _control_manager
    if _control_manager is not None:
        _control_manager.stop_all()
        _control_manager = None


def get_live_mcp_diagnostics() -> MCPDiagnosticsView:
    """Diagnostics from the live control-plane manager, not a throwaway one."""
    return get_mcp_diagnostics(manager=get_control_manager())


async def toggle_mcp_server(
    name: str,
    enabled: bool,
    allowed_tools: Optional[list[str]] = None,
) -> dict[str, object] | None:
    """Persist a server toggle and apply it to the live control plane now."""
    config = load_config()
    server = config.mcp.servers.get(name)
    if server is None:
        return None

    server.enabled = bool(enabled)
    if allowed_tools is not None:
        server.allowed_tools = [str(item).strip() for item in allowed_tools if str(item).strip()]
    save_config(config)

    manager = get_control_manager()
    manager.config.mcp.servers[name] = server
    if enabled:
        await manager.restart_server(name)
    else:
        await manager.astop_server(name)

    state = manager.registry.get_all_servers().get(name)
    return {
        "name": name,
        "enabled": enabled,
        "allowed_tools": list(server.allowed_tools),
        "applies_to": "control_plane_and_next_task",
        "running": bool(state.running) if state else False,
        "tool_count": len(manager.registry.get_server_tools(name)),
    }
