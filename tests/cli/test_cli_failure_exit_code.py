"""CLI must fail loudly when LLM credentials are missing or rejected."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from vulnclaw.agent.errors import LLMInvocationError
from vulnclaw.config.schema import VulnClawConfig


@pytest.mark.parametrize("command", ["recon", "scan", "exploit"])
def test_task_commands_require_credentials(monkeypatch, command):
    from vulnclaw.cli import main

    monkeypatch.setattr(main, "load_config", lambda: VulnClawConfig())

    async def must_not_start(**_kwargs):
        raise AssertionError("orchestration started without credentials")

    monkeypatch.setattr(main, "_run_cli_orchestrated_task", must_not_start)

    result = CliRunner().invoke(main.app, [command, "127.0.0.1:1"])

    assert result.exit_code == 1
    assert "credentials" in result.output.lower()


@pytest.mark.asyncio
async def test_helper_converts_llm_failure_to_exit_code(monkeypatch):
    import typer

    from vulnclaw.cli import _helpers

    class DummyMCP:
        def start_enabled_servers(self):
            return 0

        def stop_all(self):
            pass

    monkeypatch.setattr(
        "vulnclaw.config.settings.load_config", lambda: VulnClawConfig()
    )
    monkeypatch.setattr(
        "vulnclaw.cli.approval_channel.install_cli_approval_channel", lambda _cfg: None
    )
    monkeypatch.setattr(
        "vulnclaw.mcp.lifecycle.MCPLifecycleManager", lambda _cfg: DummyMCP()
    )
    monkeypatch.setattr(
        "vulnclaw.agent.core.AgentCore", lambda _cfg, _mcp: object()
    )

    async def boom(**_kwargs):
        raise LLMInvocationError("bad key", stage="single turn", provider="openai")

    monkeypatch.setattr("vulnclaw.orchestrator.run_agent_task", boom)

    with pytest.raises(typer.Exit) as caught:
        await _helpers._run_cli_orchestrated_task(
            command="recon",
            target="127.0.0.1:1",
            resume=False,
            snapshot=None,
            runner=lambda _agent, _config: None,
        )

    assert caught.value.exit_code == 1
