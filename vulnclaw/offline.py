"""Offline-mode helpers for air-gapped and intranet deployments."""

from __future__ import annotations

import os


def is_offline() -> bool:
    return os.environ.get("VULNCLAW_OFFLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
