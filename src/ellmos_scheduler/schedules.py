from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo


UTC = timezone.utc


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _is_valid_local(value: datetime, zone: ZoneInfo) -> bool:
    """Whether a zoned wall time survives a UTC round-trip unchanged."""
    round_trip = value.astimezone(UTC).astimezone(zone)
    return (
        round_trip.replace(tzinfo=None) == value.replace(tzinfo=None)
        and round_trip.fold == value.fold
    )


def _first_valid_local(value: datetime, zone: ZoneInfo) -> datetime:
    """Advance a nonexistent DST wall time to the first minute after the gap."""
    candidate = value
    for _ in range(180):
        if _is_valid_local(candidate, zone):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("timezone gap exceeds three hours")


def _cron_instants(
    current: date,
    hour: int,
    minute: int,
    zone: ZoneInfo,
) -> tuple[datetime, ...]:
    wall_time = datetime.combine(
        current,
        time(hour=hour, minute=minute),
        tzinfo=zone,
    )
    valid = {
        candidate.astimezone(UTC)
        for candidate in (wall_time.replace(fold=0), wall_time.replace(fold=1))
        if _is_valid_local(candidate, zone)
    }
    if valid:
        return tuple(sorted(valid))
    # BACH stores a naive nonexistent wall time and runs it when the local clock
    # reaches the first real minute after the spring gap.
    return (_first_valid_local(wall_time, zone).astimezone(UTC),)


@lru_cache(maxsize=128)
def _field_values(expression: str, minimum: int, maximum: int) -> frozenset[int]:
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
            start = int(base)
            end = maximum if "/" in part else start
        if start < minimum or end > maximum or start > end:
            raise ValueError(f"cron field outside {minimum}..{maximum}: {part}")
        return set(range(start, end + 1, step))

    allowed: set[int] = set()
    for part in expression.split(","):
        allowed.update(expand(part.strip()))
    return frozenset(allowed)


def _field_matches(value: int, expression: str, minimum: int, maximum: int) -> bool:
    return value in _field_values(expression, minimum, maximum)


def _parse_cron(
    expression: str,
) -> tuple[
    str,
    str,
    str,
    str,
    str,
    frozenset[int],
    frozenset[int],
    frozenset[int],
]:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron expression must contain five fields")
    minute, hour, day, month, weekday = fields
    return (
        minute,
        hour,
        day,
        month,
        weekday,
        _field_values(minute, 0, 59),
        _field_values(hour, 0, 23),
        _field_values(month, 1, 12),
    )


def _cron_date_matches(
    current: date,
    day_expression: str,
    weekday_expression: str,
) -> bool:
    cron_weekday = (current.weekday() + 1) % 7
    day_matches = current.day in _field_values(day_expression, 1, 31)
    weekday_values = _field_values(weekday_expression, 0, 7)
    weekday_matches = cron_weekday in weekday_values
    if cron_weekday == 0:
        weekday_matches = weekday_matches or 7 in weekday_values
    day_unrestricted = any(part.strip() == "*" for part in day_expression.split(","))
    weekday_unrestricted = any(
        part.strip() == "*" for part in weekday_expression.split(",")
    )
    if day_unrestricted or weekday_unrestricted:
        return day_matches and weekday_matches
    return day_matches or weekday_matches


def _cron_matches(local: datetime, expression: str) -> bool:
    minute, hour, day, month, weekday, minutes, hours, months = _parse_cron(expression)
    del minute, hour
    return (
        local.minute in minutes
        and local.hour in hours
        and local.month in months
        and _cron_date_matches(local.date(), day, weekday)
    )


def _next_cron(expression: str, local_after: datetime, zone: ZoneInfo) -> datetime:
    _, _, day, _, weekday, minutes, hours, months = _parse_cron(expression)
    start_date = local_after.date()
    after_wall = local_after.replace(tzinfo=None)
    after_utc = local_after.astimezone(UTC)
    # Every valid Gregorian calendar pattern repeats within 400 years.
    for day_offset in range(146_098):
        try:
            current = start_date + timedelta(days=day_offset)
        except OverflowError:
            break
        if current.month not in months or not _cron_date_matches(current, day, weekday):
            continue
        for hour in sorted(hours):
            for minute in sorted(minutes):
                candidate_wall = datetime.combine(
                    current, time(hour=hour, minute=minute)
                )
                # BACH feeds croniter a naive local datetime. This wall-clock
                # comparison prevents a second fixed-time run after its first
                # fold occurrence has already passed.
                if candidate_wall <= after_wall:
                    continue
                future = [
                    candidate
                    for candidate in _cron_instants(current, hour, minute, zone)
                    if candidate > after_utc
                ]
                if future:
                    return min(future)
    raise ValueError("no cron occurrence found within a Gregorian 400-year cycle")


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
        candidate = local_after.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate <= local_after:
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC)

    if kind == "cron":
        return _next_cron(str(spec["expression"]), local_after, zone)

    raise ValueError(f"unsupported schedule kind: {kind!r}")
