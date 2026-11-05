"""Schedule persistence and manual due-job execution."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from vulnclaw.config.settings import SCHEDULES_FILE
from vulnclaw.run_context import atomic_write_json
from vulnclaw.scheduler import ScheduledJob, Scheduler
from vulnclaw.web.schemas import ScheduleUpsertRequest, ScheduleView


def _load() -> list[dict]:
    path = Path(SCHEDULES_FILE)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _view(job: ScheduledJob) -> ScheduleView:
    return ScheduleView(
        name=job.name,
        target=job.target,
        command=job.command,
        interval_seconds=job.interval_seconds,
        enabled=job.enabled,
        options=job.options,
        last_run=job.last_run,
        next_run=job.next_run,
    )


def list_schedules() -> list[ScheduleView]:
    return [_view(job) for job in Scheduler.from_dicts(_load()).jobs]


def save_schedule(request: ScheduleUpsertRequest) -> ScheduleView:
    scheduler = Scheduler.from_dicts(_load())
    scheduler.jobs = [job for job in scheduler.jobs if job.name != request.name]
    scheduler.jobs.append(
        ScheduledJob(
            name=request.name,
            target=request.target,
            command=request.command,
            interval_seconds=request.interval_seconds,
            enabled=request.enabled,
            options=request.options,
            next_run=time.time() + request.interval_seconds,
        )
    )
    atomic_write_json(Path(SCHEDULES_FILE), scheduler.to_dicts())
    return _view(scheduler.jobs[-1])


def delete_schedule(name: str) -> bool:
    scheduler = Scheduler.from_dicts(_load())
    before = len(scheduler.jobs)
    scheduler.jobs = [job for job in scheduler.jobs if job.name != name]
    if len(scheduler.jobs) == before:
        return False
    atomic_write_json(Path(SCHEDULES_FILE), scheduler.to_dicts())
    return True


def run_due(runner: Callable[[ScheduledJob], object]) -> list[ScheduleView]:
    scheduler = Scheduler.from_dicts(_load())
    ran = scheduler.run_due(runner)
    if ran:
        atomic_write_json(Path(SCHEDULES_FILE), scheduler.to_dicts())
    return [_view(job) for job in ran]
