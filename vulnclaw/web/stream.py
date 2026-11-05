"""Helpers for server-sent event formatting."""

from __future__ import annotations

import json

from vulnclaw.web.schemas import TaskEvent


def encode_sse(event: TaskEvent) -> str:
    """Encode a task event as an SSE frame with a resumable event id."""
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    frame = f"event: {event.event}\ndata: {payload}\n\n"
    if event.seq > 0:
        return f"id: {event.seq}\n{frame}"
    return frame


def encode_heartbeat() -> str:
    """A comment frame keeps proxies and browsers from closing an idle stream."""
    return ": ping\n\n"
