"""Run listing/detail reads persisted artifacts without trusting paths."""

from __future__ import annotations

import json


def _write_run(root, name, *, status="completed", events=2):
    run_dir = root / name
    (run_dir / "events").mkdir(parents=True)
    (run_dir / "findings").mkdir()
    (run_dir / "reports").mkdir()
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_name": name,
                "command": "recon",
                "status": status,
                "created_at": "2026-11-05T00:00:00",
                "started_at": "2026-11-05T00:00:00",
                "ended_at": "2026-11-05T00:01:00",
                "exit_code": 0 if status == "completed" else 1,
                "targets": [{"canonical": "https://example.com/"}],
                "artifacts": {"events": "events/events.jsonl"},
                "resume": {"last_snapshot_id": "snap"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "events" / "events.jsonl").write_text(
        "\n".join(
            json.dumps({"timestamp": f"t{i}", "kind": "checkpoint", "payload": {"i": i}})
            for i in range(events)
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "findings" / "findings.json").write_text(
        json.dumps({"findings": []}), encoding="utf-8"
    )
    (run_dir / "reports" / "report.md").write_text("report", encoding="utf-8")
    return run_dir


def test_list_and_get_run(monkeypatch, tmp_path):
    import vulnclaw.web.services.run_service as service

    monkeypatch.setattr(service, "RUNS_DIR", tmp_path)
    _write_run(tmp_path, "run-a")
    _write_run(tmp_path, "run-b", status="failed")

    runs = service.list_runs()
    assert {item.run_name for item in runs} == {"run-a", "run-b"}
    assert all(item.targets == ["https://example.com/"] for item in runs)

    detail = service.get_run("run-a")
    assert detail is not None
    assert detail.run_name == "run-a"
    assert [event.kind for event in detail.events] == ["checkpoint", "checkpoint"]
    assert detail.findings == {"findings": []}
    assert detail.reports == ["report.md"]


def test_get_run_rejects_traversal(monkeypatch, tmp_path):
    import vulnclaw.web.services.run_service as service

    monkeypatch.setattr(service, "RUNS_DIR", tmp_path / "runs")
    (tmp_path / "runs").mkdir()
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "run.json").write_text("{}", encoding="utf-8")

    assert service.get_run("../secret") is None
    assert service.get_run("..\\secret") is None
    assert service.get_run("") is None


def test_list_runs_skips_corrupt_manifest(monkeypatch, tmp_path):
    import vulnclaw.web.services.run_service as service

    monkeypatch.setattr(service, "RUNS_DIR", tmp_path)
    _write_run(tmp_path, "good")
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "run.json").write_text("{broken", encoding="utf-8")

    runs = service.list_runs()
    assert [item.run_name for item in runs] == ["good"]


def test_list_runs_rejects_non_positive_limit(monkeypatch, tmp_path):
    import pytest

    import vulnclaw.web.services.run_service as service

    monkeypatch.setattr(service, "RUNS_DIR", tmp_path)
    with pytest.raises(ValueError):
        service.list_runs(limit=0)
