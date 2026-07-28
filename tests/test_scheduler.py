from __future__ import annotations

import sys
from datetime import datetime, timezone

import pytest

from ellmos_scheduler.executors import command_executor
from ellmos_scheduler.schedules import next_after
from ellmos_scheduler.service import SchedulerService
from ellmos_scheduler.store import SchedulerStore


UTC = timezone.utc


def test_interval_schedule():
    after = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    assert next_after({"kind": "interval", "seconds": 90}, after) == datetime(
        2026, 7, 27, 10, 1, 30, tzinfo=UTC
    )


def test_daily_schedule_in_timezone():
    after = datetime(2026, 7, 27, 6, 30, tzinfo=UTC)
    result = next_after(
        {"kind": "daily", "time": "09:00", "timezone": "Europe/Berlin"}, after
    )
    assert result == datetime(2026, 7, 27, 7, 0, tzinfo=UTC)


def test_cron_schedule():
    after = datetime(2026, 7, 27, 10, 7, tzinfo=UTC)
    result = next_after(
        {"kind": "cron", "expression": "*/15 * * * *", "timezone": "UTC"}, after
    )
    assert result == datetime(2026, 7, 27, 10, 15, tzinfo=UTC)


def test_cron_accepts_seven_as_sunday():
    after = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    result = next_after(
        {"kind": "cron", "expression": "0 9 * * 7", "timezone": "UTC"}, after
    )
    assert result == datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


def test_cron_step_with_explicit_start():
    after = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    result = next_after(
        {"kind": "cron", "expression": "1/15 * * * *", "timezone": "UTC"}, after
    )
    assert result == datetime(2026, 7, 27, 10, 1, tzinfo=UTC)


def test_cron_nonexistent_dst_time_runs_at_gap_end_like_bach():
    result = next_after(
        {
            "kind": "cron",
            "expression": "30 2 * * *",
            "timezone": "Europe/Berlin",
        },
        datetime(2026, 3, 29, 0, 59, tzinfo=UTC),
    )
    assert result == datetime(2026, 3, 29, 1, 0, tzinfo=UTC)


def test_cron_finds_leap_day_beyond_two_years():
    result = next_after(
        {
            "kind": "cron",
            "expression": "0 0 29 2 *",
            "timezone": "UTC",
        },
        datetime(2029, 3, 1, 0, 0, tzinfo=UTC),
    )
    assert result == datetime(2032, 2, 29, 0, 0, tzinfo=UTC)


def test_cron_fold_never_returns_past_instant():
    result = next_after(
        {
            "kind": "cron",
            "expression": "30 2 * * *",
            "timezone": "Europe/Berlin",
        },
        datetime(2026, 10, 25, 1, 15, tzinfo=UTC),
    )
    assert result == datetime(2026, 10, 25, 1, 30, tzinfo=UTC)


def test_cron_fold_does_not_duplicate_fixed_time_after_fold_zero_passed():
    result = next_after(
        {
            "kind": "cron",
            "expression": "30 2 * * *",
            "timezone": "Europe/Berlin",
        },
        datetime(2026, 10, 25, 0, 45, tzinfo=UTC),
    )
    assert result == datetime(2026, 10, 26, 1, 30, tzinfo=UTC)


def test_cron_stepped_day_field_uses_croniter_or_semantics():
    result = next_after(
        {
            "kind": "cron",
            "expression": "0 9 */2 * 1",
            "timezone": "UTC",
        },
        datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
    )
    assert result == datetime(2026, 7, 29, 9, 0, tzinfo=UTC)


def test_cron_list_with_exact_star_part_remains_unrestricted():
    result = next_after(
        {
            "kind": "cron",
            "expression": "0 9 *,1 * 1",
            "timezone": "UTC",
        },
        datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
    )
    assert result == datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


def test_invalid_interval():
    with pytest.raises(ValueError):
        next_after({"kind": "interval", "seconds": 0}, datetime.now(UTC))


def test_add_and_list_job(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    now = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    store.add_job("a", {"kind": "interval", "seconds": 60}, "noop", {}, now=now)
    jobs = store.list_jobs()
    assert [job["id"] for job in jobs] == ["a"]
    assert jobs[0]["next_due_at"] == "2026-07-27T10:01:00Z"


def test_due_job_runs_once_per_window(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    store.add_job(
        "a",
        {"kind": "interval", "seconds": 60},
        "noop",
        {"message": "ok"},
        now=base,
    )
    service = SchedulerService(store, "worker")
    first = service.tick(now=datetime(2026, 7, 27, 10, 1, tzinfo=UTC))
    second = service.tick(now=datetime(2026, 7, 27, 10, 1, tzinfo=UTC))
    assert first[0]["status"] == "succeeded"
    assert second == []
    runs = store.recent_runs()
    assert len(runs) == 1
    assert runs[0]["output"] == "ok"


def test_global_pause_blocks_claim(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    store.add_job("a", {"kind": "interval", "seconds": 60}, "noop", {}, now=base)
    store.set_pause("global", True, "maintenance", now=base)
    assert store.claim_due("worker", now=datetime(2026, 7, 27, 10, 2, tzinfo=UTC)) == []
    assert store.status()["control"]["paused"] is True


def test_job_pause_does_not_block_other_job(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    for job_id in ("a", "b"):
        store.add_job(job_id, {"kind": "interval", "seconds": 60}, "noop", {}, now=base)
    store.set_pause("job:a", True, now=base)
    claims = store.claim_due("worker", now=datetime(2026, 7, 27, 10, 1, tzinfo=UTC))
    assert [claim["id"] for claim in claims] == ["b"]


def test_disabled_job_not_claimed(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    store.add_job("a", {"kind": "interval", "seconds": 60}, "noop", {}, now=base)
    store.set_enabled("a", False, now=base)
    assert store.claim_due("worker", now=datetime(2026, 7, 27, 10, 2, tzinfo=UTC)) == []


def test_command_executor_uses_argv():
    result = command_executor(
        {"argv": [sys.executable, "-c", "print('hello')"]}, timeout_seconds=10
    )
    assert result.status == "succeeded"
    assert result.output.strip() == "hello"


def test_command_executor_rejects_string():
    result = command_executor({"argv": "echo unsafe"}, timeout_seconds=10)
    assert result.status == "failed"


def test_status_tracks_tick(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    now = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    SchedulerService(store).tick(now=now)
    assert store.status()["last_tick_at"] == "2026-07-27T10:00:00Z"


def test_noop_failure_is_recorded(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    store.add_job(
        "a", {"kind": "interval", "seconds": 60}, "noop", {"fail": True}, now=base
    )
    result = SchedulerService(store).tick(now=datetime(2026, 7, 27, 10, 1, tzinfo=UTC))
    assert result[0]["status"] == "failed"
    assert store.status()["runs"]["failed"] == 1


def test_expired_claim_is_recovered_with_new_attempt(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    store.add_job(
        "a",
        {"kind": "interval", "seconds": 60},
        "noop",
        {},
        now=base,
        lease_seconds=30,
    )
    first = store.claim_due("dead-worker", now=datetime(2026, 7, 27, 10, 1, tzinfo=UTC))
    recovered = store.claim_due(
        "recovery-worker", now=datetime(2026, 7, 27, 10, 2, tzinfo=UTC)
    )
    assert first[0]["attempt"] == 1
    assert recovered[0]["attempt"] == 2
    assert recovered[0]["scheduled_for"] == first[0]["scheduled_for"]
    assert recovered[0]["run_id"] != first[0]["run_id"]
    assert store.recent_runs()[1]["status"] == "abandoned"
