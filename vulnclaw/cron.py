"""Five-field cron expressions for the in-process scheduler.

The Web scheduler accepts both fixed intervals and standard cron expressions.
This parser is intentionally small: numeric fields, ``*``, ranges, lists and
``/step`` suffixes. Names (MON, JAN) are not supported; the UI asks for numeric
expressions and rejects anything this module cannot parse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

_FIELD_RANGES = (
    (0, 59),  # minute
    (0, 23),  # hour
    (1, 31),  # day of month
    (1, 12),  # month
    (0, 7),  # day of week (0 and 7 are Sunday)
)


@dataclass(frozen=True)
class CronExpression:
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]

    def matches(self, moment: datetime) -> bool:
        if moment.minute not in self.minutes:
            return False
        if moment.hour not in self.hours:
            return False
        if moment.month not in self.months:
            return False
        day_matches = moment.day in self.days
        weekday = (moment.weekday() + 1) % 7  # Monday=0 -> Sunday=0
        weekday_matches = weekday in self.weekdays or (weekday == 0 and 7 in self.weekdays)
        # Vixie cron: when both day fields are restricted, either may match.
        day_restricted = self.days != frozenset(range(1, 32))
        weekday_restricted = self.weekdays != frozenset(range(0, 7))
        if day_restricted and weekday_restricted:
            return day_matches or weekday_matches
        return day_matches and weekday_matches


def _parse_field(value: str, lower: int, upper: int, *, name: str) -> frozenset[int]:
    value = value.strip()
    if not value:
        raise ValueError(f"cron {name} field is empty")
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"cron {name} field has an empty list item")
        step = 1
        if "/" in part:
            raw_range, raw_step = part.split("/", 1)
            try:
                step = int(raw_step)
            except ValueError as exc:
                raise ValueError(f"cron {name} step is not an integer: {raw_step}") from exc
            if step <= 0:
                raise ValueError(f"cron {name} step must be positive")
        else:
            raw_range = part
        if raw_range == "*":
            start, end = lower, upper
        elif "-" in raw_range:
            raw_start, raw_end = raw_range.split("-", 1)
            try:
                start, end = int(raw_start), int(raw_end)
            except ValueError as exc:
                raise ValueError(f"cron {name} range is not numeric: {raw_range}") from exc
        else:
            try:
                start = end = int(raw_range)
            except ValueError as exc:
                raise ValueError(f"cron {name} value is not numeric: {raw_range}") from exc
        if start < lower or end > upper or start > end:
            raise ValueError(f"cron {name} value out of range: {raw_range}")
        result.update(range(start, end + 1, step))
    return frozenset(result)


def parse_cron(expression: str) -> CronExpression:
    """Parse a standard five-field cron expression."""
    fields = str(expression or "").split()
    if len(fields) != 5:
        raise ValueError("cron expression must have five fields: minute hour day month weekday")
    parsed = [
        _parse_field(field, lower, upper, name=name)
        for field, (lower, upper), name in zip(
            fields,
            _FIELD_RANGES,
            ("minute", "hour", "day", "month", "weekday"),
            strict=True,
        )
    ]
    # Normalise Sunday 7 to 0 so ``matches`` only needs one representation.
    weekdays = frozenset(0 if item == 7 else item for item in parsed[4])
    return CronExpression(parsed[0], parsed[1], parsed[2], parsed[3], weekdays)


def validate_cron(expression: str) -> None:
    """Raise ValueError when the expression is invalid."""
    parse_cron(expression)


def next_cron_time(expression: str, after: datetime) -> datetime:
    """Return the first matching minute strictly after ``after``."""
    parsed = parse_cron(expression)
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # A leap-year-safe scan bound; cron expressions that fire less often than
    # this are rejected rather than hanging the scheduler.
    limit = candidate + timedelta(days=366 * 4)
    while candidate <= limit:
        if parsed.matches(candidate):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError(f"cron expression never fires within four years: {expression}")
