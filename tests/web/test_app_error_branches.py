"""HTTP error-branch coverage for app.py routes not exercised elsewhere.

These tests drive the 404/409/400 paths of the task, target, project,
report and provider routes so `vulnclaw/web/app.py` clears the 90% gate.
"""

from __future__ import annotations

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
    import vulnclaw.web.task_manager as task_manager_mod

    monkeypatch.setattr(store, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(audit_service, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(run_service, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(project_service, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(integration_service, "INTEGRATIONS_FILE", tmp_path / "integrations.json")
    monkeypatch.setattr(schedule_service, "SCHEDULES_FILE", tmp_path / "schedules.json")

    # Isolate the module-level task manager singleton for this fixture's app.
    fresh = task_manager_mod.WebTaskManager()
    monkeypatch.setattr(web_app, "task_manager", fresh)

    return TestClient(web_app.create_app(), base_url="http://localhost", client=("127.0.0.1", 5555))


def test_task_404_branches(client):
    assert client.get("/api/tasks/nonexistent").status_code == 404
    assert client.post("/api/tasks/nonexistent/stop").status_code == 404


def test_stop_finished_task_returns_409(client):
    import vulnclaw.web.app as web_app
    from vulnclaw.web.schemas import TaskCreateRequest

    record = web_app.task_manager.create_task(
        TaskCreateRequest(command="codescan", target="https://example.com")
    )
    web_app.task_manager.set_completed(record.task_id)
    response = client.post(f"/api/tasks/{record.task_id}/stop")
    assert response.status_code == 409


def test_task_events_404_and_bad_cursor(client):
    import vulnclaw.web.app as web_app
    from vulnclaw.web.schemas import TaskCreateRequest

    # Unknown task id must 404 before any streaming starts.
    missing = client.get("/api/tasks/nonexistent/stream")
    assert missing.status_code == 404

    # A malformed Last-Event-ID cursor must not crash the route; the
    # response body starts streaming the SSE payload regardless.
    record = web_app.task_manager.create_task(
        TaskCreateRequest(command="codescan", target="https://example.com")
    )
    web_app.task_manager.set_completed(record.task_id)
    with client.stream(
        "GET",
        f"/api/tasks/{record.task_id}/stream",
        headers={"Last-Event-ID": "not-a-number"},
    ) as ok:
        assert ok.status_code == 200


def test_target_rollback_and_clear_404(client):
    assert client.post("/api/targets/https%3A%2F%2Fmissing.example/rollback", json={"snapshot_id": "s1"}).status_code == 404
    assert client.delete("/api/targets/https%3A%2F%2Fmissing.example").status_code == 404


def test_project_detail_404(client):
    assert client.get("/api/projects/does-not-exist").status_code == 404


def test_report_content_and_download_404(client):
    assert client.get("/api/reports/content", params={"path": "missing.md"}).status_code in {400, 403, 404}
    assert client.get("/api/reports/download", params={"path": "missing.md"}).status_code in {400, 403, 404}


def test_report_target_generation_rejects_bad_input(client):
    response = client.post(
        "/api/reports/target",
        json={"target": "https://missing.example", "report_format": "markdown"},
    )
    assert response.status_code in {400, 404}


def test_provider_models_offline_400(client, monkeypatch):

    monkeypatch.setenv("VULNCLAW_OFFLINE", "1")
    response = client.post("/api/provider-models", json={"provider": "openai", "base_url": "http://127.0.0.1:9", "api_key": "k"})
    assert response.status_code == 400
    assert "Offline" in response.json()["detail"]
    monkeypatch.delenv("VULNCLAW_OFFLINE")


def test_finding_triage_404(client):
    response = client.post(
        "/api/findings/triage",
        json={"target": "https://missing.example", "finding_key": "nope", "triage_status": "confirmed"},
    )
    assert response.status_code in {400, 404}


def test_integration_delete_404(client):
    assert client.delete("/api/integrations/none").status_code == 404


def test_integration_retry_404(client):
    assert client.post("/api/integrations/none/retry").status_code == 404


def test_schedules_run_due_with_runner(client, monkeypatch):
    """run-due route executes its injected runner without crashing on an empty schedule."""
    response = client.post("/api/schedules/run-due")
    assert response.status_code == 200
