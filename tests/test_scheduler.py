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
