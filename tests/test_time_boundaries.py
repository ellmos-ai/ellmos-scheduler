from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import threading

import pytest

from ellmos_scheduler import store as store_module
from ellmos_scheduler.authorities import AuthorityResolution, AuthorityResolverRegistry
from ellmos_scheduler.executors import ExecutionResult, ExecutorRegistry
from ellmos_scheduler.service import SchedulerService
from ellmos_scheduler.store import RunStateConflict, SchedulerStore

BASE = datetime(2026, 10, 16, tzinfo=timezone.utc)


def _store(tmp_path, *, due=BASE-timedelta(seconds=1)):
    store = SchedulerStore(tmp_path/'state.db')
    store.init()
    store.add_job('a', {'kind': 'interval', 'seconds': 3600}, 'noop', {},
                  now=BASE, next_due_at=due, lease_seconds=30)
    return store


@pytest.mark.parametrize('claimed_microseconds,checked_microseconds,expired', [
    (500000, 30000000, False), (500000, 30500000, False), (500000, 30500001, True),
    (0, 30000000, False), (0, 30000001, True), (0, 31000000, True),
])
def test_lease_recovery_compares_actual_instants(tmp_path, claimed_microseconds, checked_microseconds, expired):
    store = _store(tmp_path)
    original = store.claim_due('old', now=BASE+timedelta(microseconds=claimed_microseconds))[0]
    before = store.recent_runs()
    recovered = store.claim_due('new', now=BASE+timedelta(microseconds=checked_microseconds))
    assert bool(recovered) is expired
    if expired:
        assert recovered[0]['attempt'] == 2
        assert recovered[0]['scheduled_for'] == original['scheduled_for']
        assert next(row for row in store.recent_runs() if row['run_id'] == original['run_id'])['status'] == 'abandoned'
    else:
        assert store.recent_runs() == before


@pytest.mark.parametrize('due_microseconds,checked_microseconds,ready', [
    (500000, 0, False), (500000, 500000, True), (500000, 500001, True),
    (0, 500000, True), (500000, 1000000, True),
])
def test_due_boundary_compares_actual_instants(tmp_path, due_microseconds, checked_microseconds, ready):
    store = _store(tmp_path, due=BASE+timedelta(microseconds=due_microseconds))
    claims = store.claim_due('worker', now=BASE+timedelta(microseconds=checked_microseconds))
    assert bool(claims) is ready


@pytest.mark.parametrize('claimed_microseconds,started_microseconds,allowed', [
    (0, 30000000, True), (0, 30000001, False), (0, 31000000, False),
    (500000, 30000000, True), (500000, 30500000, True), (500000, 30500001, False),
])
def test_start_requires_current_lease(tmp_path, claimed_microseconds, started_microseconds, allowed):
    store = _store(tmp_path)
    claim = store.claim_due('worker', now=BASE+timedelta(microseconds=claimed_microseconds))[0]
    before = store.recent_runs()
    instant = BASE+timedelta(microseconds=started_microseconds)
    if allowed:
        store.start_run(claim['run_id'], now=instant)
        assert store.recent_runs()[0]['status'] == 'running'
    else:
        with pytest.raises(RunStateConflict) as caught:
            store.start_run(claim['run_id'], now=instant)
        assert caught.value.observed_status == 'claimed'
        assert store.recent_runs() == before


def test_due_order_is_chronological_before_limit(tmp_path):
    store = _store(tmp_path, due=BASE+timedelta(microseconds=500000))
    store.add_job('z-earlier', {'kind': 'interval', 'seconds': 3600}, 'noop', {},
                  now=BASE, next_due_at=BASE)
    claims = store.claim_due('worker', now=BASE+timedelta(seconds=1), limit=1)
    assert [row['id'] for row in claims] == ['z-earlier']


@pytest.mark.parametrize('earlier,later', [
    ('2026-10-16T00:00:00Z', '2026-10-16T00:00:00.500000Z'),
    ('2026-10-16T00:00:00Z', '2026-10-16T00:00:00.000001Z'),
    ('2026-10-16T01:00:00+01:00', '2026-10-16T00:00:00.000001Z'),
])
def test_history_and_latest_reads_order_mixed_precision_without_rewriting(tmp_path, earlier, later):
    store = _store(tmp_path)
    with store.connect() as connection:
        for run_id, stamp in [('earlier', earlier), ('later', later)]:
            connection.execute('''INSERT INTO runs(run_id, job_id, scheduled_for, claimed_by,
                lease_expires_at, status, finished_at) VALUES (?, 'a', ?, 'worker', ?, 'succeeded', ?)''',
                (run_id, stamp, stamp, stamp))
    assert store.recent_runs(limit=1)[0]['run_id'] == 'later'
    assert store.latest_runs_by_job()['a']['run_id'] == 'later'
    assert store.latest_successful_runs_by_job()['a']['run_id'] == 'later'
    rows = store.recent_runs()
    assert [row['scheduled_for'] for row in rows] == [later, earlier]


def test_expired_preflight_does_not_dispatch_and_other_claim_continues(tmp_path, monkeypatch):
    class Clock(datetime):
        current = BASE

        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz)

    monkeypatch.setattr(store_module, 'datetime', Clock)
    authorities = AuthorityResolverRegistry()

    def resolve(source):
        Clock.current = BASE+timedelta(seconds=31)
        return AuthorityResolution('resolved', 'fixture://rules', 'a'*64, 'a'*64, 1)

    authorities.register('fixture', resolve, source_validator=lambda source: source)
    store = SchedulerStore(tmp_path/'state.db', authority_registry=authorities)
    store.init()
    specs = [{'id': 'rules', 'type': 'rules', 'resolver': 'fixture', 'source': {}}]
    for name in ('a', 'b'):
        store.add_job(name, {'kind': 'interval', 'seconds': 3600}, 'fixture', {'name': name},
                      now=BASE, next_due_at=BASE-timedelta(seconds=1),
                      lease_seconds=30 if name == 'a' else 900, authorities=specs)
    dispatched = []

    def execute(payload, timeout):
        dispatched.append(payload['name'])
        return ExecutionResult('succeeded', 0)

    result = SchedulerService(store, registry=ExecutorRegistry({'fixture': execute})).tick()
    assert result[0]['status'] == 'conflict' and result[0]['observed_status'] == 'claimed'
    assert result[1]['status'] == 'succeeded'
    assert dispatched == ['b']


def test_invalid_expiry_is_storage_error_and_preserves_claim(tmp_path):
    store = _store(tmp_path)
    run_id = store.claim_due('worker', now=BASE)[0]['run_id']
    with store.connect() as connection:
        connection.execute("UPDATE runs SET lease_expires_at = 'invalid' WHERE run_id = ?", (run_id,))
    before = store.recent_runs()
    with pytest.raises(sqlite3.OperationalError):
        store.start_run(run_id, now=BASE)
    assert store.recent_runs() == before


def test_invalid_due_time_rolls_back_partial_expiry_recovery(tmp_path):
    store = _store(tmp_path)
    store.claim_due('old', now=BASE)
    store.add_job('broken', {'kind': 'interval', 'seconds': 3600}, 'noop', {}, now=BASE)
    with store.connect() as connection:
        connection.execute("UPDATE jobs SET next_due_at = 'invalid' WHERE id = 'broken'")
    jobs, runs = store.list_jobs(), store.recent_runs()
    with pytest.raises(sqlite3.OperationalError):
        store.claim_due('new', now=BASE+timedelta(seconds=31))
    assert store.list_jobs() == jobs
    assert store.recent_runs() == runs


def test_admission_rechecks_clock_after_waiting_for_writer(tmp_path, monkeypatch):
    started, observed_clock, done = threading.Event(), threading.Event(), threading.Event()
    errors = []

    class Clock(datetime):
        current = BASE

        @classmethod
        def now(cls, tz=None):
            observed_clock.set()
            return cls.current.astimezone(tz)

    store = _store(tmp_path)
    run_id = store.claim_due('worker', now=BASE)[0]['run_id']
    monkeypatch.setattr(store_module, 'datetime', Clock)

    def admit():
        started.set()
        try:
            store.start_run(run_id)
        except Exception as error:
            errors.append(error)
        finally:
            done.set()

    worker = None
    try:
        with store.connect() as writer:
            writer.execute('BEGIN IMMEDIATE')
            worker = threading.Thread(target=admit)
            worker.start()
            assert started.wait(5)
            observed_clock.wait(0.3)
            assert not done.is_set()  # Admission really waits behind this live writer.
            Clock.current = BASE+timedelta(seconds=31)
    finally:
        if worker is not None:
            worker.join(timeout=5)
    assert done.is_set() and not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], RunStateConflict)
    assert store.recent_runs()[0]['status'] == 'claimed'
