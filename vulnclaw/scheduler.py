"""Minimal in-process interval scheduler with an injectable clock."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ScheduledJob:
    name: str
    target: str
    command: str = "recon"
    interval_seconds: float = 3600.0
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)
    last_run: float | None = None
    next_run: float | None = None


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
                job.next_run = now + max(1.0, job.interval_seconds)

    def due(self, now: float | None = None) -> list[ScheduledJob]:
        current = self._clock() if now is None else now
        return [
            job
            for job in self.jobs
            if job.enabled and job.next_run is not None and job.next_run <= current
        ]

    def run_due(self, runner: Callable[[ScheduledJob], Any], now: float | None = None) -> list[ScheduledJob]:
        current = self._clock() if now is None else now
        ran: list[ScheduledJob] = []
        for job in self.due(current):
            runner(job)
            job.last_run = current
            job.next_run = current + max(1.0, job.interval_seconds)
            ran.append(job)
        return ran

    def to_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "name": job.name,
                "target": job.target,
                "command": job.command,
                "interval_seconds": job.interval_seconds,
                "enabled": job.enabled,
                "options": job.options,
                "last_run": job.last_run,
                "next_run": job.next_run,
            }
            for job in self.jobs
        ]

    @classmethod
    def from_dicts(
        cls, items: list[dict[str, Any]], *, clock: Callable[[], float] = time.time
    ) -> "Scheduler":
        return cls(
            [
                ScheduledJob(
                    name=str(item.get("name") or ""),
                    target=str(item.get("target") or ""),
                    command=str(item.get("command") or "recon"),
                    interval_seconds=float(item.get("interval_seconds") or 3600),
                    enabled=bool(item.get("enabled", True)),
                    options=dict(item.get("options") or {}),
                    last_run=item.get("last_run"),
                    next_run=item.get("next_run"),
                )
                for item in items
                if isinstance(item, dict)
            ],
            clock=clock,
        )
