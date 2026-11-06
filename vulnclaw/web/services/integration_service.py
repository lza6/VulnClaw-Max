"""Integration configuration, delivery and delivery history for the Web UI."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from vulnclaw.config.settings import INTEGRATIONS_FILE
from vulnclaw.integrations.dispatch import (
    DeliveryResult,
    IntegrationConfig,
    dispatch_findings,
)
from vulnclaw.integrations.notify import (
    RUN_EVENTS,
    build_run_notification,
    dispatch_run_notification,
)
from vulnclaw.run_context import atomic_write_json
from vulnclaw.web.schemas import (
    INTEGRATION_EVENTS,
    IntegrationDeliveryLogView,
    IntegrationUpsertRequest,
    IntegrationView,
)

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = ("http://", "https://")
_MAX_DELIVERY_ENTRIES = 100

# A defect remains after a delivery fails, so delivery history is bounded: the
# settings page needs "did the last notification land?" and "retry it", not an
# unbounded audit trail of one webhook.
DELIVERY_KINDS = ("run", "findings", "test")


def _deliveries_path() -> Path:
    """Delivery history lives beside the integration config it describes."""
    return Path(INTEGRATIONS_FILE).with_name("integration_deliveries.json")


def _load() -> list[dict]:
    path = Path(INTEGRATIONS_FILE)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _events(item: dict) -> list[str]:
    raw = item.get("events")
    if not isinstance(raw, list):
        return list(INTEGRATION_EVENTS)
    return [str(value) for value in raw if str(value) in RUN_EVENTS]


def _config(item: dict) -> IntegrationConfig:
    return IntegrationConfig(
        name=str(item.get("name") or ""),
        kind=str(item.get("kind") or "webhook"),  # type: ignore[arg-type]
        url=str(item.get("url") or ""),
        token=str(item.get("token") or ""),
        project_key=str(item.get("project_key") or ""),
    )


def _view(item: dict) -> IntegrationView:
    return IntegrationView(
        name=str(item.get("name") or ""),
        kind=str(item.get("kind") or "webhook"),
        url=str(item.get("url") or ""),
        project_key=str(item.get("project_key") or ""),
        enabled=bool(item.get("enabled", True)),
        token_configured=bool(item.get("token")),
        events=_events(item),
    )


def list_integrations() -> list[IntegrationView]:
    return [_view(item) for item in _load()]


def save_integration(request: IntegrationUpsertRequest) -> IntegrationView:
    if not request.url.startswith(_ALLOWED_SCHEMES):
        raise ValueError("integration url must use http or https")
    if request.kind == "defectdojo" and request.project_key and not request.project_key.isdigit():
        raise ValueError("defectdojo project_key must be the numeric product id")
    items = _load()
    existing = next((item for item in items if item.get("name") == request.name), {})
    token = request.token or str(existing.get("token") or "")
    record = {
        "name": request.name,
        "kind": request.kind,
        "url": request.url.rstrip("/"),
        "token": token,
        "project_key": request.project_key,
        "enabled": request.enabled,
        "events": [value for value in request.events if value in RUN_EVENTS],
    }
    items = [item for item in items if item.get("name") != request.name]
    items.append(record)
    atomic_write_json(Path(INTEGRATIONS_FILE), items)
    return _view(record)


def delete_integration(name: str) -> bool:
    items = _load()
    remaining = [item for item in items if item.get("name") != name]
    if len(remaining) == len(items):
        return False
    atomic_write_json(Path(INTEGRATIONS_FILE), remaining)
    return True


# ── Delivery history ─────────────────────────────────────────────────


def _load_deliveries() -> list[dict]:
    path = _deliveries_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _record_deliveries(entries: list[dict]) -> None:
    if not entries:
        return
    items = _load_deliveries()
    items.extend(entries)
    try:
        atomic_write_json(_deliveries_path(), items[-_MAX_DELIVERY_ENTRIES:])
    except OSError as exc:  # history is advisory; never fail the delivery
        logger.warning("Could not persist integration delivery history: %s", exc)


def _entry(
    result: DeliveryResult,
    *,
    kind: str,
    event: str = "",
    target: str = "",
    items: int = 0,
    retry_payload: dict | None = None,
) -> dict:
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "name": result.name,
        "kind": kind,
        "event": event,
        "target": target,
        "ok": bool(result.ok),
        "attempts": int(result.attempts),
        "status_code": result.status_code,
        "error": result.error,
        "items": items,
        "retry_payload": retry_payload,
    }


def list_deliveries(name: str | None = None, limit: int = 50) -> list[IntegrationDeliveryLogView]:
    """Return recent deliveries, newest first."""
    entries = _load_deliveries()
    if name:
        entries = [item for item in entries if item.get("name") == name]
    views = [
        IntegrationDeliveryLogView(
            at=str(item.get("at") or ""),
            name=str(item.get("name") or ""),
            kind=str(item.get("kind") or "run"),
            event=str(item.get("event") or ""),
            target=str(item.get("target") or ""),
            ok=bool(item.get("ok")),
            attempts=int(item.get("attempts") or 0),
            status_code=item.get("status_code"),
            error=str(item.get("error") or ""),
            items=int(item.get("items") or 0),
            retryable=bool(item.get("retry_payload")),
        )
        for item in entries
    ]
    # 同一时间戳时按写入顺序定序（后写的更新）：Windows 的 now() 精度在 15.6 ms 量级，
    # 两次投递落在同一个 tick 里会得到完全相同的 at，只按 at 排序时先后不确定。
    indexed = sorted(enumerate(views), key=lambda pair: (pair[1].at, pair[0]), reverse=True)
    return [view for _, view in indexed][: max(1, limit)]


# ── Delivery ─────────────────────────────────────────────────────────


def dispatch_integrations(
    target: str,
    run_name: str,
    findings: list[dict],
    *,
    client: httpx.Client | None = None,
) -> list[DeliveryResult]:
    results: list[DeliveryResult] = []
    for item in _load():
        if not item.get("enabled", True):
            continue
        results.extend(
            dispatch_findings(
                _config(item),
                target=target,
                run_name=run_name,
                findings=findings,
                client=client,
            )
        )
    _record_deliveries(
        [
            _entry(result, kind="findings", event="findings", target=target, items=len(findings))
            for result in results
        ]
    )
    return results


def notify_run_event(
    payload: dict,
    *,
    client: httpx.Client | None = None,
) -> list[DeliveryResult]:
    """Deliver a run lifecycle notification to every subscribed integration."""
    event = str(payload.get("event") or "")
    if event not in RUN_EVENTS:
        raise ValueError(f"unsupported run event: {event}")
    configs = [
        _config(item)
        for item in _load()
        if item.get("enabled", True) and event in _events(item)
    ]
    if not configs:
        return []
    results = dispatch_run_notification(configs, payload, client=client)
    for result in results:
        if not result.ok:
            logger.warning(
                "Run notification %s to %s failed after %s attempt(s): %s",
                event,
                result.name,
                result.attempts,
                result.error,
            )
    _record_deliveries(
        [
            _entry(
                result,
                kind="run",
                event=event,
                target=str(payload.get("target") or ""),
                items=int(payload.get("findings_count") or 0),
                retry_payload=payload,
            )
            for result in results
        ]
    )
    return results


def retry_last_failed_delivery(
    name: str, *, client: httpx.Client | None = None
) -> DeliveryResult | None:
    """Re-send the most recent failed run notification for one integration."""
    entries = [
        item for item in _load_deliveries() if item.get("name") == name and item.get("kind") == "run"
    ]
    if not entries:
        return None
    entry = entries[-1]
    # Only the newest run delivery is retryable: once a later attempt (or a newer
    # run) succeeded, an older failure is history, not something to re-send.
    if entry.get("ok") or not entry.get("retry_payload"):
        return None
    item = next((row for row in _load() if row.get("name") == name), None)
    if item is None:
        return None
    results = dispatch_run_notification([_config(item)], entry["retry_payload"], client=client)
    if not results:
        return None
    result = results[0]
    _record_deliveries(
        [
            _entry(
                result,
                kind="run",
                event=str(entry.get("event") or ""),
                target=str(entry.get("target") or ""),
                items=int(entry.get("items") or 0),
                retry_payload=entry["retry_payload"],
            )
        ]
    )
    return result


def test_integration(name: str, *, client: httpx.Client | None = None) -> DeliveryResult | None:
    """Send one synthetic delivery so an operator can verify a configuration."""
    item = next((entry for entry in _load() if entry.get("name") == name), None)
    if item is None:
        return None
    config = _config(item)
    if config.kind == "webhook":
        payload = build_run_notification(
            event="run.completed",
            task_id=f"test-{name}",
            command="run",
            target="example.com",
            status="completed",
            run_name="integration-test",
            findings_count=1,
            verified_count=1,
        )
        payload["test"] = True
        result = dispatch_run_notification([config], payload, client=client)[0]
    else:
        results = dispatch_findings(
            config,
            target="example.com",
            run_name="integration-test",
            findings=[
                {
                    "title": "VulnClaw integration test",
                    "severity": "Info",
                    "description": "Synthetic finding used to verify this integration.",
                    "verified": False,
                }
            ],
            client=client,
        )
        result = results[0] if results else None
    if result is not None:
        _record_deliveries([_entry(result, kind="test", event="test", target="example.com")])
    return result
