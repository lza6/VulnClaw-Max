"""Global --offline flag and helper."""

from __future__ import annotations

from typer.testing import CliRunner


def test_is_offline_reads_env(monkeypatch):
    from vulnclaw.offline import is_offline

    monkeypatch.delenv("VULNCLAW_OFFLINE", raising=False)
    assert is_offline() is False
    monkeypatch.setenv("VULNCLAW_OFFLINE", "true")
    assert is_offline() is True


def test_cli_offline_flag_sets_environment(monkeypatch):
    import os

    from vulnclaw.cli.main import app

    monkeypatch.delenv("VULNCLAW_OFFLINE", raising=False)
    try:
        result = CliRunner().invoke(app, ["--offline", "--version"])
        assert result.exit_code == 0
        assert os.environ["VULNCLAW_OFFLINE"] == "1"
    finally:
        os.environ.pop("VULNCLAW_OFFLINE", None)
