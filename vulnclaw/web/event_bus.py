"""Ordered, bounded per-task event bus for the Web UI.

The previous implementation had two independent channels (a deque and an
``asyncio.Queue``) for the same events, so every subscriber saw each event
twice and a disconnected subscriber left an unbounded queue behind. This bus
owns a single monotonically numbered ring buffer per task; subscribers replay
from a cursor and wait on their own ``asyncio.Event``.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Callable
from datetime import datetime

from vulnclaw.web.schemas import TaskEvent


class EventSubscription:
    """A single subscriber's wake-up handle."""

    def __init__(self, bus: "EventBus", task_id: str) -> None:
        self._bus = bus
        self.task_id = task_id
        self.event = asyncio.Event()

    def close(self) -> None:
        self._bus.close_subscription(self.task_id, self.event)


class EventBus:
    """Per-task ring buffer with monotonic sequence numbers."""

    def __init__(self, *, max_events: int = 2000, heartbeat_seconds: float = 15.0) -> None:
        self._buffers: dict[str, deque[TaskEvent]] = {}
        self._sequences: dict[str, int] = {}
        self._listeners: dict[str, set[asyncio.Event]] = {}
        self.max_events = max_events
        self.heartbeat_seconds = heartbeat_seconds

    def ensure(self, task_id: str) -> deque[TaskEvent]:
        return self._buffers.setdefault(task_id, deque(maxlen=self.max_events))

    def buffer(self, task_id: str) -> deque[TaskEvent]:
        return self.ensure(task_id)

    def forget(self, task_id: str) -> None:
        """Drop all in-memory state for a pruned task."""
        self._buffers.pop(task_id, None)
        self._sequences.pop(task_id, None)
        self._listeners.pop(task_id, None)

    def next_seq(self, task_id: str) -> int:
        return self._sequences.get(task_id, 0)

    def seed_sequence(self, task_id: str, sequence: int) -> None:
        self._sequences[task_id] = max(self.next_seq(task_id), int(sequence))

    def restore(self, task_id: str, events: list[TaskEvent]) -> None:
        """Rebuild a task buffer from persisted events after a restart."""
        buffer = deque(maxlen=self.max_events)
        highest = 0
        for event in events:
            if event.seq <= 0:
                highest += 1
                event.seq = highest
            else:
                highest = max(highest, event.seq)
            buffer.append(event)
        self._buffers[task_id] = buffer
        self._sequences[task_id] = highest

    def publish(self, task_id: str, event: str, payload: dict) -> TaskEvent:
        sequence = self.next_seq(task_id) + 1
        self._sequences[task_id] = sequence
        item = TaskEvent(
            event=event,
            task_id=task_id,
            timestamp=datetime.now().isoformat(),
            payload=payload,
            seq=sequence,
        )
        self.ensure(task_id).append(item)
        for wakeup in self._listeners.get(task_id, ()):
            wakeup.set()
        return item

    def subscribe(self, task_id: str) -> EventSubscription:
        subscription = EventSubscription(self, task_id)
        self._listeners.setdefault(task_id, set()).add(subscription.event)
        return subscription

    def close_subscription(self, task_id: str, wakeup: asyncio.Event) -> None:
        listeners = self._listeners.get(task_id)
        if listeners is None:
            return
        listeners.discard(wakeup)
        if not listeners:
            self._listeners.pop(task_id, None)

    def replay(self, task_id: str, after_seq: int = 0) -> list[TaskEvent]:
        return [event for event in self.ensure(task_id) if event.seq > after_seq]

    def has_after(self, task_id: str, after_seq: int) -> bool:
        return any(event.seq > after_seq for event in self.ensure(task_id))

    async def stream(
        self,
        task_id: str,
        *,
        after_seq: int = 0,
        is_terminal: Callable[[], bool],
        heartbeat_seconds: float | None = None,
    ) -> AsyncIterator[TaskEvent | None]:
        """Yield events after ``after_seq``; ``None`` means a heartbeat tick."""
        timeout = self.heartbeat_seconds if heartbeat_seconds is None else heartbeat_seconds
        subscription = self.subscribe(task_id)
        cursor = after_seq
        try:
            buffer = self.ensure(task_id)
            if buffer and after_seq < buffer[0].seq - 1:
                yield TaskEvent(
                    event="event_gap",
                    task_id=task_id,
                    payload={
                        "from": after_seq + 1,
                        "to": buffer[0].seq - 1,
                    },
                    seq=0,
                )
            while True:
                pending = self.replay(task_id, cursor)
                if pending:
                    for event in pending:
                        cursor = event.seq
                        yield event
                    continue

                if is_terminal():
                    return

                subscription.event.clear()
                # A publish between the replay above and the clear() above would
                # be lost; re-check the buffer after clearing to close that gap.
                if self.has_after(task_id, cursor):
                    continue

                try:
                    await asyncio.wait_for(subscription.event.wait(), timeout=timeout)
                except (asyncio.TimeoutError, TimeoutError):
                    yield None
        finally:
            subscription.close()
