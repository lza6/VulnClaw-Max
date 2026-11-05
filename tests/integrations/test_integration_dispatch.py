"""Integration delivery: payload shape, retries, idempotency and no-retry 4xx."""

from __future__ import annotations

import json

import httpx

from vulnclaw.integrations.dispatch import IntegrationConfig, dispatch_findings

FINDING = {
    "title": "SQL Injection",
    "severity": "High",
    "description": "confirmed",
    "evidence": "1=1",
    "verified": True,
}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_webhook_payload_and_idempotency_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("Idempotency-Key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    config = IntegrationConfig(name="hook", kind="webhook", url="https://hooks.example/vc")
    results = dispatch_findings(
        config,
        target="https://example.com",
        run_name="run-1",
        findings=[FINDING],
        client=_client(handler),
        sleep=lambda _seconds: None,
    )

    assert results[0].ok
    assert seen["url"] == "https://hooks.example/vc"
    assert seen["key"]
    assert seen["body"]["finding"]["title"] == "SQL Injection"
    assert seen["body"]["run_name"] == "run-1"


def test_retries_server_errors_then_succeeds():
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(503)
        return httpx.Response(201, json={})

    config = IntegrationConfig(name="hook", kind="webhook", url="https://hooks.example", retries=3)
    results = dispatch_findings(
        config,
        target="t",
        run_name="r",
        findings=[FINDING],
        client=_client(handler),
        sleep=lambda _seconds: None,
    )

    assert calls["count"] == 3
    assert results[0].ok
    assert results[0].attempts == 3


def test_client_errors_are_not_retried():
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"error": "bad"})

    config = IntegrationConfig(name="hook", kind="webhook", url="https://hooks.example", retries=3)
    results = dispatch_findings(
        config,
        target="t",
        run_name="r",
        findings=[FINDING],
        client=_client(handler),
        sleep=lambda _seconds: None,
    )

    assert calls["count"] == 1
    assert not results[0].ok
    assert results[0].status_code == 400


def test_jira_payload_and_endpoint():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"key": "VC-1"})

    config = IntegrationConfig(
        name="jira",
        kind="jira",
        url="https://jira.example",
        token="jira-token",
        project_key="VC",
    )
    results = dispatch_findings(
        config,
        target="https://example.com",
        run_name="run-1",
        findings=[FINDING],
        client=_client(handler),
        sleep=lambda _seconds: None,
    )

    assert results[0].ok
    assert seen["url"].endswith("/rest/api/3/issue")
    assert seen["body"]["fields"]["project"]["key"] == "VC"
    assert "SQL Injection" in seen["body"]["fields"]["summary"]


def test_defectdojo_payload_and_token_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": 1})

    config = IntegrationConfig(
        name="dd",
        kind="defectdojo",
        url="https://dd.example/",
        token="dd-token",
    )
    results = dispatch_findings(
        config,
        target="t",
        run_name="r",
        findings=[FINDING],
        client=_client(handler),
        sleep=lambda _seconds: None,
    )

    assert results[0].ok
    assert seen["url"].endswith("/api/v2/findings/")
    assert seen["auth"] == "Token dd-token"
    assert seen["body"]["title"] == "SQL Injection"


# ── Run lifecycle notifications ──────────────────────────────────────


def _notification(**overrides):
    from vulnclaw.integrations.notify import build_run_notification

    base = {
        "event": "run.completed",
        "task_id": "task-1",
        "command": "run",
        "target": "https://example.com",
        "status": "completed",
        "run_name": "20260101T000000Z-run-example",
        "findings_count": 3,
        "verified_count": 2,
        "pending_count": 1,
        "run_dir": "C:/runs/example",
        "reports_dir": "C:/runs/example/reports",
        "timestamp": "2026-01-01T10:00:00+00:00",
    }
    base.update(overrides)
    return build_run_notification(**base)


def test_webhook_run_notification_posts_the_raw_event():
    from vulnclaw.integrations.notify import dispatch_run_notification

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers.get("Idempotency-Key")
        return httpx.Response(202)

    config = IntegrationConfig(name="hook", kind="webhook", url="https://hooks.example/vc")
    results = dispatch_run_notification(
        [config], _notification(), client=_client(handler), sleep=lambda _s: None
    )

    assert results[0].ok
    assert seen["url"] == "https://hooks.example/vc"
    assert seen["body"]["event"] == "run.completed"
    assert seen["body"]["findings_count"] == 3
    assert seen["key"]


def test_jira_run_notification_creates_an_issue_with_adf_description():
    from vulnclaw.integrations.notify import dispatch_run_notification

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"key": "SEC-7"})

    config = IntegrationConfig(
        name="jira", kind="jira", url="https://jira.example", token="t", project_key="SEC"
    )
    results = dispatch_run_notification(
        [config], _notification(), client=_client(handler), sleep=lambda _s: None
    )

    assert results[0].ok
    assert seen["url"].endswith("/rest/api/3/issue")
    fields = seen["body"]["fields"]
    assert fields["project"]["key"] == "SEC"
    assert fields["issuetype"]["name"] == "Task"
    assert "VulnClaw" in fields["summary"]
    # Jira Cloud v3 needs ADF, not a plain string.
    assert fields["description"]["type"] == "doc"
    paragraphs = fields["description"]["content"]
    assert paragraphs[0]["content"][0]["text"].startswith("VulnClaw 任务")


def test_jira_run_notification_requires_a_project_key():
    from vulnclaw.integrations.notify import dispatch_run_notification

    config = IntegrationConfig(name="jira", kind="jira", url="https://jira.example")
    results = dispatch_run_notification([config], _notification())

    assert results[0].ok is False
    assert results[0].attempts == 0
    assert "project_key" in results[0].error


def test_defectdojo_run_notification_creates_an_engagement():
    from vulnclaw.integrations.notify import dispatch_run_notification

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(201, json={"id": 42})

    config = IntegrationConfig(
        name="dd", kind="defectdojo", url="https://dd.example/", token="dd", project_key="7"
    )
    results = dispatch_run_notification(
        [config], _notification(), client=_client(handler), sleep=lambda _s: None
    )

    assert results[0].ok
    assert seen["url"].endswith("/api/v2/engagements/")
    assert seen["auth"] == "Token dd"
    body = seen["body"]
    assert body["product"] == "7"
    assert body["status"] == "Completed"
    assert body["target_start"] == "2026-01-01"
    assert body["engagement_type"] == "CI/CD"


def test_defectdojo_failed_run_keeps_the_engagement_open():
    from vulnclaw.integrations.notify import build_run_payload

    config = IntegrationConfig(name="dd", kind="defectdojo", url="https://dd.example", project_key="7")
    payload = build_run_payload(config, _notification(status="failed", error="boom"))

    assert payload["status"] == "In Progress"
    assert "boom" in payload["description"]


def test_finding_jira_description_is_adf_too():
    from vulnclaw.integrations.dispatch import adf_document

    doc = adf_document(["line one", "  ", "line two"])

    assert doc["type"] == "doc"
    assert len(doc["content"]) == 2
    assert doc["content"][1]["content"][0]["text"] == "line two"
    assert adf_document([])["content"][0]["content"][0]["text"] == "(no detail)"
