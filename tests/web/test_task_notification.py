"""Terminal web tasks fan out a run notification without changing their outcome."""

from __future__ import annotations

import asyncio

import pytest

from vulnclaw.web.schemas import TaskCreateRequest

_TERMINAL = {"completed", "failed", "stopped", "interrupted"}


class _DummyMCP:
    def __init__(self, _config):
        pass

    def start_enabled_servers(self):
        return 0

    def stop_all(self):
        pass


def _patch_task_env(monkeypatch, service):
    monkeypatch.setattr(service, "load_config", lambda: object())
    monkeypatch.setattr(service, "init_i18n", lambda **_kwargs: None)
    monkeypatch.setattr(service, "MCPLifecycleManager", _DummyMCP)
    monkeypatch.setattr(service, "AgentCore", lambda *_args, **_kwargs: object())


def _execution(target: str, *, status: str, summary_extra: dict | None = None):
    from vulnclaw.orchestrator import OrchestratorRunResult
    from vulnclaw.target_state.store import SessionRestoreResult
    from vulnclaw.task_service import TaskExecution

    summary = {
        "target": target,
        "command": "run",
        "status": status,
        "run_name": "20260101T000000Z-run-example-abc123",
        "findings_count": 3,
        "verified_count": 2,
        "pending_count": 1,
        "run_dir": "C:/runs/example",
        "artifact_locations": {"reports": "C:/runs/example/reports"},
        **(summary_extra or {}),
    }
    run = OrchestratorRunResult(
        restore_result=SessionRestoreResult(restored=False, target=target),
        summary=summary,
        status=status,
        exit_code=0 if status == "completed" else 1,
    )
    return TaskExecution(run, None)


async def _wait_terminal(manager, task_id, timeout: float = 2.0):
    loop = int(timeout / 0.01)
    record = manager.get_task(task_id)
    for _ in range(loop):
        record = manager.get_task(task_id)
        if record is not None and record.status in _TERMINAL:
            return record
        await asyncio.sleep(0.01)
    return record


@pytest.mark.asyncio
async def test_completed_task_notifies_subscribed_webhooks(monkeypatch):
    import vulnclaw.web.services.task_service as service
    from vulnclaw.web.task_manager import WebTaskManager

    _patch_task_env(monkeypatch, service)

    async def fake_execute(agent, task, **kwargs):
        kwargs["before_action"]()
        return _execution(task.request.target, status="completed")

    monkeypatch.setattr(service, "execute_task", fake_execute)
    notifications: list[dict] = []
    monkeypatch.setattr(service, "notify_run_event", lambda payload: notifications.append(payload))

    manager = WebTaskManager()
    task_id = service.start_task(manager, TaskCreateRequest(command="run", target="example.com"))
    record = await _wait_terminal(manager, task_id)

    assert record is not None and record.status == "completed"
    assert len(notifications) == 1
    payload = notifications[0]
    assert payload["event"] == "run.completed"
    assert payload["task_id"] == task_id
    assert payload["target"] == "example.com"
    assert payload["command"] == "run"
    assert payload["findings_count"] == 3
    assert payload["verified_count"] == 2
    assert payload["reports_dir"] == "C:/runs/example/reports"
    assert payload["error"] == ""


@pytest.mark.asyncio
async def test_failed_task_notifies_with_the_error(monkeypatch):
    import vulnclaw.web.services.task_service as service
    from vulnclaw.web.task_manager import WebTaskManager

    _patch_task_env(monkeypatch, service)

    async def fake_execute(agent, task, **kwargs):
        kwargs["before_action"]()
        return _execution(
            task.request.target, status="failed", summary_extra={"error": "LLM auth failed"}
        )

    monkeypatch.setattr(service, "execute_task", fake_execute)
    notifications: list[dict] = []
    monkeypatch.setattr(service, "notify_run_event", lambda payload: notifications.append(payload))

    manager = WebTaskManager()
    task_id = service.start_task(manager, TaskCreateRequest(command="run", target="example.com"))
    record = await _wait_terminal(manager, task_id)

    assert record is not None and record.status == "failed"
    assert notifications[0]["event"] == "run.failed"
    assert notifications[0]["error"] == "LLM auth failed"


@pytest.mark.asyncio
async def test_notification_failure_does_not_fail_the_task(monkeypatch):
    import vulnclaw.web.services.task_service as service
    from vulnclaw.web.task_manager import WebTaskManager

    _patch_task_env(monkeypatch, service)

    async def fake_execute(agent, task, **kwargs):
        kwargs["before_action"]()
        return _execution(task.request.target, status="completed")

    def boom(_payload):
        raise RuntimeError("relay unreachable")

    monkeypatch.setattr(service, "execute_task", fake_execute)
    monkeypatch.setattr(service, "notify_run_event", boom)

    manager = WebTaskManager()
    task_id = service.start_task(manager, TaskCreateRequest(command="run", target="example.com"))
    record = await _wait_terminal(manager, task_id)

    assert record is not None and record.status == "completed"
