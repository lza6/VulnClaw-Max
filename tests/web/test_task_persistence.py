"""Append-only event logs and debounced task snapshots."""

from __future__ import annotations

import json
import time

from vulnclaw.web.schemas import TaskCreateRequest


def _manager(monkeypatch, tmp_path):
    import vulnclaw.web.task_manager as module

    monkeypatch.setattr(module, "WEB_TASKS_FILE", tmp_path / "web_tasks.json")
    monkeypatch.setattr(module, "WEB_EVENTS_DIR", tmp_path / "events")
    return module.WebTaskManager()


def test_events_are_append_only_and_snapshots_drop_history(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )

    started = time.perf_counter()
    for index in range(300):
        manager.publish(record.task_id, "round_output", {"i": index})
    elapsed = time.perf_counter() - started
    manager._flush_save()

    event_file = tmp_path / "events" / f"{record.task_id}.jsonl"
    lines = event_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 301
    assert [json.loads(line)["seq"] for line in lines] == list(range(1, 302))
    assert elapsed < 0.5

    snapshot = json.loads((tmp_path / "web_tasks.json").read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == 2
    assert "history" not in snapshot
    assert len(snapshot["tasks"]) == 1


def test_restart_restores_events_from_jsonl(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    manager.publish(record.task_id, "round_output", {"i": 1})
    manager.set_completed(record.task_id, latest_message="done")
    manager._flush_save()

    import vulnclaw.web.task_manager as module

    restarted = module.WebTaskManager()
    events = list(restarted._history[record.task_id])
    assert [event.seq for event in events] == [1, 2, 3]
    assert restarted.get_task(record.task_id).status == "completed"


def test_legacy_history_is_migrated_to_jsonl(monkeypatch, tmp_path):
    import vulnclaw.web.task_manager as module

    storage = tmp_path / "web_tasks.json"
    events_dir = tmp_path / "events"
    monkeypatch.setattr(module, "WEB_TASKS_FILE", storage)
    monkeypatch.setattr(module, "WEB_EVENTS_DIR", events_dir)
    storage.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "task_id": "task_legacy",
                        "command": "codescan",
                        "target": "example.com",
                        "status": "completed",
                    }
                ],
                "history": {
                    "task_legacy": [
                        {"event": "task_created", "task_id": "task_legacy", "payload": {}},
                        {
                            "event": "task_completed",
                            "task_id": "task_legacy",
                            "payload": {"status": "completed"},
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    manager = module.WebTaskManager()

    assert [event.seq for event in manager._history["task_legacy"]] == [1, 2]
    migrated = (events_dir / "task_legacy.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(migrated) == 2
    saved = json.loads(storage.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 2
    assert "history" not in saved


def test_task_retention_caps_at_200_and_forgets_bus_state(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    first = None
    for index in range(205):
        record = manager.create_task(
            TaskCreateRequest(command="codescan", target=f"t{index}")
        )
        first = first or record.task_id

    assert len(manager._tasks) == 200
    assert first not in manager._tasks
    assert first not in manager._bus._buffers


def test_loading_an_unchanged_snapshot_is_read_only(monkeypatch, tmp_path):
    manager = _manager(monkeypatch, tmp_path)
    record = manager.create_task(TaskCreateRequest(command="codescan", target="x"))
    manager.set_completed(record.task_id, latest_message="done")
    manager._flush_save()
    storage = tmp_path / "web_tasks.json"
    before = storage.read_bytes()

    import vulnclaw.web.task_manager as module

    module.WebTaskManager()

    assert storage.read_bytes() == before
