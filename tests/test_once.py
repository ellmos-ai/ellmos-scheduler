from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from ellmos_scheduler.schedules import next_after
from ellmos_scheduler.store import SchedulerStore
from ellmos_scheduler.service import SchedulerService

UTC = timezone.utc
AT = datetime(2026, 11, 4, 12, tzinfo=UTC)
SPEC = {"kind": "once", "at": "2026-11-04T12:00:00Z"}


@pytest.mark.parametrize("at", ["2026-11-04T12:00:00Z", "2026-11-04T14:00:00+02:00", "2026-11-04T07:00:00-05:00"])
def test_once_aware_and_strict_next(at):
    spec = {"kind": "once", "at": at}
    assert next_after(spec, AT - timedelta(microseconds=1)) == AT
    assert next_after(spec, AT) is None
    assert next_after(spec, AT + timedelta(days=1)) is None


@pytest.mark.parametrize("at", ["2026-11-04T12:00:00", "2026-11-04", "", None])
def test_once_rejects_naive_or_invalid_even_with_due_override(tmp_path, at):
    store = SchedulerStore(tmp_path / "state.db")
    store.init()
    with pytest.raises(ValueError):
        store.add_job("j", {"kind": "once", "at": at}, "noop", {}, next_due_at=AT)


def make_store(tmp_path, **kwargs):
    store = SchedulerStore(tmp_path / "state.db")
    store.init()
    store.add_job("j", SPEC, "noop", {}, now=AT + timedelta(days=1), lease_seconds=10, **kwargs)
    return store


def test_once_exact_due_pause_restart_enable_and_success(tmp_path):
    store = make_store(tmp_path)
    assert store.claim_due("a", now=AT - timedelta(microseconds=1)) == []
    store.set_pause("job:j", True)
    assert store.claim_due("a", now=AT) == []
    store.set_pause("job:j", False)
    (run,) = store.claim_due("a", now=AT)
    assert store.list_jobs()[0]["exhausted"] == 1
    store.start_run(run["run_id"], now=AT)
    store.finish_run(run["run_id"], "succeeded", now=AT)
    reopened = SchedulerStore(store.path)
    reopened.init()
    reopened.set_enabled("j", False)
    reopened.set_enabled("j", True)
    assert reopened.claim_due("b", now=AT + timedelta(days=2)) == []
    assert reopened.recent_runs()[0]["status"] == "succeeded"
    assert reopened.list_jobs()[0]["next_due_at"] == "2026-11-04T12:00:00Z"


@pytest.mark.parametrize("running", [False, True])
def test_once_lease_recovery_then_terminal_no_replay(tmp_path, running):
    store = make_store(tmp_path)
    (run,) = store.claim_due("a", now=AT)
    if running:
        store.start_run(run["run_id"], now=AT)
    reopened = SchedulerStore(store.path)
    reopened.init()
    assert reopened.claim_due("b", now=AT + timedelta(seconds=10)) == []
    (retry,) = reopened.claim_due("b", now=AT + timedelta(seconds=11))
    assert retry["attempt"] == 2 and retry["scheduled_for"] == run["scheduled_for"]
    reopened.start_run(retry["run_id"], now=AT + timedelta(seconds=11))
    reopened.finish_run(retry["run_id"], "failed", now=AT + timedelta(seconds=11))
    assert reopened.claim_due("c", now=AT + timedelta(days=1)) == []
    assert {r["status"] for r in reopened.recent_runs()} == {"abandoned", "failed"}


def test_once_concurrent_claim(tmp_path):
    store = make_store(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(lambda worker: SchedulerStore(store.path).claim_due(worker, now=AT), ["a", "b"]))
    assert sum(map(len, batches)) == 1


def test_once_authority_failure_consumes_occurrence_not_success(tmp_path):
    store = make_store(tmp_path)
    results = SchedulerService(store, require_authorities=True).tick(now=AT)
    assert results[0]["status"] == "failed"
    assert store.recent_runs()[0]["authority_error"] == "authority_configuration_required"
    assert store.claim_due("b", now=AT + timedelta(days=1)) == []


def test_once_explicit_due_cannot_reschedule(tmp_path):
    store = SchedulerStore(tmp_path / "state.db")
    store.init()
    with pytest.raises(ValueError):
        store.add_job("j", SPEC, "noop", {}, next_due_at=AT + timedelta(seconds=1))


def test_old_schema_migrates_exhaustion_default(tmp_path):
    store = SchedulerStore(tmp_path / "state.db")
    store.init()
    with sqlite3.connect(store.path) as conn:
        conn.execute("ALTER TABLE jobs DROP COLUMN exhausted")
    store.init()
    store.add_job("j", SPEC, "noop", {}, now=AT)
    assert store.list_jobs()[0]["exhausted"] == 0


def test_once_disabled_expired_lease_stays_disabled_until_enabled(tmp_path):
    store = make_store(tmp_path)
    (run,) = store.claim_due("a", now=AT)
    store.set_enabled("j", False)
    reopened = SchedulerStore(store.path)
    reopened.init()
    assert reopened.claim_due("b", now=AT + timedelta(seconds=11)) == []
    row = reopened.list_jobs()[0]
    assert row["enabled"] == 0 and row["exhausted"] == 0
    reopened.set_enabled("j", True)
    (retry,) = reopened.claim_due("b", now=AT + timedelta(seconds=12))
    assert retry["attempt"] == 2
    assert retry["scheduled_for"] == run["scheduled_for"]


def test_once_service_success_and_bach_projection(tmp_path):
    from ellmos_scheduler.bach import BachSchedulerAdapter

    store = make_store(tmp_path)
    results = SchedulerService(store).tick(now=AT)
    assert results[0]["status"] == "succeeded"
    reopened = SchedulerStore(store.path)
    reopened.init()
    assert SchedulerService(reopened).tick(now=AT + timedelta(days=1)) == []
    (projected,) = BachSchedulerAdapter(reopened.path).jobs(now=AT + timedelta(days=1))
    assert projected["exhausted"] is True and projected["next_run"] is None
    assert projected["status"] == "exhausted"


@pytest.mark.parametrize("running", [False, True])
def test_once_active_projection_does_not_claim_completion(tmp_path, running):
    from ellmos_scheduler.bach import BachSchedulerAdapter

    store = make_store(tmp_path)
    (run,) = store.claim_due("a", now=AT)
    if running:
        store.start_run(run["run_id"], now=AT)
    (projected,) = BachSchedulerAdapter(store.path).jobs(now=AT)
    assert projected["status"] == ("running" if running else "claimed")
    assert projected["exhausted"] is True
    assert projected["next_run"] is None


def test_once_cli_uses_existing_json_schedule(tmp_path):
    import json
    from ellmos_scheduler.cli import main

    db = tmp_path / "cli.db"
    assert main(["--db", str(db), "init"]) == 0
    assert (
        main(
            [
                "--db",
                str(db),
                "add",
                "--id",
                "once-cli",
                "--schedule",
                json.dumps(SPEC),
                "--executor",
                "noop",
                "--payload",
                "{}",
            ]
        )
        == 0
    )
    store = SchedulerStore(db)
    assert store.list_jobs()[0]["next_due_at"] == "2026-11-04T12:00:00Z"
    assert len(store.claim_due("cli-test", now=AT)) == 1
