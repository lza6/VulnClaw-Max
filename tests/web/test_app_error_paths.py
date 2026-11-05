"""Web API error paths: every route must answer with a real status, not a 500."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def _make_client(monkeypatch, tmp_path) -> TestClient:
    import vulnclaw.target_state.store as store
    import vulnclaw.web.app as web_app
    import vulnclaw.web.services.constraint_audit_service as audit_service
    import vulnclaw.web.services.integration_service as integration_service
    import vulnclaw.web.services.mcp_control_service as mcp_service
    import vulnclaw.web.services.project_service as project_service
    import vulnclaw.web.services.report_service as report_service
    import vulnclaw.web.services.run_service as run_service
    import vulnclaw.web.services.schedule_service as schedule_service

    targets = tmp_path / "targets"
    sessions = tmp_path / "sessions"
    targets.mkdir(parents=True, exist_ok=True)
    sessions.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(store, "TARGETS_DIR", targets)
    monkeypatch.setattr(audit_service, "TARGETS_DIR", targets)
    monkeypatch.setattr(run_service, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(project_service, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(report_service, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(report_service, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(integration_service, "INTEGRATIONS_FILE", tmp_path / "integrations.json")
    monkeypatch.setattr(schedule_service, "SCHEDULES_FILE", tmp_path / "schedules.json")
    monkeypatch.setattr(
        mcp_service,
        "load_config",
        lambda: SimpleNamespace(mcp=SimpleNamespace(servers={})),
    )
    monkeypatch.setattr(mcp_service, "set_config_value", lambda *_args: None)

    return TestClient(web_app.create_app(), base_url="http://localhost", client=("127.0.0.1", 5555))


@pytest.fixture
def client(monkeypatch, tmp_path):
    return _make_client(monkeypatch, tmp_path)


def test_unknown_task_routes_return_404(client):
    assert client.get("/api/tasks/does-not-exist").status_code == 404
    assert client.post("/api/tasks/does-not-exist/stop").status_code == 404
    assert client.get("/api/tasks/does-not-exist/stream").status_code == 404


def test_task_creation_rejects_an_unknown_project(client):
    response = client.post(
        "/api/tasks/run",
        json={"command": "run", "target": "example.com", "options": {"project": "ghost"}},
    )
    assert response.status_code == 400
    assert "Project not found" in response.json()["detail"]


def test_unknown_target_routes_return_404(client):
    assert client.get("/api/targets/ghost.example").status_code == 404
    assert client.get("/api/targets/ghost.example/raw").status_code == 404
    assert client.get("/api/target-preview/ghost.example").status_code == 404
    assert client.delete("/api/targets/ghost.example").status_code == 404
    assert client.get(
        "/api/target-diff/ghost.example?from_snapshot_id=snap-1"
    ).status_code == 404
    assert client.get("/api/targets/ghost.example/snapshots").status_code in {200, 404}


def test_rollback_requires_a_snapshot_id(client):
    response = client.post("/api/targets/example.com/rollback", json={})
    assert response.status_code == 400
    assert "snapshot_id" in response.json()["detail"]

    missing = client.post("/api/targets/example.com/rollback", json={"snapshot_id": "nope"})
    assert missing.status_code == 404


def test_unknown_schedule_delete_is_404_and_run_due_is_empty(client):
    assert client.delete("/api/schedules/ghost").status_code == 404
    assert client.post("/api/schedules/run-due").json() == []


def test_unknown_integration_routes_return_404(client):
    assert client.delete("/api/integrations/ghost").status_code == 404
    assert client.post("/api/integrations/ghost/test").status_code == 404
    assert client.post("/api/integrations/ghost/retry").status_code == 404
    assert client.get("/api/integrations/deliveries").json() == []


def test_integration_save_rejects_a_non_http_url(client):
    response = client.post(
        "/api/integrations",
        json={"name": "bad", "kind": "webhook", "url": "file:///etc/passwd"},
    )
    assert response.status_code == 400
    assert "http or https" in response.json()["detail"]


def test_integration_deliveries_track_dispatch_results(client, monkeypatch):
    import vulnclaw.web.services.integration_service as integration_service

    class _Result:
        def __init__(self, name, ok):
            self.name = name
            self.ok = ok
            self.attempts = 1
            self.status_code = 200 if ok else 500
            self.error = "" if ok else "HTTP 500"

    client.post(
        "/api/integrations",
        json={"name": "hook", "kind": "webhook", "url": "https://hooks.example/vc"},
    )
    monkeypatch.setattr(
        integration_service,
        "dispatch_findings",
        lambda config, **_kwargs: [_Result(config.name, True)],
    )

    dispatched = client.post(
        "/api/integrations/dispatch",
        json={"target": "example.com", "run_name": "r1", "findings": [{"title": "x"}]},
    )
    assert dispatched.status_code == 200
    assert dispatched.json()[0]["ok"] is True

    history = client.get("/api/integrations/deliveries").json()
    assert history[0]["name"] == "hook"
    assert history[0]["kind"] == "findings"
    assert history[0]["items"] == 1


def test_unknown_project_routes_return_404(client):
    assert client.get("/api/projects/ghost").status_code == 404
    response = client.post("/api/projects/ghost/targets", json={"target": "example.com"})
    assert response.status_code == 404


def test_unknown_run_detail_is_404(client):
    assert client.get("/api/runs/ghost-run").status_code == 404


def test_report_paths_outside_the_roots_are_forbidden(client, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("# nope", encoding="utf-8")

    assert client.get(f"/api/reports/content?path={outside}").status_code == 403
    assert client.get(f"/api/reports/download?path={outside}").status_code == 403
    assert client.get("/api/reports/content?path=/nope/missing.md").status_code in {403, 404}


def test_missing_report_file_is_404(client, monkeypatch):
    import vulnclaw.web.services.report_service as report_service

    missing = report_service.SESSIONS_DIR / "missing.md"
    assert client.get(f"/api/reports/content?path={missing}").status_code == 404


def test_report_target_for_unknown_target_is_404(client):
    response = client.post("/api/reports/target", json={"target": "ghost.example"})
    assert response.status_code == 404


def test_report_target_rejects_an_unknown_template(client):
    response = client.post(
        "/api/reports/target", json={"target": "example.com", "template": "freestyle"}
    )
    assert response.status_code == 422


def test_health_reports_version_and_task_counts(client):
    payload = client.get("/api/health").json()

    assert payload["status"] == "ok"
    assert payload["version"]
    assert "tasks" in payload


def test_startup_and_shutdown_lifespan_runs_cleanly(monkeypatch, tmp_path):
    import vulnclaw.web.app as web_app
    import vulnclaw.web.services.integration_service as integration_service
    import vulnclaw.web.services.schedule_service as schedule_service

    monkeypatch.setattr(integration_service, "INTEGRATIONS_FILE", tmp_path / "integrations.json")
    monkeypatch.setattr(schedule_service, "SCHEDULES_FILE", tmp_path / "schedules.json")

    with TestClient(web_app.create_app(), base_url="http://localhost", client=("127.0.0.1", 5555)) as scoped:
        assert scoped.get("/api/health").json()["status"] == "ok"


def test_target_subroutes_are_reachable_for_an_existing_target(monkeypatch, tmp_path):
    """Regression: a greedy ``{target:path}`` route must not shadow /raw and /snapshots."""
    import vulnclaw.target_state.store as store
    import vulnclaw.web.services.target_service as target_service
    from vulnclaw.agent.context import SessionState

    targets = tmp_path / "targets"
    monkeypatch.setattr(store, "TARGETS_DIR", targets)
    monkeypatch.setattr(target_service, "TARGETS_DIR", targets)
    store.save_target_state(
        "https://real.example", SessionState(target="https://real.example"), command="scan"
    )
    client = _make_client(monkeypatch, tmp_path)

    detail = client.get("/api/targets/https://real.example")
    raw = client.get("/api/targets/https://real.example/raw")
    snapshots = client.get("/api/targets/https://real.example/snapshots")

    assert detail.status_code == 200
    assert raw.status_code == 200
    assert snapshots.status_code == 200
    assert snapshots.json(), "a saved target must expose at least one snapshot"


def test_task_accepts_an_existing_project(client, tmp_path):
    """Regression: ``options.project`` used to be rejected for every command (422),
    so choosing a project in the web UI broke task creation."""
    created = client.post("/api/projects", json={"name": "Acme Audit", "customer": "Acme"})
    assert created.status_code == 200
    slug = created.json()["slug"]

    scan_target = tmp_path / "src"
    scan_target.mkdir()
    (scan_target / "app.py").write_text("print('hello')\n", encoding="utf-8")

    response = client.post(
        "/api/tasks/run",
        json={
            "command": "codescan",
            "target": str(scan_target),
            "resume": False,
            "options": {"project": slug},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["options"]["project"] == slug


def test_pdf_export_without_the_optional_extra_is_a_client_error(client, monkeypatch):
    import vulnclaw.web.services.report_service as report_service

    def no_pdf(*_args, **_kwargs):
        raise RuntimeError("PDF export requires reportlab. Install the extra with: pip install 'vulnclaw[pdf]'")

    def fake_generate(_raw, report_format, output_path, template="pentest"):
        Path(output_path).write_text("# markdown body", encoding="utf-8")
        return output_path

    monkeypatch.setattr(report_service, "generate_report_from_target_state", fake_generate)
    monkeypatch.setattr(report_service, "load_target_state", lambda _target: {"target": "example.com"})
    monkeypatch.setattr(
        "vulnclaw.report.pdf_exporter.export_pdf",
        no_pdf,
        raising=False,
    )

    response = client.post(
        "/api/reports/target", json={"target": "example.com", "report_format": "pdf"}
    )

    assert response.status_code == 400
    assert "vulnclaw[pdf]" in response.json()["detail"]
