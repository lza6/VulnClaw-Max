"""SSE stream must be duplicate-free, resumable, and bounded."""

from __future__ import annotations

import asyncio

import pytest

from vulnclaw.web.schemas import TaskCreateRequest
from vulnclaw.web.stream import encode_heartbeat, encode_sse


@pytest.mark.asyncio
async def test_stream_has_no_duplicates_and_stops_at_terminal():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    manager.set_queued(record.task_id)
    manager.set_running(record.task_id)
    manager.set_completed(record.task_id, latest_message="done")

    events = [
        event
        async for event in manager.stream_events(record.task_id)
        if event is not None
    ]

    seqs = [event.seq for event in events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))
    assert events[-1].event == "task_completed"


@pytest.mark.asyncio
async def test_stream_after_seq_replays_only_the_gap():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    first = manager.get_task(record.task_id)
    manager.set_completed(record.task_id, latest_message="done")

    events = [
        event
        async for event in manager.stream_events(record.task_id, after_seq=1)
        if event is not None
    ]

    assert all(event.seq > 1 for event in events)
    assert events[-1].event == "task_completed"
    assert first.status == "completed"


@pytest.mark.asyncio
async def test_stream_emits_heartbeat_for_live_task():
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager()
    record = manager.create_task(
        TaskCreateRequest(command="codescan", target="example.com")
    )
    manager._bus.heartbeat_seconds = 0.01

    async def wait_for_heartbeat() -> bool:
        async for item in manager.stream_events(record.task_id):
            if item is None:
                return True
        return False

    assert await asyncio.wait_for(wait_for_heartbeat(), timeout=2)


def test_heartbeat_and_event_frames_include_ids():
    from vulnclaw.web.schemas import TaskEvent

    event = TaskEvent(event="task_started", task_id="t", seq=7)
    frame = encode_sse(event)
    assert frame.startswith("id: 7\n")
    assert "event: task_started" in frame
    assert encode_heartbeat() == ": ping\n\n"


def test_task_event_schema_accepts_legacy_payload_without_seq():
    from vulnclaw.web.schemas import TaskEvent

    event = TaskEvent(event="task_started", task_id="t")
    assert event.seq == 0


def test_events_after_returns_a_bounded_rest_page():
    from vulnclaw.task_service import TaskCreateRequest
    from vulnclaw.web.task_manager import WebTaskManager

    manager = WebTaskManager(max_concurrent=1)
    record = manager.create_task(TaskCreateRequest(command="codescan", target="example.com"))
    for index in range(5):
        manager.publish(record.task_id, "round_output", {"index": index})

    page = manager.events_after(record.task_id, after_seq=1, limit=2)

    assert [event.seq for event in page] == [2, 3]
