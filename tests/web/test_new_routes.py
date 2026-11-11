"""HTTP contract tests for the new Web API routes."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    import vulnclaw.target_state.store as store
    import vulnclaw.web.app as web_app
    import vulnclaw.web.services.constraint_audit_service as audit_service
    import vulnclaw.web.services.integration_service as integration_service
    import vulnclaw.web.services.project_service as project_service
    import vulnclaw.web.services.run_service as run_service
    import vulnclaw.web.services.schedule_service as schedule_service
    from vulnclaw.mcp.schemas import MCPDiagnosticsView

    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(audit_service, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(run_service, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(project_service, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(integration_service, "INTEGRATIONS_FILE", tmp_path / "integrations.json")
    monkeypatch.setattr(schedule_service, "SCHEDULES_FILE", tmp_path / "schedules.json")
    async def fake_toggle(name, enabled, allowed_tools=None):
        if name != "fetch":
            return None
        return {
            "name": name,
            "enabled": enabled,
            "allowed_tools": list(allowed_tools or []),
            "applies_to": "control_plane_and_next_task",
            "running": False,
            "tool_count": 0,
        }

    monkeypatch.setattr(web_app, "get_live_mcp_diagnostics", lambda: MCPDiagnosticsView())
    monkeypatch.setattr(web_app, "toggle_mcp_server", fake_toggle)

    return TestClient(web_app.create_app(), base_url="http://localhost", client=("127.0.0.1", 5555))


def _seed_run(root, name="run-a"):
    run_dir = root / name
    (run_dir / "events").mkdir(parents=True)
    (run_dir / "findings").mkdir()
    (run_dir / "reports").mkdir()
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_name": name,
                "command": "run",
                "status": "failed",
                "created_at": "2026-11-05T00:00:00",
                "targets": [{"canonical": "https://example.com/"}],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "events" / "events.jsonl").write_text(
        json.dumps({"timestamp": "t", "kind": "run_created", "payload": {}}) + "\n",
        encoding="utf-8",
    )


def _seed_finding():
    from vulnclaw.agent.context import SessionState
    from vulnclaw.config.domain_models import VulnerabilityFinding
    from vulnclaw.target_state.store import save_target_state

    session = SessionState(target="https://example.com")
    finding = VulnerabilityFinding(
        title="SQL Injection",
        severity="High",
        vuln_type="SQLi",
        description="confirmed",
    )
    finding.mark_verified(note="ok")
    session.add_finding(finding)
    save_target_state("https://example.com", session, command="scan")


def test_health_and_missing_asset(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["version"]
    assert "tasks" in body and "ui" in body

    missing = client.get("/assets/missing.js")
    assert missing.status_code == 404


def test_run_routes(client, tmp_path):
    _seed_run(tmp_path / "runs")

    runs = client.get("/api/runs")
    assert runs.status_code == 200
    assert runs.json()[0]["run_name"] == "run-a"

    detail = client.get("/api/runs/run-a")
    assert detail.status_code == 200
    assert detail.json()["events"][0]["kind"] == "run_created"

    assert client.get("/api/runs/missing").status_code == 404


def test_project_routes(client):
    created = client.post(
        "/api/projects",
        json={"name": "Acme Web", "customer": "Acme", "targets": ["https://example.com"]},
    )
    assert created.status_code == 200
    assert created.json()["slug"] == "acme-web"

    assert client.get("/api/projects").json()[0]["name"] == "Acme Web"
    assert client.post("/api/projects", json={"name": "Acme Web"}).status_code == 409

    added = client.post("/api/projects/acme-web/targets", json={"target": "https://two.example"})
    assert added.status_code == 200
    assert "https://two.example" in added.json()["targets"]


def test_finding_routes(client):
    _seed_finding()

    findings = client.get("/api/findings", params={"target": "https://example.com"})
    assert findings.status_code == 200
    item = findings.json()[0]
    assert item["triage_status"] == "new"

    updated = client.post(
        "/api/findings/triage",
        json={
            "target": "https://example.com",
            "finding_key": item["finding_key"],
            "triage_status": "confirmed",
            "note": "reproduced",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["triage_status"] == "confirmed"

    missing = client.post(
        "/api/findings/triage",
        json={
            "target": "https://missing.example",
            "finding_key": "x",
            "triage_status": "confirmed",
        },
    )
    assert missing.status_code == 404


def test_audit_export_routes(client):
    _seed_finding()

    csv_response = client.get("/api/audit/export", params={"format": "csv"})
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")

    jsonl_response = client.get("/api/audit/export", params={"format": "jsonl"})
    assert jsonl_response.status_code == 200

    assert client.get("/api/audit/export", params={"format": "bogus"}).status_code == 400


def test_mcp_toggle_routes(client):
    enabled = client.post("/api/mcp/toggle", json={"name": "fetch", "enabled": False})
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is False

    unknown = client.post("/api/mcp/toggle", json={"name": "missing", "enabled": True})
    assert unknown.status_code == 404


def test_integration_routes(client):
    created = client.post(
        "/api/integrations",
        json={
            "name": "hook",
            "kind": "webhook",
            "url": "https://hooks.example/vc",
            "token": "secret",
        },
    )
    assert created.status_code == 200
    assert created.json()["token_configured"] is True
    assert "secret" not in created.text

    assert client.get("/api/integrations").json()[0]["name"] == "hook"
    assert client.delete("/api/integrations/hook").status_code == 200
    assert client.delete("/api/integrations/hook").status_code == 404


def test_schedule_routes(client):
    created = client.post(
        "/api/schedules",
        json={"name": "nightly", "target": "example.com", "interval_seconds": 3600},
    )
    assert created.status_code == 200
    assert created.json()["name"] == "nightly"

    assert client.get("/api/schedules").json()[0]["target"] == "example.com"
    assert client.delete("/api/schedules/nightly").status_code == 200
    assert client.delete("/api/schedules/nightly").status_code == 404



def test_tasks_list_filters_by_project(client):
    """`/api/tasks?project=` filters by project_id; `?project=` matches unassigned."""

    import vulnclaw.web.app as web_app
    from vulnclaw.web.schemas import TaskCreateRequest, TaskOptions

    manager = web_app.task_manager
    assigned = manager.create_task(
        TaskCreateRequest(command="recon", target="https://proj-a.example", options=TaskOptions(project="alpha"))
    )
    unassigned = manager.create_task(
        TaskCreateRequest(command="recon", target="https://plain.example")
    )

    all_ids = {item["task_id"] for item in client.get("/api/tasks").json()}
    assert assigned.task_id in all_ids and unassigned.task_id in all_ids

    alpha_ids = {item["task_id"] for item in client.get("/api/tasks?project=alpha").json()}
    # The manager is a module-level singleton shared across tests; assert
    # inclusion rather than exact-set equality.
    assert assigned.task_id in alpha_ids
    assert unassigned.task_id not in alpha_ids

    none_ids = {item["task_id"] for item in client.get("/api/tasks?project=").json()}
    assert unassigned.task_id in none_ids
    assert assigned.task_id not in none_ids
    for record in client.get("/api/tasks?project=alpha").json():
        assert record["project_id"] == "alpha"
