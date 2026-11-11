"""Read-only storage accounting and the Web-side gc trigger."""

from __future__ import annotations

from pathlib import Path

from vulnclaw.config.settings import (
    PROJECTS_DIR,
    RUNS_DIR,
    SESSIONS_DIR,
    TARGETS_DIR,
    WEB_EVENTS_DIR,
    WEB_TASKS_FILE,
)
from vulnclaw.gc import prune


def _dir_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    except OSError:
        return 0


def storage_usage() -> dict[str, int]:
    values = {
        "sessions_bytes": _dir_bytes(SESSIONS_DIR),
        "runs_bytes": _dir_bytes(RUNS_DIR),
        "targets_bytes": _dir_bytes(TARGETS_DIR),
        "projects_bytes": _dir_bytes(PROJECTS_DIR),
        "web_events_bytes": _dir_bytes(WEB_EVENTS_DIR),
        "web_tasks_bytes": WEB_TASKS_FILE.stat().st_size if WEB_TASKS_FILE.exists() else 0,
    }
    values["total_bytes"] = sum(values.values())
    return values


def run_gc(*, older_than: int = 30, keep_last: int = 50, dry_run: bool = True) -> dict[str, object]:
    result = prune(older_than_days=older_than, keep_last=keep_last, dry_run=dry_run)
    return {
        "removed": result.removed,
        "freed_bytes": result.freed_bytes,
        "dry_run": dry_run,
        "entries": result.entries,
    }
