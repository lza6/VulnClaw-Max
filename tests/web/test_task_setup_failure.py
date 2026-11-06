"""Web tasks must surface setup failures and reject terminal-state rewrites."""

from __future__ import annotations

import asyncio

import pytest

from vulnclaw.web.schemas import TaskCreateRequest


@pytest.mark.asyncio
async def test_setup_failure_marks_task_failed(monkeypatch):
    import vulnclaw.web.services.task_service as service
    from vulnclaw.web.task_manager import WebTaskManager

    class DummyMCP:
        def __init__(self, _config):
            pass

        def start_enabled_servers(self):
            return 0

        def stop_all(self):
            pass

    monkeypatch.setattr(service, "load_config", lambda: object())
    monkeypatch.setattr(service, "init_i18n", lambda **_kwargs: None)
    monkeypatch.setattr(service, "MCPLifecycleManager", DummyMCP)

    def boom(*_args, **_kwargs):
        raise RuntimeError("agent setup failed")

    monkeypatch.setattr(service, "AgentCore", boom)

    manager = WebTaskManager()
    task_id = service.start_task(
        manager, TaskCreateRequest(command="codescan", target="example.com")
    )

    record = manager.get_task(task_id)
    # 落终态与从 _running 摘除是两步：只看终态会在清理完成前就断言，
    # 平台调度一慢就假失败。这里等两件事都成立，下面的断言一条不减。
    for _ in range(100):
        await asyncio.sleep(0.01)
        record = manager.get_task(task_id)
        if (
            record is not None
            and record.status in {"failed", "completed", "stopped"}
            and task_id not in manager._running
        ):
            break

    assert record is not None
    assert record.status == "failed"
    assert "agent setup failed" in (record.error or "")
    assert any(event.event == "task_failed" for event in manager._history[task_id])
    assert task_id not in manager._running


@pytest.mark.asyncio
async def test_stop_rejects_terminal_task_even_with_runtime_handle():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    manager.set_completed(record.task_id, latest_message="done")

    dummy = asyncio.create_task(asyncio.sleep(30))
    manager.bind_runtime_task(record.task_id, dummy)
    try:
        assert await manager.stop_task(record.task_id) is False
    finally:
        dummy.cancel()
        with pytest.raises(asyncio.CancelledError):
            await dummy

    assert manager.get_task(record.task_id).status == "completed"


@pytest.mark.asyncio
async def test_terminal_states_are_idempotent():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    manager.set_completed(record.task_id, latest_message="done")
    manager.set_failed(record.task_id, "late failure")

    assert manager.get_task(record.task_id).status == "completed"
    assert manager.get_task(record.task_id).error is None
