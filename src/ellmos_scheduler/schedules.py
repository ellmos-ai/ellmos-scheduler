from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


UTC = timezone.utc


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _field_matches(value: int, expression: str, minimum: int, maximum: int) -> bool:
    def expand(part: str) -> set[int]:
        if "/" in part:
            base, raw_step = part.split("/", 1)
            step = int(raw_step)
            if step <= 0:
                raise ValueError("cron step must be positive")
        else:
            base, step = part, 1
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            raw_start, raw_end = base.split("-", 1)
            start, end = int(raw_start), int(raw_end)
        else:
            start = end = int(base)
        if start < minimum or end > maximum or start > end:
            raise ValueError(f"cron field outside {minimum}..{maximum}: {part}")
        return set(range(start, end + 1, step))

    allowed: set[int] = set()
    for part in expression.split(","):
        allowed.update(expand(part.strip()))
    return value in allowed


def _cron_matches(local: datetime, expression: str) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron expression must contain five fields")
    minute, hour, day, month, weekday = fields
    cron_weekday = (local.weekday() + 1) % 7
    return all(
        (
            _field_matches(local.minute, minute, 0, 59),
            _field_matches(local.hour, hour, 0, 23),
            _field_matches(local.day, day, 1, 31),
            _field_matches(local.month, month, 1, 12),
            _field_matches(cron_weekday, weekday, 0, 6),
        )
    )


def next_after(spec: dict[str, Any], after: datetime) -> datetime:
    """Return the first scheduled instant strictly after *after*, in UTC."""
    after = _utc(after)
    kind = spec.get("kind")
    if kind == "interval":
        seconds = int(spec["seconds"])
        if seconds <= 0:
            raise ValueError("interval seconds must be positive")
        return after + timedelta(seconds=seconds)

    zone = ZoneInfo(str(spec.get("timezone", "UTC")))
    local_after = after.astimezone(zone)
    if kind == "daily":
        hour, minute = (int(part) for part in str(spec["time"]).split(":", 1))
        if hour not in range(24) or minute not in range(60):
            raise ValueError("daily time must be HH:MM")
        candidate = local_after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= local_after:
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC)

    if kind == "cron":
        expression = str(spec["expression"])
        candidate = local_after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(60 * 24 * 366 * 2):
            if _cron_matches(candidate, expression):
                return candidate.astimezone(UTC)
            candidate += timedelta(minutes=1)
        raise ValueError("no cron occurrence found within two years")

    raise ValueError(f"unsupported schedule kind: {kind!r}")
