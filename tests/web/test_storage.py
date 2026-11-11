"""Storage accounting and the Web-triggered gc path."""

from __future__ import annotations

import os
import time


def _seed(tmp_path, monkeypatch):
    import vulnclaw.config.settings as settings
    import vulnclaw.web.services.storage_service as storage

    dirs = {
        "SESSIONS_DIR": tmp_path / "sessions",
        "RUNS_DIR": tmp_path / "runs",
        "TARGETS_DIR": tmp_path / "targets",
        "PROJECTS_DIR": tmp_path / "projects",
        "WEB_EVENTS_DIR": tmp_path / "events",
    }
    for name, path in dirs.items():
        path.mkdir()
        monkeypatch.setattr(settings, name, path)
        monkeypatch.setattr(storage, name, path)
    tasks = tmp_path / "web_tasks.json"
    tasks.write_text('{"tasks": []}', encoding="utf-8")
    monkeypatch.setattr(settings, "WEB_TASKS_FILE", tasks)
    monkeypatch.setattr(storage, "WEB_TASKS_FILE", tasks)
    return settings, storage, dirs


def test_storage_usage_counts_files(tmp_path, monkeypatch):
    _settings, storage, dirs = _seed(tmp_path, monkeypatch)
    (dirs["SESSIONS_DIR"] / "a").mkdir()
    (dirs["SESSIONS_DIR"] / "a" / "report.md").write_text("hello", encoding="utf-8")
    (dirs["WEB_EVENTS_DIR"] / "task.jsonl").write_text("event", encoding="utf-8")

    usage = storage.storage_usage()

    assert usage["sessions_bytes"] == 5
    assert usage["web_events_bytes"] == 5
    assert usage["total_bytes"] >= 10


def test_gc_dry_run_keeps_old_directory(tmp_path, monkeypatch):
    settings, storage, dirs = _seed(tmp_path, monkeypatch)
    old = dirs["SESSIONS_DIR"] / "old"
    old.mkdir()
    (old / "file").write_text("x", encoding="utf-8")
    os.utime(old, (time.time() - 40 * 86400, time.time() - 40 * 86400))

    result = storage.run_gc(older_than=30, keep_last=0, dry_run=True)

    assert result["removed"] == 1
    assert result["freed_bytes"] == 1
    assert old.exists()
