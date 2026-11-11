"""Interval scheduler with a controlled clock."""

from __future__ import annotations

from vulnclaw.scheduler import ScheduledJob, Scheduler


def test_due_jobs_run_and_advance():
    now = 1000.0
    job = ScheduledJob(name="j", target="example.com", interval_seconds=60)
    scheduler = Scheduler([job], clock=lambda: now)
    job.next_run = 1000.0
    ran = []

    assert scheduler.run_due(lambda item: ran.append(item.name), now=1000.0) == [job]
    assert ran == ["j"]
    assert job.last_run == 1000.0
    assert job.next_run == 1060.0
    assert scheduler.due(now=1010.0) == []


def test_disabled_jobs_do_not_run():
    job = ScheduledJob(name="j", target="t", enabled=False, next_run=0)
    scheduler = Scheduler([job], clock=lambda: 100)
    assert scheduler.due() == []


def test_round_trip_dicts():
    scheduler = Scheduler([ScheduledJob(name="j", target="t", interval_seconds=30)], clock=lambda: 0)
    restored = Scheduler.from_dicts(scheduler.to_dicts(), clock=lambda: 0)
    assert restored.jobs[0].name == "j"
    assert restored.jobs[0].interval_seconds == 30


def test_cron_expression_next_run():
    from datetime import datetime

    from vulnclaw.cron import next_cron_time

    after = datetime(2026, 11, 11, 10, 30)
    assert next_cron_time("0 2 * * *", after) == datetime(2026, 11, 12, 2, 0)
    assert next_cron_time("*/15 * * * *", after) == datetime(2026, 11, 11, 10, 45)
    assert next_cron_time("0 0 1 * *", after) == datetime(2026, 12, 1, 0, 0)


def test_cron_expression_rejects_invalid_values():
    import pytest

    from vulnclaw.cron import parse_cron

    with pytest.raises(ValueError):
        parse_cron("* * *")
    with pytest.raises(ValueError):
        parse_cron("60 * * * *")
    with pytest.raises(ValueError):
        parse_cron("*/0 * * * *")


def test_scheduler_cron_advances_to_next_match():
    from datetime import datetime

    from vulnclaw.scheduler import ScheduledJob, Scheduler

    now = datetime(2026, 11, 11, 10, 30).timestamp()
    job = ScheduledJob(name="nightly", target="example.com", cron="0 2 * * *", next_run=now)
    scheduler = Scheduler([job], clock=lambda: now)

    ran = scheduler.run_due(lambda item: None, now=now)

    assert [item.name for item in ran] == ["nightly"]
    assert datetime.fromtimestamp(job.next_run) == datetime(2026, 11, 12, 2, 0)


def test_scheduler_records_job_failure():
    from vulnclaw.scheduler import ScheduledJob, Scheduler

    job = ScheduledJob(name="bad", target="", interval_seconds=60, next_run=0)
    scheduler = Scheduler([job], clock=lambda: 100)

    def boom(_job):
        raise RuntimeError("cannot start")

    scheduler.run_due(boom, now=100)

    assert "cannot start" in job.last_error
    assert job.last_error_at
    assert scheduler.to_dicts()[0]["last_error"] == "cannot start"
