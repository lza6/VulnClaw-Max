"""Task lifecycle transitions, restart reconciliation and concurrency slots."""

from __future__ import annotations

import asyncio

import pytest

from vulnclaw.web.schemas import TaskCreateRequest


@pytest.mark.asyncio
async def test_lifecycle_transitions_and_terminal_guards():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    task_id = record.task_id

    manager.set_queued(task_id)
    assert manager.get_task(task_id).status == "queued"

    manager.set_restoring(task_id, snapshot_id="snap")
    assert manager.get_task(task_id).status == "restoring"

    manager.set_running(task_id)
    assert manager.get_task(task_id).status == "running"

    manager.set_completed(task_id, latest_message="done")
    assert manager.get_task(task_id).status == "completed"

    manager.set_failed(task_id, "late")
    manager.set_stopped(task_id)
    assert manager.get_task(task_id).status == "completed"
    assert manager.get_task(task_id).error is None


@pytest.mark.asyncio
async def test_illegal_transition_is_rejected():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    manager.set_completed(record.task_id, latest_message="done")

    assert manager._transition(record.task_id, "running") is False
    assert manager.get_task(record.task_id).status == "completed"


def test_restart_reconciles_non_terminal_tasks(monkeypatch, tmp_path):
    import vulnclaw.web.task_manager as module

    storage = tmp_path / "web_tasks.json"
    monkeypatch.setattr(module, "WEB_TASKS_FILE", storage)

    first = module.WebTaskManager()
    record = first.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    first.set_running(record.task_id)
    first._save_state()

    second = module.WebTaskManager()
    loaded = second.get_task(record.task_id)

    assert loaded is not None
    assert loaded.status == "interrupted"
    assert loaded.interrupted_at
    events = list(second._history[record.task_id])
    assert events[-1].event == "task_interrupted"
    assert events[-1].payload["previous_status"] == "running"


@pytest.mark.asyncio
async def test_max_concurrent_one_queues_the_second_task(monkeypatch):
    import vulnclaw.web.services.task_service as service

    started: list[str] = []
    release = asyncio.Event()

    async def fake_run(manager, task_id, _request):
        manager.set_running(task_id)
        started.append(task_id)
        await release.wait()
        manager.set_completed(task_id, latest_message="done")

    monkeypatch.setattr(service, "_run_task", fake_run)
    manager = service.WebTaskManager(max_concurrent=1)
    request = TaskCreateRequest(command="codescan", target="example.com")

    first = service.start_task(manager, request)
    second = service.start_task(manager, request)
    for _ in range(100):
        await asyncio.sleep(0.01)
        if started:
            break

    assert manager.get_task(first).status == "running"
    assert manager.get_task(second).status == "queued"
    assert started == [first]

    release.set()
    for _ in range(100):
        await asyncio.sleep(0.01)
        if manager.get_task(second).status == "completed":
            break

    assert manager.get_task(first).status == "completed"
    assert manager.get_task(second).status == "completed"
    assert started == [first, second]


@pytest.mark.asyncio
async def test_shutdown_cancels_runtime_tasks():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    task = asyncio.create_task(asyncio.sleep(30))
    manager.bind_runtime_task("orphan", task)

    await manager.shutdown()

    assert task.cancelled()
    assert "orphan" not in manager._running


@pytest.mark.asyncio
async def test_shutdown_marks_a_queued_task_stopped():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    manager.set_queued(record.task_id)
    task = asyncio.create_task(asyncio.sleep(30))
    manager.bind_runtime_task(record.task_id, task)

    await manager.shutdown()

    assert manager.get_task(record.task_id).status == "stopped"
