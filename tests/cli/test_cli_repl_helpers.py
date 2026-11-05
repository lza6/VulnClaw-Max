"""Classic REPL helper coverage."""

from __future__ import annotations

from types import SimpleNamespace

import vulnclaw.cli.main as cli_main
from vulnclaw.config.schema import VulnClawConfig


def test_read_repl_line(monkeypatch):
    monkeypatch.setattr(cli_main.console, "input", lambda *_a, **_k: "hello")
    assert cli_main._read_repl_line(None, "example.com", "recon", True) == "hello"
    assert cli_main._read_repl_line(None, None, "recon", False) == "hello"

    class Session:
        def prompt(self, *_args, **_kwargs):
            return "line"

    assert cli_main._read_repl_line(Session(), "example.com", "recon", False) == "line"


def test_repl_switch_language(monkeypatch):
    config = VulnClawConfig()
    agent = SimpleNamespace(apply_config=lambda _cfg: None)
    monkeypatch.setattr(cli_main, "save_config", lambda _cfg: None)
    monkeypatch.setattr("vulnclaw.i18n.init_i18n", lambda **_kwargs: None)
    monkeypatch.setattr("vulnclaw.cli.tui.rebuild_translations", lambda: None)

    assert cli_main._repl_switch_language("bad", agent, config) is config
    assert cli_main._repl_switch_language("zh", agent, config) is config
    assert config.session.language == "zh"


def test_emit_solve_report(monkeypatch, tmp_path):
    agent = SimpleNamespace(context=SimpleNamespace(state=SimpleNamespace(agent_state=None)))
    assert cli_main._emit_solve_report_if_completed(agent, VulnClawConfig()) == ""

    state = SimpleNamespace(completed=True)
    agent.context.state.agent_state = state
    config = VulnClawConfig()
    config.session.solve_auto_report = False
    assert cli_main._emit_solve_report_if_completed(agent, config) == ""

    report = tmp_path / "report.md"
    report.write_text("content", encoding="utf-8")
    monkeypatch.setattr("vulnclaw.report.solve_report.generate_solve_report", lambda _state: report)
    config.session.solve_auto_report = True
    assert cli_main._emit_solve_report_if_completed(agent, config) == str(report)


def test_prepare_repl_target(monkeypatch):
    agent = SimpleNamespace(reset_context=lambda: None, session_state=SimpleNamespace(phase=SimpleNamespace(value="recon")))
    assert cli_main._prepare_repl_target(agent, "", "old", "recon") == ("old", "recon", False)
    monkeypatch.setattr(
        cli_main,
        "apply_target_state_to_agent",
        lambda _agent, target: SimpleNamespace(phase="recon", restored=True),
    )
    assert cli_main._prepare_repl_target(agent, "new", "old", "recon")[0] == "new"
