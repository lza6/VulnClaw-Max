"""Target-state service for the Web UI backend."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from vulnclaw.agent.context import SessionState
from vulnclaw.config.settings import TARGETS_DIR, ensure_dirs
from vulnclaw.target_state.store import (
    clear_target_state,
    diff_target_state_snapshots,
    get_target_state_preview,
    list_target_snapshots,
    load_target_state,
    rollback_target_state,
)
from vulnclaw.web.schemas import (
    TargetPreviewView,
    TargetSnapshotView,
    TargetStateDiffView,
    TargetView,
)

logger = logging.getLogger(__name__)


def list_targets(limit: int = 20, project: str | None = None) -> list[TargetView]:
    """List recent targets, preferring the O(1) global index.

    ``project`` filters by the single-owner project index; an empty string means
    targets that are not assigned to any project.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    ensure_dirs()
    allowed: set[str] | None = None
    owned: set[str] | None = None
    if project is not None:
        from vulnclaw.web.services.project_service import (
            owned_targets,
            targets_for_project,
        )

        if project:
            allowed = targets_for_project(project)
        else:
            owned = owned_targets()
    index_path = TARGETS_DIR / "index.json"
    if index_path.exists():
        try:
            indexed = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(indexed, list):
                ordered = sorted(
                    (item for item in indexed if isinstance(item, dict)),
                    key=lambda item: str(item.get("updated_at", "")),
                    reverse=True,
                )
                views: list[TargetView] = []
                for item in ordered:
                    try:
                        view = TargetView(**item)
                    except (TypeError, ValueError, KeyError):
                        continue
                    if owned is not None and view.target in owned:
                        continue
                    if allowed is not None and view.target not in allowed:
                        continue
                    views.append(view)
                    if len(views) >= limit:
                        break
                return views
        except (OSError, json.JSONDecodeError):
            logger.warning("Target index is unreadable; falling back to a directory scan")
    entries: list[tuple[float, Path]] = []
    for state_path in TARGETS_DIR.glob("*/state.json"):
        try:
            entries.append((state_path.stat().st_mtime, state_path))
        except OSError:
            continue
    entries.sort(key=lambda item: item[0], reverse=True)

    views: list[TargetView] = []
    for _mtime_value, state_path in entries:
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
            view = _build_target_view(raw)
        except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Skipping unreadable target state %s: %s", state_path, exc)
            continue
        if owned is not None and view.target in owned:
            continue
        if allowed is not None and view.target not in allowed:
            continue
        views.append(view)
        if len(views) >= limit:
            break
    return views


def get_target(target: str) -> TargetView | None:
    """Load a single target view."""
    raw = load_target_state(target)
    if not raw:
        return None
    return _build_target_view(raw)


def get_target_raw(target: str) -> dict | None:
    """Load raw target state."""
    return load_target_state(target)


def get_snapshots(target: str) -> list[TargetSnapshotView]:
    """Return target snapshots."""
    return [TargetSnapshotView(**item) for item in list_target_snapshots(target)]


def get_preview(target: str, snapshot_id: str | None = None) -> TargetPreviewView | None:
    """Return a preview of the resume plan for a target or snapshot."""
    raw = get_target_state_preview(target, snapshot_id=snapshot_id)
    if not raw:
        return None
    return TargetPreviewView(**raw)


def get_diff(
    target: str, from_snapshot_id: str, to_snapshot_id: str | None = None
) -> TargetStateDiffView | None:
    """Return a diff between two snapshots, or a snapshot and current state."""
    raw = diff_target_state_snapshots(target, from_snapshot_id, to_snapshot_id=to_snapshot_id)
    if not raw:
        return None
    return TargetStateDiffView(**raw)


def rollback_target(target: str, snapshot_id: str) -> bool:
    """Rollback target state to a snapshot."""
    return rollback_target_state(target, snapshot_id) is not None


def clear_target(target: str) -> bool:
    """Clear a target state tree."""
    return clear_target_state(target)


def _build_target_view(raw: dict) -> TargetView:
    session = SessionState(
        **{
            k: v
            for k, v in raw.items()
            if k
            not in {"resume_meta", "resume_summary", "finding_meta", "recon_meta", "runtime_meta"}
        }
    )
    resume_meta = raw.get("resume_meta", {})
    return TargetView(
        target=session.target or resume_meta.get("target", "unknown"),
        schema_version=int(raw.get("schema_version", 1)),
        phase=session.phase.value if hasattr(session.phase, "value") else str(session.phase),
        findings_count=len(session.findings),
        verified_count=len(session.get_verified_findings()),
        pending_count=len(session.get_pending_findings()),
        candidate_count=len(session.get_candidate_findings())
        if hasattr(session, "get_candidate_findings")
        else 0,
        pending_verification_count=(
            len(session.get_pending_verification_findings())
            if hasattr(session, "get_pending_verification_findings")
            else 0
        ),
        manual_review_count=len(session.get_manual_review_findings())
        if hasattr(session, "get_manual_review_findings")
        else 0,
        resume_strategy=resume_meta.get("resume_strategy", ""),
        resume_reason=resume_meta.get("resume_strategy_reason", ""),
        constraints=session.task_constraints.model_dump(mode="json")
        if hasattr(session, "task_constraints")
        else {},
        constraint_violations=list(getattr(session, "constraint_violations", [])),
        constraint_violation_events=[
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in getattr(session, "constraint_violation_events", [])
        ],
        raw=raw,
    )
