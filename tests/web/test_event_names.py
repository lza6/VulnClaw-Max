"""The browser event whitelist stays in sync with the backend publisher."""

from __future__ import annotations

import re
from pathlib import Path

from vulnclaw.web.event_names import TASK_EVENT_NAMES


def test_frontend_event_names_match_backend():
    root = Path(__file__).resolve().parents[2]
    source = (root / "frontend" / "src" / "api" / "taskEvents.ts").read_text(encoding="utf-8")
    imported = tuple(re.findall(r'"([a-z_]+)"', source))
    assert imported == TASK_EVENT_NAMES
