"""Wizard stage logic with a fake UI."""

from __future__ import annotations

import io
from types import SimpleNamespace

from rich.console import Console

from vulnclaw.cli import wizard


def _ui():
    return SimpleNamespace(
        console=Console(file=io.StringIO()),
        begin=lambda *_a, **_k: None,
        finish=lambda *_a, **_k: None,
    )


def test_stage_llm_skips_when_ready():
    config = wizard.VulnClawConfig()
    status = wizard.SetupStatus(llm_ready=True)
    result = wizard.WizardResult()
    out_config, out_status = wizard._stage_llm(_ui(), config, status, result)
    assert out_config is config and out_status.llm_ready
    assert "LLM" in result.skipped


def test_stage_llm_non_ollama(monkeypatch):
    config = wizard.VulnClawConfig()
    status = wizard.SetupStatus(llm_ready=False)
    result = wizard.WizardResult()
    monkeypatch.setattr(wizard, "list_providers", lambda: [{"provider": "openai"}])
    monkeypatch.setattr(wizard, "_ask", lambda *_a, **_k: "openai")
    monkeypatch.setattr(wizard, "_ask_secret", lambda *_a, **_k: "secret")
    monkeypatch.setattr(wizard, "_confirm", lambda *_a, **_k: False)

    out_config, out_status = wizard._stage_llm(_ui(), config, status, result)

    assert out_config.llm.api_key == "secret"
    assert out_status.llm_ready is True


def test_stage_llm_ollama_and_override(monkeypatch):
    config = wizard.VulnClawConfig()
    status = wizard.SetupStatus(llm_ready=False)
    result = wizard.WizardResult()
    monkeypatch.setattr(wizard, "list_providers", lambda: [{"provider": "ollama"}])
    monkeypatch.setattr(wizard, "_ask", lambda *_a, default="": "ollama" if "Provider" in _a else "model-x")
    monkeypatch.setattr(wizard, "_confirm", lambda *_a, **_k: True)

    out_config, _ = wizard._stage_llm(_ui(), config, status, result)

    assert out_config.llm.api_key == "ollama"
    assert out_config.llm.model == "model-x"


def test_stage_language_skip_and_prompt(monkeypatch):
    config = wizard.VulnClawConfig()
    config.session.language = "zh"
    status = wizard.SetupStatus()
    result = wizard.WizardResult()
    _, status = wizard._stage_language(_ui(), config, status, result)
    assert status.language == "zh"

    config.session.language = "auto"
    monkeypatch.setattr(wizard, "_ask", lambda *_a, **_k: "bad")
    monkeypatch.setattr(wizard, "_pause", lambda *_a, **_k: None)
    monkeypatch.setattr("vulnclaw.cli.tui.rebuild_translations", lambda: None)
    _, status = wizard._stage_language(_ui(), config, status, result)
    assert status.language == "en"


def test_stage_chrome_without_browser(monkeypatch, tmp_path):
    status = wizard.SetupStatus(chrome_path=None, chrome_debug_live=False)
    result = wizard.WizardResult()
    monkeypatch.setattr(wizard, "CHROME_PROFILE", tmp_path / "profile")
    monkeypatch.setattr(wizard, "_ask", lambda *_a, **_k: "")
    monkeypatch.setattr(wizard, "_pause", lambda *_a, **_k: None)
    monkeypatch.setattr(wizard, "port_open", lambda *_a, **_k: False)
    port, chrome, profile, out = wizard._stage_chrome(_ui(), status, result)
    assert port == status.debug_port and chrome is None
    assert profile.exists()


def test_stage_chrome_devtools_and_burp_skip(monkeypatch):
    config = wizard.VulnClawConfig()
    status = wizard.SetupStatus(chrome_devtools_enabled=True, chrome_devtools_url="http://127.0.0.1:9222")
    result = wizard.WizardResult()
    _, out = wizard._stage_chrome_devtools(_ui(), config, status, 9222, result)
    assert out.chrome_devtools_enabled and "chrome-devtools MCP" in result.skipped

    status = wizard.SetupStatus(burp_enabled=True, burp_sse_live=True)
    result = wizard.WizardResult()
    _, out = wizard._stage_burp(_ui(), config, status, result)
    assert out.burp_enabled and "Burp MCP" in result.skipped

    status = wizard.SetupStatus(burp_enabled=True, burp_jar=__import__("pathlib").Path("x"), burp_sse_live=False)
    result = wizard.WizardResult()
    wizard._stage_burp(_ui(), config, status, result)
    assert result.skipped


def test_run_setup_wizard_happy_path(monkeypatch, tmp_path):
    config = wizard.VulnClawConfig()
    status = wizard.SetupStatus()
    status.chrome_path = "/chrome"
    status.llm_ready = True
    status.language = "en"
    status.chrome_debug_live = True
    status.chrome_devtools_enabled = True
    status.burp_enabled = True
    status.burp_sse_live = True

    monkeypatch.setattr(wizard, "load_config", lambda: config)
    monkeypatch.setattr(wizard, "detect_setup_status", lambda _config: status)
    monkeypatch.setattr(wizard, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "WIZARD_ENV", tmp_path / "wizard.env")
    monkeypatch.setattr(wizard, "_confirm", lambda *_a, **_k: True)
    monkeypatch.setattr(wizard, "_stage_prereqs", lambda _ui, st: st)
    monkeypatch.setattr(wizard, "_stage_llm", lambda _ui, cfg, st, _res: (cfg, st))
    monkeypatch.setattr(wizard, "_stage_language", lambda _ui, cfg, st, _res: (cfg, st))
    monkeypatch.setattr(
        wizard, "_stage_chrome", lambda _ui, st, _res: (9222, "/chrome", tmp_path / "profile", st)
    )
    monkeypatch.setattr(wizard, "_stage_chrome_devtools", lambda _ui, cfg, st, _port, _res: (cfg, st))
    monkeypatch.setattr(wizard, "_stage_burp", lambda _ui, cfg, st, _res: (cfg, st))
    monkeypatch.setattr(wizard, "save_config", lambda _cfg: None)
    monkeypatch.setattr(wizard, "_reload_mcp", lambda *_a, **_k: True)

    result = wizard.run_setup_wizard(console=Console(file=io.StringIO()))

    assert result.completed is True
    assert result.restarted_mcp is True


def test_run_setup_wizard_cancel(monkeypatch, tmp_path):
    monkeypatch.setattr(wizard, "load_config", lambda: wizard.VulnClawConfig())
    monkeypatch.setattr(wizard, "detect_setup_status", lambda _config: wizard.SetupStatus())
    monkeypatch.setattr(wizard, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(wizard, "TOOLS_DIR", tmp_path / "tools")
    monkeypatch.setattr(wizard, "_confirm", lambda *_a, **_k: False)

    result = wizard.run_setup_wizard(console=Console(file=io.StringIO()))

    assert result.completed is False
    assert result.messages
