"""In-memory task manager for the Web UI backend."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from vulnclaw.config.settings import WEB_EVENTS_DIR, WEB_TASKS_FILE, ensure_dirs
from vulnclaw.run_context import atomic_write_json
from vulnclaw.web.event_bus import EventBus
from vulnclaw.web.schemas import TaskCreateRequest, TaskEvent, TaskRecord, TaskSummary

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = frozenset({"completed", "failed", "stopped", "interrupted"})
_ACTIVE_STATUSES = frozenset({"pending", "queued", "restoring", "running"})
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset(
        {"queued", "restoring", "running", "completed", "stopped", "failed", "interrupted"}
    ),
    "queued": frozenset(
        {"restoring", "running", "completed", "stopped", "failed", "interrupted"}
    ),
    "restoring": frozenset({"running", "completed", "stopped", "failed", "interrupted"}),
    "running": frozenset({"completed", "failed", "stopped", "interrupted"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "stopped": frozenset(),
    "interrupted": frozenset(),
}


def _default_max_concurrent() -> int:
    raw = os.environ.get("VULNCLAW_WEB_MAX_CONCURRENT_TASKS", "1").strip()
    try:
        return max(1, min(4, int(raw)))
    except ValueError:
        return 1


class WebTaskManager:
    """Manage background task state and event streams."""

    def __init__(
        self,
        *,
        max_concurrent: int | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._history: dict[str, deque[TaskEvent]] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._bus = event_bus or EventBus()
        self._max_concurrent = max_concurrent or _default_max_concurrent()
        self._slots: asyncio.Semaphore | None = None
        self._storage_path = WEB_TASKS_FILE
        self._events_dir = WEB_EVENTS_DIR
        self._last_save = 0.0
        self._save_handle: asyncio.TimerHandle | None = None
        self._event_flush_handle: asyncio.TimerHandle | None = None
        self._pending_events: dict[str, list[TaskEvent]] = {}
        self._load_state()

    # ── task records ────────────────────────────────────────────────

    def create_task(self, request: TaskCreateRequest) -> TaskRecord:
        task_id = f"task_{uuid4().hex[:12]}"
        record = TaskRecord(
            task_id=task_id,
            command=request.command,
            target=request.target,
            project_id=request.options.project,
            status="pending",
            resume=request.resume,
            snapshot_id=request.snapshot_id,
            options=request.options,
        )
        self._tasks[task_id] = record
        self._history[task_id] = self._bus.ensure(task_id)
        self._prune_tasks()
        self.publish(
            task_id, "task_created", {"command": request.command, "target": request.target}
        )
        self._schedule_save()
        return record

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return list(self._tasks.values())

    def running_count(self) -> int:
        return sum(
            1 for task in self._tasks.values() if task.status in {"restoring", "running"}
        )

    def queued_count(self) -> int:
        return sum(1 for task in self._tasks.values() if task.status == "queued")

    # ── events ──────────────────────────────────────────────────────

    def publish(self, task_id: str, event: str, payload: dict) -> TaskEvent:
        item = self._bus.publish(task_id, event, payload)
        record = self._tasks.get(task_id)
        if record is not None:
            record.event_seq = item.seq
        self._append_event(task_id, item)
        self._schedule_event_flush()
        return item

    def _transition(
        self,
        task_id: str,
        to_status: str,
        *,
        event: str | None = None,
        payload: dict | None = None,
        **fields,
    ) -> bool:
        record = self._tasks.get(task_id)
        if record is None:
            return False
        if record.status == to_status or record.status in _TERMINAL_STATUSES:
            return False
        allowed = _ALLOWED_TRANSITIONS.get(record.status, frozenset())
        if to_status not in allowed:
            logger.warning(
                "Rejected task transition %s: %s -> %s",
                task_id,
                record.status,
                to_status,
            )
            return False

        record.status = to_status
        for name, value in fields.items():
            setattr(record, name, value)
        self.publish(
            task_id,
            event or f"task_{to_status}",
            payload if payload is not None else {"status": to_status},
        )
        self._schedule_save()
        return True

    def set_queued(self, task_id: str) -> None:
        self._transition(
            task_id,
            "queued",
            event="task_queued",
            payload={"status": "queued"},
        )

    def set_restoring(self, task_id: str, *, snapshot_id: str | None = None) -> None:
        record = self._tasks[task_id]
        self._transition(
            task_id,
            "restoring",
            event="task_restoring",
            payload={
                "status": "restoring",
                "snapshot_id": snapshot_id or record.snapshot_id or "",
            },
            snapshot_id=snapshot_id or record.snapshot_id,
        )

    def set_running(self, task_id: str) -> None:
        self._transition(
            task_id,
            "running",
            event="task_started",
            payload={"status": "running"},
            started_at=datetime.now().isoformat(),
        )

    def set_completed(
        self,
        task_id: str,
        latest_message: str | None = None,
        summary: dict | TaskSummary | None = None,
    ) -> None:
        record = self._tasks[task_id]
        if record.status in _TERMINAL_STATUSES:
            return
        if summary is not None:
            record.summary = summary if isinstance(summary, TaskSummary) else TaskSummary(**summary)
        payload = {"status": "completed", "message": latest_message or ""}
        if record.summary is not None:
            payload["summary"] = record.summary.model_dump(mode="json")
        self._transition(
            task_id,
            "completed",
            event="task_completed",
            payload=payload,
            completed_at=datetime.now().isoformat(),
            latest_message=latest_message,
        )

    def set_failed(self, task_id: str, error: str) -> None:
        self._transition(
            task_id,
            "failed",
            event="task_failed",
            payload={"status": "failed", "error": error},
            completed_at=datetime.now().isoformat(),
            error=error,
            latest_message=error,
        )

    def set_stopped(self, task_id: str) -> None:
        self._transition(
            task_id,
            "stopped",
            event="task_stopped",
            payload={"status": "stopped"},
            completed_at=datetime.now().isoformat(),
        )

    def set_interrupted(self, task_id: str, *, previous_status: str = "") -> None:
        self._transition(
            task_id,
            "interrupted",
            event="task_interrupted",
            payload={"status": "interrupted", "previous_status": previous_status},
            interrupted_at=datetime.now().isoformat(),
        )

    def update_progress(
        self, task_id: str, *, phase: str | None = None, message: str | None = None
    ) -> None:
        record = self._tasks[task_id]
        if phase:
            record.latest_phase = phase
        if message:
            record.latest_message = message
        self._schedule_save()

    async def stream_events(self, task_id: str, *, after_seq: int = 0):
        """Yield ordered events after ``after_seq``; ``None`` is a heartbeat."""
        async for item in self._bus.stream(
            task_id,
            after_seq=after_seq,
            is_terminal=lambda: self._is_terminal(task_id),
        ):
            yield item

    def _is_terminal(self, task_id: str) -> bool:
        record = self._tasks.get(task_id)
        return bool(record and record.status in _TERMINAL_STATUSES)

    # ── runtime task handles and scheduling ─────────────────────────

    def bind_runtime_task(self, task_id: str, task: asyncio.Task) -> None:
        self._running[task_id] = task

    def unbind_runtime_task(self, task_id: str) -> None:
        self._running.pop(task_id, None)

    def _semaphore(self) -> asyncio.Semaphore:
        if self._slots is None:
            self._slots = asyncio.Semaphore(self._max_concurrent)
        return self._slots

    async def acquire_slot(self) -> None:
        await self._semaphore().acquire()

    def release_slot(self) -> None:
        self._semaphore().release()

    async def stop_task(self, task_id: str) -> bool:
        task = self._running.get(task_id)
        record = self._tasks.get(task_id)
        if task is None or record is None or record.status not in _ACTIVE_STATUSES:
            return False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        self.set_stopped(task_id)
        return True

    async def shutdown(self) -> None:
        """Cancel every live task and persist the final state."""
        live = list(self._running.items())
        for _task_id, task in live:
            task.cancel()
        for _task_id, task in live:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._running.clear()
        for task_id, record in self._tasks.items():
            if record.status not in _TERMINAL_STATUSES:
                self.set_stopped(task_id)
        self._flush_save()

    # ── persistence ─────────────────────────────────────────────────

    def _event_path(self, task_id: str) -> Path:
        return self._events_dir / f"{task_id}.jsonl"

    def _append_event(self, task_id: str, item: TaskEvent) -> None:
        self._pending_events.setdefault(task_id, []).append(item)

    def _schedule_event_flush(self) -> None:
        if self._event_flush_handle is not None or not self._pending_events:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._flush_events()
            return
        self._event_flush_handle = loop.call_later(0.3, self._flush_events)

    def _flush_events(self) -> None:
        if self._event_flush_handle is not None:
            self._event_flush_handle.cancel()
            self._event_flush_handle = None
        if not self._pending_events:
            return
        self._events_dir.mkdir(parents=True, exist_ok=True)
        for task_id, events in list(self._pending_events.items()):
            with self._event_path(task_id).open("a", encoding="utf-8") as handle:
                for event in events:
                    handle.write(
                        json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
                        + "\n"
                    )
        self._pending_events.clear()

    def _read_events(self, task_id: str) -> list[TaskEvent]:
        path = self._event_path(task_id)
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        events: list[TaskEvent] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                events.append(TaskEvent(**json.loads(line)))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return events

    def _rewrite_events(self, task_id: str, events: list[TaskEvent]) -> None:
        self._flush_events()
        self._events_dir.mkdir(parents=True, exist_ok=True)
        path = self._event_path(task_id)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(
                    json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n"
                )
        temporary.replace(path)

    def _prune_events(self, task_id: str, events: list[TaskEvent]) -> list[TaskEvent]:
        cutoff = datetime.now() - timedelta(days=7)
        kept: list[TaskEvent] = []
        changed = False
        for event in events:
            try:
                timestamp = datetime.fromisoformat(event.timestamp)
            except ValueError:
                kept.append(event)
                continue
            if timestamp < cutoff:
                changed = True
                continue
            kept.append(event)
        if changed:
            self._rewrite_events(task_id, kept)
        return kept

    def _prune_tasks(self) -> bool:
        if len(self._tasks) <= 200:
            return False
        ordered = sorted(
            self._tasks.values(), key=lambda record: record.created_at, reverse=True
        )
        removed = False
        for record in ordered[200:]:
            self._tasks.pop(record.task_id, None)
            self._history.pop(record.task_id, None)
            self._bus.forget(record.task_id)
            with contextlib.suppress(OSError):
                self._event_path(record.task_id).unlink()
            removed = True
        return removed

    def _schedule_save(self) -> None:
        now = time.monotonic()
        if now - self._last_save >= 0.3:
            self._flush_save()
            return
        if self._save_handle is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._flush_save()
            return
        self._save_handle = loop.call_later(0.3, self._flush_save)

    def _flush_save(self) -> None:
        if self._save_handle is not None:
            self._save_handle.cancel()
            self._save_handle = None
        self._flush_events()
        self._save_state()
        self._last_save = time.monotonic()

    def _save_state(self) -> None:
        ensure_dirs()
        payload = {
            "schema_version": 2,
            "tasks": [
                task.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
                for task in self._tasks.values()
            ],
        }
        atomic_write_json(self._storage_path, payload)

    def _load_state(self) -> None:
        ensure_dirs()
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        for item in raw.get("tasks", []):
            record = TaskRecord(**item)
            self._tasks[record.task_id] = record

        legacy_history = raw.get("history", {})
        changed = False
        for task_id in self._tasks:
            file_events = self._read_events(task_id)
            if file_events:
                events = self._prune_events(task_id, file_events)
            else:
                legacy = [TaskEvent(**item) for item in legacy_history.get(task_id, [])]
                events = self._prune_events(task_id, legacy)
            self._bus.restore(task_id, events)
            if not events:
                self._bus.seed_sequence(task_id, getattr(self._tasks[task_id], "event_seq", 0))
            self._history[task_id] = self._bus.buffer(task_id)
            if not file_events and events:
                self._rewrite_events(task_id, list(self._bus.buffer(task_id)))
                changed = True

        changed = self._prune_tasks() or changed

        for task_id, record in self._tasks.items():
            if record.status in _TERMINAL_STATUSES:
                continue
            previous = record.status
            record.status = "interrupted"
            record.interrupted_at = datetime.now().isoformat()
            item = self._bus.publish(
                task_id,
                "task_interrupted",
                {"status": "interrupted", "previous_status": previous},
            )
            self._append_event(task_id, item)
            changed = True

        if changed:
            self._flush_save()
