"""`vulnclaw gc` prunes old state without touching newer entries."""

from __future__ import annotations

import os
import time

from typer.testing import CliRunner


def _make_dirs(monkeypatch, tmp_path):
    import vulnclaw.config.settings as settings

    sessions = tmp_path / "sessions"
    runs = tmp_path / "runs"
    targets = tmp_path / "targets"
    for root in (sessions, runs, targets):
        root.mkdir()
    monkeypatch.setattr(settings, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(settings, "RUNS_DIR", runs)
    monkeypatch.setattr(settings, "TARGETS_DIR", targets)

    old = sessions / "old"
    old.mkdir()
    (old / "file.txt").write_text("x", encoding="utf-8")
    os.utime(old, (time.time() - 40 * 86400, time.time() - 40 * 86400))
    new = sessions / "new"
    new.mkdir()
    return sessions, old, new


def test_gc_dry_run_keeps_old_dirs(monkeypatch, tmp_path):
    from vulnclaw.cli.main import app

    sessions, old, _new = _make_dirs(monkeypatch, tmp_path)
    result = CliRunner().invoke(app, ["gc", "--older-than", "30", "--keep-last", "0", "--dry-run"])
    assert result.exit_code == 0
    assert old.exists()
    assert "would remove" in result.output


def test_gc_removes_old_dirs(monkeypatch, tmp_path):
    from vulnclaw.cli.main import app

    sessions, old, new = _make_dirs(monkeypatch, tmp_path)
    result = CliRunner().invoke(app, ["gc", "--older-than", "30", "--keep-last", "0"])
    assert result.exit_code == 0
    assert not old.exists()
    assert new.exists()
