"""Constraint audit aggregation service for the Web UI backend."""

from __future__ import annotations

import csv
import io
import json

from vulnclaw.config.settings import TARGETS_DIR, ensure_dirs
from vulnclaw.web.schemas import ConstraintAuditEventView, ConstraintAuditView

_EXPORT_FIELDS = (
    "target",
    "timestamp",
    "code",
    "severity",
    "source",
    "action",
    "tool_name",
    "phase",
    "summary",
    "detail",
)


def collect_constraint_events() -> list[ConstraintAuditEventView]:
    """Collect every constraint audit event across target state."""
    ensure_dirs()
    events: list[ConstraintAuditEventView] = []
    for state_path in TARGETS_DIR.glob("*/state.json"):
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        target = str(raw.get("target") or "unknown")
        for item in raw.get("constraint_violation_events", []):
            if not isinstance(item, dict):
                continue
            try:
                events.append(ConstraintAuditEventView(target=target, **item))
            except (TypeError, ValueError):
                continue
    events.sort(key=lambda item: item.timestamp, reverse=True)
    return events


def get_constraint_audit(limit: int = 30) -> ConstraintAuditView:
    """Aggregate recent constraint audit events across target state."""
    events = collect_constraint_events()
    by_source: dict[str, int] = {}
    by_code: dict[str, int] = {}
    high_severity = 0
    for event in events:
        by_source[event.source or "unknown"] = by_source.get(event.source or "unknown", 0) + 1
        by_code[event.code or "unknown"] = by_code.get(event.code or "unknown", 0) + 1
        if (event.severity or "").lower() == "high":
            high_severity += 1

    return ConstraintAuditView(
        total_events=len(events),
        high_severity_events=high_severity,
        by_source=by_source,
        by_code=by_code,
        recent_events=events[:limit],
    )


def export_constraint_audit(fmt: str = "jsonl") -> tuple[str, str]:
    """Return (content, media_type) for jsonl or csv audit export."""
    events = collect_constraint_events()
    rows = [event.model_dump(mode="json") for event in events]
    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(_EXPORT_FIELDS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue(), "text/csv"
    if fmt != "jsonl":
        raise ValueError("format must be jsonl or csv")
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), "application/x-ndjson"
