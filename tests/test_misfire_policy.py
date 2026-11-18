"""Behavior of explicit interval coalescing and guarded policy migration."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

import ellmos_scheduler
import ellmos_scheduler.store as store_module
from ellmos_scheduler import ExecutionResult, ExecutorRegistry, SchedulerService, SchedulerStore
from ellmos_scheduler.store import iso, parse_iso

UTC = timezone.utc
ANCHOR = datetime(2026, 10, 29, 16, 22, 44, 714586, tzinfo=UTC)
NOW = ANCHOR + timedelta(days=19, seconds=172)
INTERVAL = {"kind": "interval", "seconds": 300}


@pytest.fixture
def store(tmp_path):
    result = SchedulerStore(tmp_path / "scheduler.db")
    result.init()
    return result


def add(store, name="delta", *, due=ANCHOR, policy="coalesce_latest", **options):
    store.add_job(name, INTERVAL, "noop", {}, now=ANCHOR, next_due_at=due,
                  misfire_policy=policy, **options)


def complete(store, claim, now=NOW, status="succeeded"):
    store.start_run(claim["run_id"], now=now)
    store.finish_run(claim["run_id"], status, now=now)


def row(store, job_id="delta"):
    return next(job for job in store.list_jobs() if job["id"] == job_id)


def test_weeks_of_delta_backlog_yield_to_other_due_jobs_with_limit_one(store):
    add(store)
    store.add_job("routine", {"kind": "interval", "seconds": 14 * 86400},
                  "noop", {}, now=ANCHOR, next_due_at=NOW - timedelta(days=1))
    service = SchedulerService(store, "worker")
    assert [r["job_id"] for r in service.tick(now=NOW, limit=1)] == ["delta"]
    assert [r["job_id"] for r in service.tick(now=NOW, limit=1)] == ["routine"]
    assert service.tick(now=NOW, limit=1) == []
    delta = next(r for r in store.recent_runs() if r["job_id"] == "delta")
    assert delta["scheduled_for"] == iso(ANCHOR + timedelta(days=19))
    assert delta["coalesced_from"] == iso(ANCHOR)
    assert delta["coalesced_count"] == 19 * 86400 // 300
    assert delta["misfire_policy"] == "coalesce_latest"
    assert len(store.recent_runs()) == 2
    assert parse_iso(row(store)["next_due_at"]) == ANCHOR + timedelta(days=19, seconds=300)
    assert delta["status"] == "succeeded"  # Exactly one actual executor invocation.


def test_default_replay_keeps_every_occurrence(store):
    store.add_job("delta", INTERVAL, "noop", {}, now=ANCHOR, next_due_at=ANCHOR)
    service = SchedulerService(store, "worker")
    for _ in range(3):
        assert len(service.tick(now=NOW, limit=1)) == 1
    runs = sorted(store.recent_runs(), key=lambda r: r["scheduled_for"])
    assert [r["scheduled_for"] for r in runs] == [
        iso(ANCHOR + timedelta(seconds=300 * i)) for i in range(3)]
    assert all(r["coalesced_count"] == 0 and r["coalesced_from"] is None for r in runs)
    assert row(store)["misfire_policy"] == "replay"


@pytest.mark.parametrize("offset, skipped", [(0, 0), (299.999999, 0), (300, 1), (900.000001, 3)])
def test_coalescing_preserves_anchor_precision_and_exact_boundaries(store, offset, skipped):
    add(store)
    now = (ANCHOR + timedelta(seconds=offset)).astimezone(timezone(timedelta(hours=5, minutes=30)))
    claim = store.claim_due("worker", now=now)[0]
    assert claim["scheduled_for"] == iso(ANCHOR + timedelta(seconds=300 * skipped))
    assert claim["coalesced_count"] == skipped
    assert claim["coalesced_from"] == (iso(ANCHOR) if skipped else None)
    assert parse_iso(row(store)["next_due_at"]) == ANCHOR + timedelta(seconds=300 * (skipped + 1))


@pytest.mark.parametrize("policy,schedule", [
    ("skip_everything", INTERVAL),
    ("coalesce_latest", {"kind": "daily", "time": "12:00"}),
    ("coalesce_latest", {"kind": "once", "at": iso(ANCHOR)}),
    ("coalesce_latest", {"kind": "interval", "seconds": 0}),
])
def test_invalid_policy_cannot_create_job(store, policy, schedule):
    with pytest.raises(ValueError):
        store.add_job("invalid", schedule, "noop", {}, now=ANCHOR,
                      next_due_at=ANCHOR, misfire_policy=policy)
    assert store.list_jobs() == []


@pytest.mark.parametrize("started", [False, True])
def test_active_coalesced_claim_is_not_overlapped_or_allowed_to_consume_limit(store, started):
    add(store, lease_seconds=900)
    claim = store.claim_due("first", now=NOW)[0]
    if started:
        store.start_run(claim["run_id"], now=NOW)
    later = NOW + timedelta(seconds=400)
    add(store, "other", due=later)
    selected = store.claim_due("second", now=later, limit=1)
    assert [c["id"] for c in selected] == ["other"]
    assert len([r for r in store.recent_runs() if r["job_id"] == "delta"]) == 1


@pytest.mark.parametrize("started", [False, True])
def test_expired_claim_retries_original_occurrence_and_coalescing_receipt(store, started):
    add(store, lease_seconds=60)
    first = store.claim_due("first", now=NOW)[0]
    if started:
        store.start_run(first["run_id"], now=NOW)
    # A later tick must retry this claim, not relabel it as a newer occurrence.
    later = NOW + timedelta(days=2)
    retry = store.claim_due("second", now=later)[0]
    for field in ("scheduled_for", "misfire_policy", "coalesced_from", "coalesced_count"):
        assert retry[field] == first[field]
    assert retry["attempt"] == 2 and retry["run_id"] != first["run_id"]
    assert next(r for r in store.recent_runs() if r["run_id"] == first["run_id"])["status"] == "abandoned"
    complete(store, retry, later)
    following = store.claim_due("third", now=later)[0]
    assert following["scheduled_for"] == iso(ANCHOR + timedelta(days=21))
    assert following["attempt"] == 1
    assert following["coalesced_from"] == iso(parse_iso(first["scheduled_for"]) + timedelta(seconds=300))


def test_parallel_claimers_only_admit_one_coalesced_occurrence(store):
    add(store, lease_seconds=900)
    barrier = Barrier(2)

    def claim(worker):
        other = SchedulerStore(store.path)
        barrier.wait()
        return other.claim_due(worker, now=NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim, worker) for worker in ("a", "b")]
        claims = [c for future in futures for c in future.result(timeout=10)]
    assert len(claims) == 1
    assert len(store.recent_runs()) == 1


def test_policy_cas_updates_version_without_touching_dates_or_history(store):
    add(store, policy="replay")
    before = row(store)
    result = store.set_misfire_policy("delta", "coalesce_latest",
        expected_generation=before["generation"], expected_policy="replay", now=NOW)
    after = row(store)
    assert result == after
    assert after["generation"] == before["generation"] + 1
    assert after["misfire_policy"] == "coalesce_latest"
    for field in ("schedule_json", "payload_json", "executor", "next_due_at", "created_at",
                  "enabled", "lease_seconds", "timeout_seconds", "authorities_json"):
        assert after[field] == before[field]
    assert store.recent_runs() == []
    assert ellmos_scheduler.MISFIRE_POLICY_SCHEMA == "ellmos.scheduler.misfire-policy.v1"


@pytest.mark.parametrize("started", [False, True])
def test_policy_update_rechecks_active_claim_at_exact_expiry(store, started):
    add(store, policy="replay", lease_seconds=60)
    before = row(store)
    claim = store.claim_due("worker", now=NOW)[0]
    if started:
        store.start_run(claim["run_id"], now=NOW)
    after_claim = row(store)
    with pytest.raises(store_module.JobPolicyConflict, match="active_claim"):
        store.set_misfire_policy("delta", "coalesce_latest",
            expected_generation=before["generation"], expected_policy="replay",
            now=NOW + timedelta(seconds=60))
    assert row(store) == after_claim
    assert store.recent_runs()[0]["status"] == ("running" if started else "claimed")


def test_expired_replay_claim_survives_policy_migration_as_retry(store):
    add(store, policy="replay", lease_seconds=60)
    first = store.claim_due("worker", now=NOW)[0]
    later = NOW + timedelta(seconds=61)
    store.set_misfire_policy("delta", "coalesce_latest",
        expected_generation=1, expected_policy="replay", now=later)
    assert store.recent_runs()[0]["status"] == "claimed"  # The update only changes policy.
    retry = store.claim_due("next", now=later)[0]
    assert retry["scheduled_for"] == first["scheduled_for"] == iso(ANCHOR)
    assert retry["attempt"] == 2 and retry["coalesced_count"] == 0
    complete(store, retry, later)
    current = store.claim_due("next", now=later)[0]
    assert parse_iso(current["scheduled_for"]) > ANCHOR + timedelta(days=18)


def test_stale_policy_generation_and_expected_policy_fail_without_mutation(store):
    add(store, policy="replay")
    store.set_authorities("delta", [], now=NOW)
    before = row(store)
    for generation, policy in [(1, "replay"), (2, "coalesce_latest")]:
        with pytest.raises(store_module.JobPolicyConflict, match="stale"):
            store.set_misfire_policy("delta", "coalesce_latest",
                expected_generation=generation, expected_policy=policy, now=NOW)
        assert row(store) == before


def test_parallel_policy_updates_have_one_cas_winner(store):
    add(store, policy="replay")
    barrier = Barrier(2)

    def update():
        other = SchedulerStore(store.path)
        barrier.wait()
        try:
            other.set_misfire_policy("delta", "coalesce_latest",
                expected_generation=1, expected_policy="replay", now=NOW)
            return "changed"
        except store_module.JobPolicyConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(update) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures) == ["changed", "conflict"]
    assert row(store)["generation"] == 2


@pytest.mark.parametrize("status", ["failed", "timed_out"])
def test_failed_coalesced_execution_does_not_invent_success_or_replay_skipped_runs(store, status):
    add(store)
    calls = []
    registry = ExecutorRegistry(include_standard=False)

    def execute(payload, timeout):
        calls.append(payload)
        return ExecutionResult(status, error="expected test outcome")

    registry.register("noop", execute)
    service = SchedulerService(store, "worker", registry=registry)
    assert service.tick(now=NOW)[0]["status"] == status
    assert service.tick(now=NOW) == []
    assert calls == [{}]
    assert store.latest_successful_runs_by_job() == {}
    runs = store.recent_runs()
    assert len(runs) == 1 and runs[0]["status"] == status and runs[0]["coalesced_count"] > 5000


def test_policy_update_rejects_noninterval_and_invalid_version(store):
    store.add_job("once", {"kind": "once", "at": iso(ANCHOR)}, "noop", {}, now=ANCHOR)
    before = row(store, "once")
    with pytest.raises(ValueError, match="interval"):
        store.set_misfire_policy("once", "coalesce_latest",
            expected_generation=1, expected_policy="replay", now=NOW)
    assert row(store, "once") == before
    for invalid in (True, 0, "1"):
        with pytest.raises(ValueError, match="generation"):
            store.set_misfire_policy("once", "replay",
                expected_generation=invalid, expected_policy="replay", now=NOW)


def test_historical_036_schema_migrates_without_rewriting_existing_rows(tmp_path):
    import json
    import sqlite3
    from pathlib import Path

    path = tmp_path / "historical.db"
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript((Path(__file__).parent / "fixtures/scheduler-f2740ba7.sql").read_text())
        conn.execute(
            """INSERT INTO jobs(id,schedule_json,executor,payload_json,next_due_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            ("delta", json.dumps(INTERVAL), "noop", "{}", iso(ANCHOR), iso(ANCHOR), iso(ANCHOR)))
        conn.execute(
            """INSERT INTO runs(run_id,job_id,scheduled_for,claimed_by,lease_expires_at,status,
                                started_at,finished_at,output)
               VALUES (?,?,?,?,?,'succeeded',?,?,?)""",
            ("historical-success", "delta", iso(ANCHOR-timedelta(seconds=300)), "historical",
             iso(ANCHOR), iso(ANCHOR-timedelta(seconds=10)), iso(ANCHOR), "historical receipt"))
        old_job = dict(conn.execute("SELECT * FROM jobs").fetchone())
        old_run = dict(conn.execute("SELECT * FROM runs").fetchone())
    store = SchedulerStore(path)
    # Inspection of old state must remain read-only and must not add columns.
    assert store.list_jobs()[0] == old_job
    store.init()
    store.init()  # Migration is restart-safe.
    migrated_job, migrated_run = row(store), store.recent_runs()[0]
    assert {k: migrated_job[k] for k in old_job} == old_job
    assert {k: migrated_run[k] for k in old_run} == old_run
    assert migrated_job["misfire_policy"] == migrated_run["misfire_policy"] == "replay"
    assert migrated_run["coalesced_count"] == 0 and migrated_run["coalesced_from"] is None
    assert store.latest_successful_runs_by_job()["delta"]["run_id"] == "historical-success"
    store.set_misfire_policy("delta", "coalesce_latest",
        expected_generation=1, expected_policy="replay", now=NOW)
    claim = store.claim_due("new", now=NOW)[0]
    assert claim["coalesced_count"] == 19 * 86400 // 300
    assert store.latest_successful_runs_by_job()["delta"]["run_id"] == "historical-success"


@pytest.mark.parametrize("_repeat", range(5))
def test_claim_and_policy_change_are_serialized_at_the_native_boundary(store, _repeat):
    add(store, policy="replay")
    barrier = Barrier(2)

    def update():
        other = SchedulerStore(store.path)
        barrier.wait()
        try:
            other.set_misfire_policy("delta", "coalesce_latest",
                expected_generation=1, expected_policy="replay", now=NOW)
            return "changed"
        except store_module.JobPolicyConflict as error:
            assert str(error) == "active_claim"
            return "conflict"

    def claim():
        other = SchedulerStore(store.path)
        barrier.wait()
        return other.claim_due("racing-worker", now=NOW)[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        change, acquisition = pool.submit(update), pool.submit(claim)
        outcome, claimed = change.result(timeout=10), acquisition.result(timeout=10)
    assert len(store.recent_runs()) == 1
    if outcome == "changed":
        assert row(store)["misfire_policy"] == claimed["misfire_policy"] == "coalesce_latest"
        assert claimed["coalesced_count"] > 5000
    else:
        assert row(store)["misfire_policy"] == claimed["misfire_policy"] == "replay"
        assert claimed["scheduled_for"] == iso(ANCHOR) and claimed["coalesced_count"] == 0



@pytest.mark.parametrize("expired_before_policy", [False, True])
@pytest.mark.parametrize("retry_outcome", ["succeeded", "failed", "timed_out"])
def test_separated_expired_replay_occurrences_retry_without_recounting_success(
    store, expired_before_policy, retry_outcome
):
    base = datetime(2026, 11, 17, tzinfo=UTC)
    def stamp(seconds):
        return base + timedelta(seconds=seconds)

    store.add_job("delta", {"kind": "interval", "seconds": 60}, "noop", {},
                  now=base, next_due_at=base, lease_seconds=180)
    first = store.claim_due("old-zero", now=stamp(0), limit=1)[0]
    middle = store.claim_due("old-success", now=stamp(60), limit=1)[0]
    complete(store, middle, stamp(60))
    last = store.claim_due("old-two", now=stamp(120), limit=1)[0]
    middle_receipt = next(r for r in store.recent_runs() if r["run_id"] == middle["run_id"])

    if expired_before_policy:
        # An old replay owner can rewind the cursor while paused, before upgrade.
        store.set_pause("job:delta", True, now=stamp(301))
        assert store.claim_due("old-paused", now=stamp(301), limit=1) == []
        assert row(store)["next_due_at"] == iso(stamp(0))
        store.set_pause("job:delta", False, now=stamp(301))
    before_policy = row(store)["next_due_at"]
    store.set_misfire_policy("delta", "coalesce_latest",
        expected_generation=1, expected_policy="replay", now=stamp(301))
    assert row(store)["next_due_at"] == before_policy  # CAS never changes dates.

    for original, outcome in ((first, retry_outcome), (last, "succeeded")):
        retry = store.claim_due("new-owner", now=stamp(301), limit=1)[0]
        assert retry["scheduled_for"] == original["scheduled_for"]
        assert retry["attempt"] == 2 and retry["misfire_policy"] == "replay"
        assert retry["coalesced_count"] == 0 and retry["coalesced_from"] is None
        assert row(store)["next_due_at"] == iso(stamp(180))
        complete(store, retry, stamp(301), outcome)

    fresh = store.claim_due("new-owner", now=stamp(301), limit=1)[0]
    assert fresh["scheduled_for"] == iso(stamp(300)) and fresh["attempt"] == 1
    assert fresh["coalesced_from"] == iso(stamp(180)) and fresh["coalesced_count"] == 2
    assert row(store)["next_due_at"] == iso(stamp(360))
    assert next(r for r in store.recent_runs() if r["run_id"] == middle["run_id"]) == middle_receipt
    assert len([r for r in store.recent_runs() if r["scheduled_for"] == iso(stamp(60))]) == 1


def test_expired_retry_remains_eligible_before_future_high_water_cursor(store):
    base = datetime(2026, 11, 17, tzinfo=UTC)
    store.add_job("delta", {"kind": "interval", "seconds": 60}, "noop", {},
                  now=base, next_due_at=base, lease_seconds=1, misfire_policy="coalesce_latest")
    first = store.claim_due("first", now=base, limit=1)[0]
    retry_time = base + timedelta(seconds=2)
    retry = store.claim_due("retry", now=retry_time, limit=1)[0]
    assert retry["scheduled_for"] == first["scheduled_for"]
    assert retry["attempt"] == 2
    assert row(store)["next_due_at"] == iso(base + timedelta(seconds=60))
    complete(store, retry, retry_time)
    assert store.claim_due("third", now=retry_time, limit=1) == []


def test_migration_after_completed_legacy_retry_never_counts_admitted_successes_as_omitted(store):
    base = datetime(2026, 11, 17, tzinfo=UTC)
    def stamp(seconds):
        return base + timedelta(seconds=seconds)

    store.add_job("delta", {"kind": "interval", "seconds": 60}, "noop", {},
                  now=base, next_due_at=base, lease_seconds=180)
    store.claim_due("expired", now=stamp(0), limit=1)
    for seconds in (60, 120):
        completed = store.claim_due("completed", now=stamp(seconds), limit=1)[0]
        complete(store, completed, stamp(seconds))
    legacy_retry = store.claim_due("legacy-retry", now=stamp(301), limit=1)[0]
    assert legacy_retry["scheduled_for"] == iso(stamp(0))
    complete(store, legacy_retry, stamp(301))
    assert row(store)["next_due_at"] == iso(stamp(60))
    previous = {r["run_id"]: r for r in store.recent_runs()}
    store.set_misfire_policy("delta", "coalesce_latest",
        expected_generation=1, expected_policy="replay", now=stamp(301))
    fresh = store.claim_due("new-owner", now=stamp(301), limit=1)[0]
    assert fresh["scheduled_for"] == iso(stamp(300))
    assert fresh["coalesced_from"] == iso(stamp(180))
    assert fresh["coalesced_count"] == 2
    assert all(r == previous[r["run_id"]] for r in store.recent_runs() if r["run_id"] in previous)
