"""Configuration writes must be atomic and leave no temp file behind."""

from __future__ import annotations

import yaml


def test_save_config_replaces_atomically(monkeypatch, tmp_path):
    import vulnclaw.config.settings as settings
    from vulnclaw.config.schema import VulnClawConfig

    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr(settings, "CONFIG_FILE", config_file)
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(settings, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(settings, "KB_DIR", tmp_path / "kb")
    monkeypatch.setattr(settings, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(settings, "WEB_EVENTS_DIR", tmp_path / "web_events")

    config = VulnClawConfig()
    config.llm.api_key = "test-key"
    settings.save_config(config)

    saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert saved["llm"]["api_key"] == "test-key"
    assert not (tmp_path / "config.yaml.tmp").exists()
