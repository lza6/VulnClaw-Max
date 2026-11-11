"""Prune old session, run and target-state directories."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GCResult:
    removed: int = 0
    freed_bytes: int = 0
    entries: list[dict[str, object]] = field(default_factory=list)


def _dir_size(path: Path) -> int:
    try:
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    except OSError:
        return 0


def prune(
    *,
    older_than_days: int = 30,
    keep_last: int = 50,
    dry_run: bool = False,
) -> GCResult:
    """Delete directories older than the cutoff, always keeping the newest N.

    Paths are read from ``vulnclaw.config.settings`` at call time so tests and
    callers can redirect the roots.
    """
    from vulnclaw.config import settings

    roots = (
        ("sessions", settings.SESSIONS_DIR),
        ("runs", settings.RUNS_DIR),
        ("targets", settings.TARGETS_DIR),
    )
    cutoff = time.time() - max(1, older_than_days) * 86400
    result = GCResult()
    for label, root in roots:
        if not root.exists():
            continue
        entries = [path for path in root.iterdir() if path.is_dir() and not path.is_symlink()]
        entries.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for index, path in enumerate(entries):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if index < keep_last or mtime >= cutoff:
                continue
            size = _dir_size(path)
            if not dry_run:
                shutil.rmtree(path, ignore_errors=True)
            result.removed += 1
            result.freed_bytes += size
            result.entries.append({"root": label, "name": path.name, "bytes": size})
    return result
