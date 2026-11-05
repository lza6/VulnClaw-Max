"""Finding triage metadata layered on top of persisted target state."""

from __future__ import annotations

from typing import Any

from vulnclaw.run_context import atomic_write_json
from vulnclaw.target_state.store import load_target_state, target_state_path
from vulnclaw.web.schemas import FindingTriageStatus, FindingView

TRIAGE_STATUSES: frozenset[str] = frozenset(
    {"new", "triaged", "confirmed", "false_positive", "fixed", "risk_accepted"}
)


def finding_key(finding: dict[str, Any]) -> str:
    """Stable key matching target_state.store's finding_meta key."""
    return str(
        finding.get("finding_id")
        or f"{finding.get('title', '')}::{finding.get('vuln_type', '')}"
    )


def list_findings(target: str) -> list[FindingView]:
    raw = load_target_state(target)
    if not raw:
        return []
    meta = raw.get("finding_meta") or {}
    views: list[FindingView] = []
    for item in raw.get("findings") or []:
        if not isinstance(item, dict):
            continue
        key = finding_key(item)
        triage = meta.get(key) if isinstance(meta.get(key), dict) else {}
        status = str(triage.get("triage_status") or "new")
        if status not in TRIAGE_STATUSES:
            status = "new"
        views.append(
            FindingView(
                finding_key=key,
                title=str(item.get("title") or ""),
                severity=str(item.get("severity") or ""),
                vuln_type=str(item.get("vuln_type") or ""),
                lifecycle_status=str(item.get("lifecycle_status") or ""),
                verified=bool(item.get("verified")),
                triage_status=status,  # type: ignore[arg-type]
                note=str(triage.get("note") or ""),
                assignee=str(triage.get("assignee") or ""),
            )
        )
    return views


def update_finding(
    target: str,
    finding_key_value: str,
    *,
    triage_status: FindingTriageStatus,
    note: str = "",
    assignee: str = "",
) -> FindingView | None:
    if triage_status not in TRIAGE_STATUSES:
        raise ValueError(f"unsupported triage status: {triage_status}")
    raw = load_target_state(target)
    if not raw:
        return None

    matched = None
    for item in raw.get("findings") or []:
        if isinstance(item, dict) and finding_key(item) == finding_key_value:
            matched = item
            break
    if matched is None:
        return None

    meta = dict(raw.get("finding_meta") or {})
    entry = dict(meta.get(finding_key_value) or {})
    entry.update(
        {
            "triage_status": triage_status,
            "note": note,
            "assignee": assignee,
        }
    )
    meta[finding_key_value] = entry
    raw["finding_meta"] = meta
    atomic_write_json(target_state_path(target), raw)

    return FindingView(
        finding_key=finding_key_value,
        title=str(matched.get("title") or ""),
        severity=str(matched.get("severity") or ""),
        vuln_type=str(matched.get("vuln_type") or ""),
        lifecycle_status=str(matched.get("lifecycle_status") or ""),
        verified=bool(matched.get("verified")),
        triage_status=triage_status,
        note=note,
        assignee=assignee,
    )
