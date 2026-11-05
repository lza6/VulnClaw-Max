"""Integration config persistence and dispatch."""

from __future__ import annotations

import json

import httpx

from vulnclaw.web.schemas import IntegrationUpsertRequest


def _service(monkeypatch, tmp_path):
    import vulnclaw.web.services.integration_service as service

    monkeypatch.setattr(service, "INTEGRATIONS_FILE", tmp_path / "integrations.json")
    return service


def test_save_list_and_delete(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    service.save_integration(
        IntegrationUpsertRequest(
            name="hook",
            kind="webhook",
            url="https://hooks.example/vc",
            token="secret",
        )
    )

    listed = service.list_integrations()
    assert listed[0].name == "hook"
    assert listed[0].token_configured is True
    assert not hasattr(listed[0], "token")

    service.save_integration(
        IntegrationUpsertRequest(
            name="hook", kind="webhook", url="https://hooks.example/vc2"
        )
    )
    assert service.list_integrations()[0].url.endswith("vc2")
    assert service.list_integrations()[0].token_configured is True
    assert service.delete_integration("hook") is True
    assert service.list_integrations() == []


def test_dispatch_uses_configured_webhook(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    service.save_integration(
        IntegrationUpsertRequest(name="hook", kind="webhook", url="https://hooks.example/vc")
    )
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    results = service.dispatch_integrations(
        "https://example.com",
        "run-1",
        [{"title": "SQL Injection", "severity": "High"}],
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert results[0].ok
    assert seen["body"]["finding"]["title"] == "SQL Injection"


def test_invalid_url_is_rejected(monkeypatch, tmp_path):
    import pytest

    service = _service(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        service.save_integration(
            IntegrationUpsertRequest(name="bad", kind="webhook", url="file:///etc/passwd")
        )


def test_events_are_persisted_and_default_to_both_run_events(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)

    defaulted = service.save_integration(
        IntegrationUpsertRequest(name="hook", kind="webhook", url="https://hooks.example/vc")
    )
    assert defaulted.events == ["run.completed", "run.failed"]

    narrowed = service.save_integration(
        IntegrationUpsertRequest(
            name="hook",
            kind="webhook",
            url="https://hooks.example/vc",
            events=["run.failed"],
        )
    )
    assert narrowed.events == ["run.failed"]
    assert service.list_integrations()[0].events == ["run.failed"]

    muted = service.save_integration(
        IntegrationUpsertRequest(
            name="hook", kind="webhook", url="https://hooks.example/vc", events=[]
        )
    )
    assert muted.events == []


def test_notify_run_event_posts_only_to_subscribed_integrations(monkeypatch, tmp_path):
    from vulnclaw.integrations.dispatch import DeliveryResult
    from vulnclaw.integrations.notify import build_run_notification

    service = _service(monkeypatch, tmp_path)
    service.save_integration(
        IntegrationUpsertRequest(
            name="watcher", kind="webhook", url="https://hooks.example/watch"
        )
    )
    service.save_integration(
        IntegrationUpsertRequest(
            name="failures-only",
            kind="webhook",
            url="https://hooks.example/fail",
            events=["run.failed"],
        )
    )
    service.save_integration(
        IntegrationUpsertRequest(
            name="disabled",
            kind="webhook",
            url="https://hooks.example/off",
            enabled=False,
        )
    )
    service.save_integration(
        IntegrationUpsertRequest(
            name="jira-watch",
            kind="jira",
            url="https://jira.example",
            project_key="SEC",
        )
    )

    hits: list[tuple[str, dict]] = []

    def fake_dispatch(configs, payload, *, client=None, sleep=None):
        for config in configs:
            hits.append((config.url, payload))
        return [
            DeliveryResult(name=config.name, ok=True, attempts=1, status_code=200)
            for config in configs
        ]

    monkeypatch.setattr(service, "dispatch_run_notification", fake_dispatch)

    payload = build_run_notification(
        event="run.completed",
        task_id="task-1",
        command="run",
        target="example.com",
        status="completed",
        findings_count=2,
        verified_count=1,
    )
    results = service.notify_run_event(payload)

    assert [url for url, _ in hits] == ["https://hooks.example/watch", "https://jira.example"]
    assert hits[0][1]["event"] == "run.completed"
    assert hits[0][1]["findings_count"] == 2
    assert hits[1][1]["event"] == "run.completed"
    assert len(results) == 2


def test_notify_run_event_rejects_unknown_events(monkeypatch, tmp_path):
    import pytest

    service = _service(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        service.notify_run_event({"event": "run.exploded", "task_id": "t"})


def test_test_integration_sends_a_marked_probe(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    service.save_integration(
        IntegrationUpsertRequest(name="hook", kind="webhook", url="https://hooks.example/vc")
    )
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx.Response(204)

    result = service.test_integration(
        "hook", client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    assert result is not None and result.ok and result.attempts == 1
    assert seen["url"] == "https://hooks.example/vc"
    assert seen["body"]["test"] is True
    assert seen["body"]["event"] == "run.completed"
    assert service.test_integration("missing") is None


def test_jira_without_project_key_reports_an_actionable_failure(monkeypatch, tmp_path):
    from vulnclaw.integrations.notify import build_run_notification

    service = _service(monkeypatch, tmp_path)
    service.save_integration(
        IntegrationUpsertRequest(name="jira", kind="jira", url="https://jira.example")
    )

    results = service.notify_run_event(
        build_run_notification(
            event="run.failed", task_id="t1", command="run", target="t", status="failed"
        )
    )

    assert results[0].ok is False
    assert results[0].attempts == 0
    assert "project_key" in results[0].error


def test_defectdojo_requires_a_numeric_product_id(monkeypatch, tmp_path):
    import pytest

    service = _service(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="numeric product id"):
        service.save_integration(
            IntegrationUpsertRequest(
                name="dd", kind="defectdojo", url="https://dd.example", project_key="acme"
            )
        )


def test_delivery_history_records_and_retries_failures(monkeypatch, tmp_path):
    from vulnclaw.integrations.notify import build_run_notification

    service = _service(monkeypatch, tmp_path)
    service.save_integration(
        IntegrationUpsertRequest(name="hook", kind="webhook", url="https://hooks.example/vc")
    )
    attempts: list[dict] = []

    def failing_dispatch(configs, notification, *, client=None, sleep=None):
        from vulnclaw.integrations.dispatch import DeliveryResult

        attempts.append(notification)
        return [
            DeliveryResult(name=c.name, ok=False, attempts=3, status_code=503, error="HTTP 503")
            for c in configs
        ]

    monkeypatch.setattr(service, "dispatch_run_notification", failing_dispatch)
    payload = build_run_notification(
        event="run.completed",
        task_id="task-9",
        command="run",
        target="example.com",
        status="completed",
        findings_count=4,
    )
    service.notify_run_event(payload)

    history = service.list_deliveries("hook")
    assert len(history) == 1
    assert history[0].ok is False
    assert history[0].retryable is True
    assert history[0].status_code == 503
    assert history[0].items == 4

    def succeeding_dispatch(configs, notification, *, client=None, sleep=None):
        from vulnclaw.integrations.dispatch import DeliveryResult

        attempts.append(notification)
        return [
            DeliveryResult(name=c.name, ok=True, attempts=1, status_code=200) for c in configs
        ]

    monkeypatch.setattr(service, "dispatch_run_notification", succeeding_dispatch)
    result = service.retry_last_failed_delivery("hook")

    assert result is not None and result.ok
    assert attempts[-1]["task_id"] == "task-9"
    latest = service.list_deliveries("hook")
    assert latest[0].ok is True
    # Nothing left to retry once the last delivery succeeded.
    assert service.retry_last_failed_delivery("hook") is None


def test_delivery_history_is_bounded_and_isolated_per_integration(monkeypatch, tmp_path):
    from vulnclaw.integrations.dispatch import DeliveryResult

    service = _service(monkeypatch, tmp_path)
    monkeypatch.setattr(
        service,
        "_MAX_DELIVERY_ENTRIES",
        3,
    )
    for index in range(5):
        service._record_deliveries(
            [
                {
                    "at": f"2026-01-01T00:00:0{index}+00:00",
                    "name": "hook",
                    "kind": "run",
                    "event": "run.completed",
                    "target": "t",
                    "ok": True,
                    "attempts": 1,
                    "status_code": 200,
                    "error": "",
                    "items": 0,
                    "retry_payload": None,
                }
            ]
        )

    history = service.list_deliveries("hook")
    assert len(history) == 3
    assert history[0].at.startswith("2026-01-01T00:00:04")
    assert service.list_deliveries("other") == []
    assert DeliveryResult(name="hook", ok=True, attempts=1)
