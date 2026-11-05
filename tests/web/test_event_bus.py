"""Event bus ordering, replay and bounded memory."""

from __future__ import annotations

import asyncio

import pytest

from vulnclaw.web.event_bus import EventBus


@pytest.mark.asyncio
async def test_publish_assigns_monotonic_sequence():
    bus = EventBus(max_events=5)
    first = bus.publish("task", "a", {"i": 1})
    second = bus.publish("task", "a", {"i": 2})
    third = bus.publish("task", "a", {"i": 3})

    assert [first.seq, second.seq, third.seq] == [1, 2, 3]
    assert [event.seq for event in bus.replay("task", after_seq=1)] == [2, 3]


@pytest.mark.asyncio
async def test_buffer_is_bounded_but_sequence_keeps_growing():
    bus = EventBus(max_events=5)
    for index in range(20):
        bus.publish("task", "a", {"i": index})

    assert len(bus.buffer("task")) == 5
    assert bus.next_seq("task") == 20
    assert [event.seq for event in bus.replay("task")] == [16, 17, 18, 19, 20]


@pytest.mark.asyncio
async def test_stream_replays_then_stops_at_terminal():
    bus = EventBus()
    bus.publish("task", "a", {})
    bus.publish("task", "b", {})

    events = [event async for event in bus.stream("task", is_terminal=lambda: True)]

    assert [event.seq for event in events] == [1, 2]


@pytest.mark.asyncio
async def test_stream_honors_after_seq():
    bus = EventBus()
    for _ in range(4):
        bus.publish("task", "a", {})

    events = [
        event
        async for event in bus.stream("task", after_seq=2, is_terminal=lambda: True)
    ]

    assert [event.seq for event in events] == [3, 4]


@pytest.mark.asyncio
async def test_stream_emits_heartbeat_when_idle():
    bus = EventBus(heartbeat_seconds=0.01)
    bus.publish("task", "a", {})

    async def first_heartbeat() -> bool:
        async for item in bus.stream("task", is_terminal=lambda: False):
            if item is None:
                return True
        return False

    assert await asyncio.wait_for(first_heartbeat(), timeout=2)


@pytest.mark.asyncio
async def test_stream_reports_a_gap_when_the_buffer_dropped_events():
    bus = EventBus(max_events=2)
    for _ in range(5):
        bus.publish("task", "a", {})

    events = [event async for event in bus.stream("task", is_terminal=lambda: True)]

    assert events[0].event == "event_gap"
    assert events[0].payload == {"from": 1, "to": 3}
    assert [event.seq for event in events[1:]] == [4, 5]
