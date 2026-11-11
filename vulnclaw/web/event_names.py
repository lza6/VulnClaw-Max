"""Canonical task event names shared by the Web UI and its SSE client.

The browser ``EventSource`` only invokes a listener for an exact ``event:``
name, so the frontend must know every name the backend can publish. Keep this
tuple and ``frontend/src/api/taskEvents.ts`` in sync; a test enforces it.
"""

from __future__ import annotations

TASK_EVENT_NAMES: tuple[str, ...] = (
    "task_created",
    "task_queued",
    "task_restoring",
    "task_started",
    "task_state_changed",
    "legacy_import",
    "round_output",
    "cycle_completed",
    "task_completed",
    "task_failed",
    "task_stopped",
    "task_interrupted",
    "event_gap",
)
