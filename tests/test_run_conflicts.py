from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from ellmos_scheduler.authorities import AuthorityResolution, AuthorityResolverRegistry
from ellmos_scheduler.executors import ExecutionResult, ExecutorRegistry
from ellmos_scheduler.service import SchedulerService
from ellmos_scheduler.store import RunStateConflict, SchedulerStore

BASE = datetime(2026, 10, 16, tzinfo=timezone.utc)
DUE = BASE + timedelta(seconds=60)
RECOVERY = BASE + timedelta(seconds=100)


@pytest.mark.parametrize('phase', ['finish', 'receipt', 'start', 'fail-claimed'])
def test_recovered_run_does_not_abort_independent_claim(tmp_path, phase):
    recovered, recovery_rows, executed = [], [], []

    def recover():
        recovered.extend(store.claim_due('new-worker', now=RECOVERY, job_ids=['a']))
        recovery_rows.extend(store.recent_runs())

    class RecoverAfterReceipt(SchedulerStore):
        def record_authority_receipt(self, run_id, *args, **kwargs):
            super().record_authority_receipt(run_id, *args, **kwargs)
            if phase in ('start', 'fail-claimed') and not recovered:
                recover()

    authorities = AuthorityResolverRegistry()

    def resolve(spec):
        if phase == 'receipt' and not recovered:
            recover()
        return AuthorityResolution('resolved', 'fixture://authority', 'a'*64, 'a'*64, 1)

    authorities.register('fixture', resolve, source_validator=lambda source: source)
    store = RecoverAfterReceipt(tmp_path/'state.db', authority_registry=authorities)
    store.init()
    specs = [{'id': 'rules', 'type': 'rules', 'resolver': 'fixture', 'required': True, 'source': {}}]
    for name in ('a', 'b'):
        store.add_job(name, {'kind': 'interval', 'seconds': 60}, 'fixture', {'name': name},
                      now=BASE, lease_seconds=30 if name == 'a' else 900,
                      authorities=[] if phase == 'fail-claimed' and name == 'a' else specs)

    def execute(payload, timeout):
        executed.append(payload['name'])
        if phase == 'finish' and payload['name'] == 'a':
            recover()
        return ExecutionResult('succeeded', 0, 'completed')

    service = SchedulerService(store, worker_id='old-worker', authority_registry=authorities,
                               registry=ExecutorRegistry({'fixture': execute}),
                               require_authorities=(phase == 'fail-claimed'))
    results = service.tick(now=DUE)
    assert len(results) == 2
    assert results[0]['job_id'] == 'a'
    assert results[0]['status'] == 'conflict'
    assert results[0]['phase'] == 'run-state-conflict'
    assert results[0]['observed_status'] == 'abandoned'
    assert results[0]['exit_code'] is None
    assert results[1]['job_id'] == 'b' and results[1]['status'] == 'succeeded'
    assert executed == (['a', 'b'] if phase == 'finish' else ['b'])
    before = {row['run_id']: row for row in recovery_rows if row['job_id'] == 'a'}
    after = {row['run_id']: row for row in store.recent_runs() if row['job_id'] == 'a'}
    assert after == before  # All stored fields of the original and retry remain unchanged.
    assert next(row for row in after.values() if row['run_id'] == recovered[0]['run_id'])['status'] == 'claimed'


@pytest.mark.parametrize('operation', ['start', 'receipt', 'fail', 'finish'])
@pytest.mark.parametrize('state', ['abandoned', 'succeeded', 'missing'])
def test_conflicting_store_transition_preserves_record_and_reports_observed_state(tmp_path, operation, state):
    store = SchedulerStore(tmp_path/'state.db')
    store.init()
    store.add_job('a', {'kind': 'interval', 'seconds': 60}, 'noop', {}, now=BASE)
    run_id = store.claim_due('worker', now=DUE)[0]['run_id']
    with store.connect() as connection:
        if state == 'missing':
            connection.execute('DELETE FROM runs WHERE run_id = ?', (run_id,))
        else:
            connection.execute('UPDATE runs SET status = ? WHERE run_id = ?', (state, run_id))
    before = store.recent_runs()
    with pytest.raises(RunStateConflict) as caught:
        if operation == 'start':
            store.start_run(run_id, now=DUE)
        elif operation == 'receipt':
            store.record_authority_receipt(run_id, [], 'a'*64)
        elif operation == 'fail':
            store.fail_claimed_run(run_id, error='late', now=DUE)
        else:
            store.finish_run(run_id, 'succeeded', output='late', now=DUE)
    assert isinstance(caught.value, RuntimeError)
    assert caught.value.observed_status == (None if state == 'missing' else state)
    assert store.recent_runs() == before


@pytest.mark.parametrize('failure', [RuntimeError, sqlite3.OperationalError])
def test_nonconflict_store_failure_still_propagates(tmp_path, failure):
    class BrokenStore(SchedulerStore):
        def start_run(self, run_id, **kwargs):
            raise failure('synthetic storage failure')

    store = BrokenStore(tmp_path/'state.db')
    store.init()
    store.add_job('a', {'kind': 'interval', 'seconds': 60}, 'noop', {}, now=BASE)
    with pytest.raises(failure, match='synthetic storage failure'):
        SchedulerService(store).tick(now=DUE)
    assert store.recent_runs()[0]['status'] == 'claimed'


def test_observed_completed_run_is_not_reported_as_this_ticks_success(tmp_path):
    completed = []

    class CompletedElsewhere(SchedulerStore):
        def record_authority_receipt(self, run_id, *args, **kwargs):
            super().record_authority_receipt(run_id, *args, **kwargs)
            if not completed:
                self.start_run(run_id, now=DUE)
                self.finish_run(run_id, 'succeeded', output='other completion', now=DUE)
                completed.extend(self.recent_runs())

    store = CompletedElsewhere(tmp_path/'state.db')
    store.init()
    store.add_job('a', {'kind': 'interval', 'seconds': 60}, 'noop', {}, now=BASE)
    result = SchedulerService(store).tick(now=DUE)[0]
    assert result['status'] == 'conflict' and result['exit_code'] is None
    assert result['observed_status'] == 'succeeded'
    assert store.recent_runs() == completed
