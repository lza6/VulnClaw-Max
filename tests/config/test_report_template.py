"""Report template configuration: schema default, `config set`, CLI wiring."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_session_report_template_defaults_to_pentest():
    from vulnclaw.config.schema import VulnClawConfig

    assert VulnClawConfig().session.report_template == "pentest"


def test_session_report_template_rejects_unknown_values():
    from vulnclaw.config.schema import SessionConfig

    with pytest.raises(ValidationError):
        SessionConfig(report_template="freestyle")


def test_set_config_value_accepts_known_templates(monkeypatch, tmp_path):
    import vulnclaw.config.settings as settings

    monkeypatch.setattr(settings, "CONFIG_FILE", tmp_path / "config.yaml")
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)

    settings.set_config_value("session.report_template", "executive")

    assert settings.load_config().session.report_template == "executive"


def test_set_config_value_rejects_unknown_template_before_writing(monkeypatch, tmp_path):
    import vulnclaw.config.settings as settings

    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr(settings, "CONFIG_FILE", config_file)
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    settings.set_config_value("session.report_template", "ctf")

    with pytest.raises(ValueError, match="must be one of"):
        settings.set_config_value("session.report_template", "freestyle")

    # A rejected value must never reach disk: load_config drops the whole file
    # when any field fails validation, which would silently reset every setting.
    assert settings.load_config().session.report_template == "ctf"


def test_report_command_uses_the_configured_template(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    import vulnclaw.config.settings as settings
    import vulnclaw.report.generator as report_generator
    import vulnclaw.target_state.store as store
    from vulnclaw.agent.context import SessionState
    from vulnclaw.cli.main import app
    from vulnclaw.config.domain_models import VulnerabilityFinding

    config_dir = tmp_path / "cfg"
    sessions = config_dir / "sessions"
    targets = config_dir / "targets"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "session:\n  language: zh\n  report_template: ctf\n", encoding="utf-8"
    )
    monkeypatch.setattr(settings, "CONFIG_FILE", config_dir / "config.yaml")
    monkeypatch.setattr(settings, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(settings, "TARGETS_DIR", targets)
    monkeypatch.setattr(store, "TARGETS_DIR", targets)
    monkeypatch.setattr(report_generator, "SESSIONS_DIR", sessions)

    state = SessionState(target="https://example.com")
    finding = VulnerabilityFinding(
        title="IDOR",
        severity="High",
        vuln_type="IDOR",
        description="Order id enumerable.",
        evidence="/api/orders/1001",
    )
    finding.mark_verified(note="config template check")
    state.add_finding(finding)
    state.add_step("enumerate ids")
    store.save_target_state("https://example.com", state, command="scan")

    result = CliRunner().invoke(app, ["report", "https://example.com", "--target"])

    assert result.exit_code == 0, result.output
    reports = sorted(sessions.glob("*.md"))
    assert reports, "report command produced no markdown report"
    assert "_ctf_" in reports[-1].name
    assert "CTF 挑战报告" in reports[-1].read_text(encoding="utf-8")


def test_public_config_round_trips_the_template(monkeypatch):
    from vulnclaw.config.schema import VulnClawConfig
    from vulnclaw.web.schemas import ConfigUpdateRequest
    from vulnclaw.web.services import config_service

    config = VulnClawConfig()
    config.session.report_template = "ctf"
    monkeypatch.setattr(config_service, "load_config", lambda: config)
    monkeypatch.setattr(config_service, "save_config", lambda _cfg: None)

    assert config_service.get_public_config().report_template == "ctf"

    updated = config_service.update_public_config(
        ConfigUpdateRequest(report_template="executive")
    )

    assert updated.report_template == "executive"
    assert config.session.report_template == "executive"
