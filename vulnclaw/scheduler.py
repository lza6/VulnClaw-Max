"""Minimal in-process scheduler with interval and cron expressions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from vulnclaw.cron import next_cron_time, parse_cron


@dataclass
class ScheduledJob:
    name: str
    target: str
    command: str = "recon"
    interval_seconds: float = 3600.0
    cron: str | None = None
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)
    last_run: float | None = None
    next_run: float | None = None
    last_error: str = ""
    last_error_at: str | None = None

    def next_after(self, current: float) -> float:
        """Return the next scheduled epoch for this job after ``current``."""
        if self.cron:
            return next_cron_time(self.cron, datetime.fromtimestamp(current)).timestamp()
        return current + max(1.0, self.interval_seconds)


class Scheduler:
    def __init__(
        self,
        jobs: list[ScheduledJob] | None = None,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.jobs = jobs or []
        self._clock = clock
        now = self._clock()
        for job in self.jobs:
            if job.next_run is None:
                job.next_run = job.next_after(now)

    def due(self, now: float | None = None) -> list[ScheduledJob]:
        current = self._clock() if now is None else now
        return [
            job
            for job in self.jobs
            if job.enabled and job.next_run is not None and job.next_run <= current
        ]

    def run_due(
        self, runner: Callable[[ScheduledJob], Any], now: float | None = None
    ) -> list[ScheduledJob]:
        current = self._clock() if now is None else now
        ran: list[ScheduledJob] = []
        for job in self.due(current):
            try:
                runner(job)
                job.last_error = ""
                job.last_error_at = None
            except Exception as exc:
                job.last_error = str(exc)
                job.last_error_at = datetime.now().isoformat()
            job.last_run = current
            job.next_run = job.next_after(current)
            ran.append(job)
        return ran

    def to_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "name": job.name,
                "target": job.target,
                "command": job.command,
                "interval_seconds": job.interval_seconds,
                "cron": job.cron,
                "enabled": job.enabled,
                "options": job.options,
                "last_run": job.last_run,
                "next_run": job.next_run,
                "last_error": job.last_error,
                "last_error_at": job.last_error_at,
            }
            for job in self.jobs
        ]

    @classmethod
    def from_dicts(
        cls, items: list[dict[str, Any]], *, clock: Callable[[], float] = time.time
    ) -> "Scheduler":
        jobs: list[ScheduledJob] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            cron = item.get("cron")
            cron_value = str(cron).strip() if cron else None
            if cron_value:
                parse_cron(cron_value)
            jobs.append(
                ScheduledJob(
                    name=str(item.get("name") or ""),
                    target=str(item.get("target") or ""),
                    command=str(item.get("command") or "recon"),
                    interval_seconds=float(item.get("interval_seconds") or 3600),
                    cron=cron_value,
                    enabled=bool(item.get("enabled", True)),
                    options=dict(item.get("options") or {}),
                    last_run=item.get("last_run"),
                    next_run=item.get("next_run"),
                    last_error=str(item.get("last_error") or ""),
                    last_error_at=item.get("last_error_at"),
                )
            )
        return cls(jobs, clock=clock)
