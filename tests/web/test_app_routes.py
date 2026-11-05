"""Broad route coverage for the Web app wiring."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def _dump(_self=None, **_kwargs):
    return {"ok": True}


@pytest.fixture
def client(monkeypatch, tmp_path):
    import vulnclaw.web.app as app

    def dumpable():
        return SimpleNamespace(model_dump=_dump)

    monkeypatch.setattr(app, "get_public_config", dumpable)
    monkeypatch.setattr(app, "update_public_config", lambda _request: dumpable())
    monkeypatch.setattr(app, "get_mcp_diagnostics", dumpable)
    monkeypatch.setattr(app, "get_constraint_audit", dumpable)
    monkeypatch.setattr(app, "get_provider_presets", dumpable)
    monkeypatch.setattr(app, "fetch_models", lambda _request: dumpable())
    monkeypatch.setattr(app, "list_targets", lambda: [])
    monkeypatch.setattr(app, "get_target", lambda _target: None)
    monkeypatch.setattr(app, "get_target_raw", lambda _target: None)
    monkeypatch.setattr(app, "get_preview", lambda _target, snapshot_id=None: None)
    monkeypatch.setattr(app, "get_snapshots", lambda _target: [])
    monkeypatch.setattr(app, "get_diff", lambda _target, from_snapshot_id, to_snapshot_id=None: None)
    monkeypatch.setattr(app, "rollback_target", lambda _target, _snapshot: False)
    monkeypatch.setattr(app, "clear_target", lambda _target: False)
    monkeypatch.setattr(app, "list_reports", lambda: [])
    monkeypatch.setattr(app, "read_report_content", lambda _path: dumpable())
    report = tmp_path / "report.md"
    report.write_text("report", encoding="utf-8")
    monkeypatch.setattr(app, "resolve_report_path", lambda _path: report)
    monkeypatch.setattr(app, "generate_target_report", lambda *_args, **_kwargs: str(report))
    monkeypatch.setattr(app, "start_task", lambda _manager, _request: "task_x")
    return TestClient(app.create_app(), base_url="http://localhost", client=("127.0.0.1", 5555))


def test_config_and_provider_routes(client):
    assert client.get("/api/config").status_code == 200
    assert client.post("/api/config", json={}).status_code == 200
    assert client.get("/api/mcp").status_code == 200
    assert client.get("/api/constraint-audit").status_code == 200
    assert client.get("/api/providers").status_code == 200
    assert client.post("/api/provider-models", json={}).status_code == 200


def test_task_routes(client):
    assert client.get("/api/tasks").status_code == 200
    created = client.post("/api/tasks/run", json={"command": "recon", "target": "example.com"})
    assert created.status_code == 200
    assert created.json()["task_id"] == "task_x"
    assert client.get("/api/tasks/missing").status_code == 404
    assert client.post("/api/tasks/missing/stop").status_code == 404
    assert client.get("/api/tasks/missing/stream").status_code == 404


def test_target_routes(client):
    assert client.get("/api/targets").status_code == 200
    for path in (
        "/api/targets/example.com",
        "/api/targets/example.com/raw",
        "/api/targets/example.com/snapshots",
        "/api/target-preview/example.com",
        "/api/target-diff/example.com?from_snapshot_id=x",
        "/api/targets/example.com/rollback",
        "/api/targets/example.com",
    ):
        method = client.delete if path == "/api/targets/example.com" and path.count("/") == 3 else client.get
        if "rollback" in path:
            assert client.post(path, json={"snapshot_id": "x"}).status_code in {400, 404}
        else:
            assert method(path).status_code in {200, 400, 404}


def test_report_routes(client):
    assert client.get("/api/reports").status_code == 200
    assert client.get("/api/reports/content", params={"path": "report.md"}).status_code == 200
    assert client.get("/api/reports/download", params={"path": "report.md"}).status_code == 200
    assert (
        client.post(
            "/api/reports/target",
            json={"target": "example.com", "report_format": "markdown"},
        ).status_code
        == 200
    )


def test_frontend_fallback_and_404(client):
    assert client.get("/").status_code == 200
    assert client.get("/some/deep/route").status_code == 200
    assert client.get("/api/nope").status_code == 404
    assert client.get("/assets/nope.js").status_code == 404
