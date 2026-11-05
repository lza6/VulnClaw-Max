"""Additional CLI command smoke coverage."""

from __future__ import annotations

from typer.testing import CliRunner

from vulnclaw.cli.main import app
from vulnclaw.config.schema import VulnClawConfig


def test_config_commands(monkeypatch):
    import vulnclaw.cli.main as cli_main

    config = VulnClawConfig()
    config.llm.api_key = "secret-key"
    monkeypatch.setattr(cli_main, "load_config", lambda: config)
    monkeypatch.setattr(cli_main, "set_config_value", lambda key, value: None)
    monkeypatch.setattr(
        cli_main,
        "list_providers",
        lambda: [{"provider": "openai", "label": "OpenAI", "base_url": "u", "default_model": "m"}],
    )
    runner = CliRunner()
    assert runner.invoke(app, ["config", "set", "llm.model", "m"]).exit_code == 0
    assert runner.invoke(app, ["config", "get", "llm.api_key"]).exit_code == 0
    assert runner.invoke(app, ["config", "list"]).exit_code == 0
    assert runner.invoke(app, ["config", "provider", "--list"]).exit_code == 0


def test_plugin_commands():
    runner = CliRunner()
    listed = runner.invoke(app, ["plugins", "list", "--no-external"])
    assert listed.exit_code == 0
    assert "builtin.web.headers" in listed.output
    assert runner.invoke(app, ["plugins", "info", "missing"]).exit_code == 1


def test_target_state_commands(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    from vulnclaw.agent.context import SessionState

    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path)
    session = SessionState(target="example.com")
    store.save_target_state("example.com", session, command="recon")

    runner = CliRunner()
    listed = runner.invoke(app, ["target-state", "list", "example.com"])
    assert listed.exit_code == 0
    assert "snapshot" in listed.output.lower()


def test_web_dry_run():
    result = CliRunner().invoke(app, ["web", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower()
