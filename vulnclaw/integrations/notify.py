"""Run lifecycle notifications for configured integrations.

Findings get a record per finding (see :mod:`dispatch`). A run notification is a
single delivery per terminal run event so a CI pipeline, chat relay, Jira board
or DefectDojo product can react to "scan finished" without polling the task
list. Each kind maps the same event onto its own resource:

- ``webhook`` — the raw event JSON.
- ``jira`` — one issue (``project_key`` = Jira project key).
- ``defectdojo`` — one engagement (``project_key`` = DefectDojo product id).
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from vulnclaw.integrations.dispatch import (
    DeliveryResult,
    IntegrationConfig,
    adf_document,
    dispatch_notification,
)

logger = logging.getLogger(__name__)

RUN_EVENTS = ("run.completed", "run.failed")

_STATUS_LABELS = {"completed": "完成", "failed": "失败", "stopped": "停止", "interrupted": "中断"}


def build_run_notification(
    *,
    event: str,
    task_id: str,
    command: str,
    target: str,
    status: str,
    run_name: str = "",
    findings_count: int = 0,
    verified_count: int = 0,
    pending_count: int = 0,
    run_dir: str = "",
    reports_dir: str = "",
    error: str = "",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build the notification body posted to subscribed integrations."""
    return {
        "event": event,
        "source": "vulnclaw",
        "task_id": task_id,
        "command": command,
        "target": target,
        "run_name": run_name,
        "status": status,
        "findings_count": findings_count,
        "verified_count": verified_count,
        "pending_count": pending_count,
        "run_dir": run_dir,
        "reports_dir": reports_dir,
        "error": error,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


def notification_idempotency_key(payload: dict[str, Any]) -> str:
    """Stable per (task, event) key so a webhook retry is de-duplicable."""
    seed = f"{payload.get('task_id', '')}:{payload.get('event', '')}:{payload.get('status', '')}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _summary_lines(notification: dict[str, Any]) -> list[str]:
    status = str(notification.get("status") or "unknown")
    lines = [
        f"VulnClaw 任务{_STATUS_LABELS.get(status, status)}：{notification.get('command', '')} "
        f"{notification.get('target', '')}",
        f"状态: {status}",
        f"发现: {notification.get('findings_count', 0)} "
        f"(已验证 {notification.get('verified_count', 0)}, 待验证 {notification.get('pending_count', 0)})",
        f"运行: {notification.get('run_name') or notification.get('task_id', '')}",
    ]
    if notification.get("run_dir"):
        lines.append(f"运行目录: {notification['run_dir']}")
    if notification.get("reports_dir"):
        lines.append(f"报告目录: {notification['reports_dir']}")
    if notification.get("error"):
        lines.append(f"错误: {notification['error']}")
    lines.append(f"时间: {notification.get('timestamp', '')}")
    return lines


def _defectdojo_date(notification: dict[str, Any]) -> str:
    raw = str(notification.get("timestamp") or "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return datetime.now(timezone.utc).date().isoformat()


def build_run_payload(config: IntegrationConfig, notification: dict[str, Any]) -> dict[str, Any]:
    """Map one run event onto the payload this integration kind expects.

    Raises ``ValueError`` when the configuration cannot express the event (for
    example a Jira integration without a project key): a doomed request should
    surface as an actionable delivery error, not an opaque HTTP 400.
    """
    if config.kind == "webhook":
        return notification
    if config.kind == "jira":
        if not config.project_key:
            raise ValueError("jira integration needs project_key to receive run notifications")
        status = str(notification.get("status") or "unknown")
        return {
            "fields": {
                "project": {"key": config.project_key},
                "summary": (
                    f"[VulnClaw] {notification.get('command', 'run')} "
                    f"{_STATUS_LABELS.get(status, status)}: {notification.get('target', '')}"
                ),
                "description": adf_document(_summary_lines(notification)),
                "issuetype": {"name": "Task"},
            }
        }
    if not config.project_key:
        raise ValueError(
            "defectdojo integration needs project_key (product id) to receive run notifications"
        )
    status = str(notification.get("status") or "unknown")
    day = _defectdojo_date(notification)
    return {
        "name": (
            f"[VulnClaw] {notification.get('command', 'run')} "
            f"{(notification.get('run_name') or notification.get('task_id', ''))[:64]}"
        ),
        "product": config.project_key,
        "target_start": day,
        "target_end": day,
        "status": "Completed" if status == "completed" else "In Progress",
        "engagement_type": "CI/CD",
        "description": "\n".join(_summary_lines(notification)),
    }


def dispatch_run_notification(
    configs: list[IntegrationConfig],
    notification: dict[str, Any],
    *,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[DeliveryResult]:
    """Deliver the event to every config, isolating per-integration failures."""
    key = notification_idempotency_key(notification)
    results: list[DeliveryResult] = []
    for config in configs:
        try:
            payload = build_run_payload(config, notification)
        except ValueError as exc:
            results.append(DeliveryResult(name=config.name, ok=False, attempts=0, error=str(exc)))
            continue
        try:
            results.append(
                dispatch_notification(
                    config,
                    payload=payload,
                    idempotency_key=key,
                    client=client,
                    sleep=sleep,
                )
            )
        except Exception as exc:  # a broken relay must never fail the run
            logger.warning("Notification to %s failed: %s", config.name, exc)
            results.append(
                DeliveryResult(name=config.name, ok=False, attempts=0, error=str(exc))
            )
    return results
