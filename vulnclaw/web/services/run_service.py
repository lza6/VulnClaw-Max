"""Read-only access to persisted run artifacts for the Web UI."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from vulnclaw.config.settings import RUNS_DIR, ensure_dirs
from vulnclaw.web.schemas import RunDetailView, RunEventView, RunPhaseView, RunSummaryView

logger = logging.getLogger(__name__)

_MAX_EVENTS = 500


def list_runs(limit: int = 50) -> list[RunSummaryView]:
    """List recent runs, newest first, tolerating one corrupt manifest."""
    if limit < 1:
        raise ValueError("limit must be positive")
    ensure_dirs()
    entries: list[tuple[float, Path]] = []
    for manifest in RUNS_DIR.glob("*/run.json"):
        try:
            entries.append((manifest.stat().st_mtime, manifest))
        except OSError:
            continue
    entries.sort(key=lambda item: item[0], reverse=True)

    views: list[RunSummaryView] = []
    for _mtime, manifest in entries[:limit]:
        try:
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            views.append(_summary(raw))
        except (OSError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            logger.warning("Skipping unreadable run manifest %s: %s", manifest, exc)
    return views


def get_run(run_name: str) -> RunDetailView | None:
    """Load one run by name; reject separators so callers cannot escape RUNS_DIR."""
    if not run_name or "/" in run_name or "\\" in run_name or run_name in {".", ".."}:
        return None
    run_dir = RUNS_DIR / run_name
    manifest = run_dir / "run.json"
    if not manifest.is_file():
        return None
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None

    summary = _summary(raw)
    events = _read_events(run_dir / "events" / "events.jsonl")
    return RunDetailView(
        **summary.model_dump(),
        run_dir=run_name,
        artifacts=dict(raw.get("artifacts") or {}),
        resume=dict(raw.get("resume") or {}),
        events=events,
        phases=_build_phases(events),
        findings=_read_findings(run_dir / "findings" / "findings.json"),
        reports=_list_reports(run_dir / "reports"),
    )


def _build_phases(events: list[RunEventView]) -> list[RunPhaseView]:
    """Group persisted run events by kind and compute their wall-clock span."""
    groups: dict[str, list[tuple[datetime, str]]] = {}
    for event in events:
        timestamp = event.timestamp
        if not timestamp:
            continue
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            continue
        groups.setdefault(event.kind or "event", []).append((parsed, timestamp))

    phases: list[RunPhaseView] = []
    for name, items in groups.items():
        items.sort(key=lambda item: item[0])
        started, started_raw = items[0]
        ended, ended_raw = items[-1]
        phases.append(
            RunPhaseView(
                name=name,
                started_at=started_raw,
                ended_at=ended_raw,
                duration_seconds=max(0.0, (ended - started).total_seconds()),
                event_count=len(items),
            )
        )
    phases.sort(key=lambda item: item.started_at)
    return phases


def _summary(raw: dict) -> RunSummaryView:
    targets = []
    for item in raw.get("targets") or []:
        if isinstance(item, dict):
            targets.append(str(item.get("canonical") or item.get("input") or ""))
    return RunSummaryView(
        run_name=str(raw.get("run_name") or ""),
        command=str(raw.get("command") or ""),
        status=str(raw.get("status") or ""),
        created_at=str(raw.get("created_at") or ""),
        started_at=str(raw.get("started_at") or ""),
        ended_at=str(raw.get("ended_at") or ""),
        exit_code=int(raw.get("exit_code") or 0),
        message=str(raw.get("message") or ""),
        targets=[target for target in targets if target],
    )


def _read_events(path: Path) -> list[RunEventView]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[RunEventView] = []
    for line in lines[-_MAX_EVENTS:]:
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        events.append(
            RunEventView(
                timestamp=str(raw.get("timestamp") or ""),
                kind=str(raw.get("kind") or raw.get("event") or ""),
                payload=dict(raw.get("payload") or {}),
            )
        )
    return events


def _read_findings(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, (dict, list)) else None


def _list_reports(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    reports = []
    for item in sorted(path.iterdir(), key=lambda entry: entry.name):
        if item.is_file():
            reports.append(item.name)
    return reports[:100]
