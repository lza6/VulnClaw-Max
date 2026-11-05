"""Schedule persistence and due-job execution."""

from __future__ import annotations

from vulnclaw.web.schemas import ScheduleUpsertRequest


def _service(monkeypatch, tmp_path):
    import vulnclaw.web.services.schedule_service as service

    monkeypatch.setattr(service, "SCHEDULES_FILE", tmp_path / "schedules.json")
    return service


def test_save_list_delete(monkeypatch, tmp_path):
    service = _service(monkeypatch, tmp_path)
    service.save_schedule(
        ScheduleUpsertRequest(name="nightly", target="example.com", interval_seconds=3600)
    )
    assert service.list_schedules()[0].name == "nightly"
    assert service.delete_schedule("nightly") is True
    assert service.list_schedules() == []


def test_run_due_calls_runner(monkeypatch, tmp_path):
    import vulnclaw.web.services.schedule_service as service

    jobs = [
        {
            "name": "due",
            "target": "example.com",
            "command": "recon",
            "interval_seconds": 60,
            "enabled": True,
            "next_run": 0,
        }
    ]
    import json

    (tmp_path / "schedules.json").write_text(json.dumps(jobs), encoding="utf-8")
    monkeypatch.setattr(service, "SCHEDULES_FILE", tmp_path / "schedules.json")
    ran = []

    result = service.run_due(lambda job: ran.append(job.name))

    assert ran == ["due"]
    assert result[0].name == "due"
    assert result[0].last_run is not None
