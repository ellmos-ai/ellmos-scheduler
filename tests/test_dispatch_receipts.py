"""Crash-window/CAS tests with native temporary runs and simulated controller effects."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from ellmos_scheduler import AcceptedTaskResult, DispatchConflict, DispatchReceipts, RecoveryEvidence, SchedulerStore

BASE = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
DUE = BASE + timedelta(seconds=60)
INSTANCE = "a" * 32
PROFILE = "b" * 64
TASK_VERSION = "c" * 64


def setup(tmp_path, *, fixed=True):
    store = SchedulerStore(tmp_path / "state.db")
    store.init()
    store.add_job("job", {"kind": "interval", "seconds": 60}, "noop", {}, now=BASE, lease_seconds=10)
    (job,) = store.claim_due("scheduler-a", now=DUE)
    context = store.start_run_context(job["run_id"], worker_id="scheduler-a", now=DUE)
    receipts = DispatchReceipts(store)
    target = {
        "agent_id": "agent/native",
        "configuration_version": PROFILE,
        "task_id": 42 if fixed else None,
        "task_version": TASK_VERSION if fixed else None,
    }
    row = receipts.reserve(context, **target, now=DUE)
    return store, receipts, context, target, row


def prepare(receipts, context, row):
    return receipts.prepare(context, expected_version=row["version"], controller_instance=INSTANCE, now=DUE)


def claim(receipts, row):
    return receipts.claim_admission(
        row["occurrence_id"],
        expected_version=row["version"],
        controller_instance=INSTANCE,
        pid=123,
        process_create_time=100.25,
        host="synthetic-host",
        now=DUE,
    )


def owner(row):
    return {
        "expected_version": row["version"],
        "controller_instance": row["controller"]["service_instance"],
        "generation": row["controller"]["generation"],
    }


def launch(receipts, row):
    return receipts.launch_intent(row["occurrence_id"], **owner(row), now=DUE)


def bind(receipts, row, **changes):
    return receipts.bind_task(
        row["occurrence_id"],
        **owner(row),
        task_id=changes.get("task_id", 42),
        task_version=changes.get("task_version", TASK_VERSION),
        fence=changes.get("fence", 5),
        holder=row["controller"]["lease_worker_id"],
        now=DUE,
    )


def evidence(row, **changes):
    fields = {
        "controller_instance": row["controller"]["service_instance"],
        "generation": row["controller"]["generation"],
        "pid": row["controller"]["pid"],
        "process_create_time": row["controller"]["process_create_time"],
        "controller_gone": True,
        "leases_clear": True,
        "traces_closed": True,
        "native_admission_absent": True,
    }
    return RecoveryEvidence(**{**fields, **changes})


def complete(receipts, row, **changes):
    fields = {
        "task_id": 42,
        "task_version": TASK_VERSION,
        "fence": 5,
        "result_id": 90,
        "result_sha256": "d" * 64,
        "status_revision": 7,
        "accepted_status_event_id": 7,
        "acceptance_event_id": 8,
    }
    return receipts.complete_accepted(row["occurrence_id"], **owner(row), **{**fields, **changes}, now=DUE)


def retry(store, receipts, target):
    when = DUE + timedelta(seconds=11)
    (job,) = store.claim_due("scheduler-b", now=when)
    context = store.start_run_context(job["run_id"], worker_id="scheduler-b", now=when)
    return context, receipts.reserve(context, **target, now=when)


def test_native_context_reservation_and_send_intent_survive_reopen(tmp_path):
    store, receipts, context, target, row = setup(tmp_path)
    assert row["state"] == "prepared" and row["version"] == 1
    assert receipts.reserve(context, **target, now=DUE) == row
    row = prepare(receipts, context, row)
    reopened = DispatchReceipts(SchedulerStore(store.path))
    assert reopened.get(context.occurrence_id) == row
    assert row["state"] == "start_unknown"
    assert row["request_id"] == context.occurrence_id[:32]
    assert row["observation"] == {} and row["terminal"] == {}
    assert len(reopened.pending()) == 1 and len(reopened.history(context.occurrence_id)) == 2


@pytest.mark.parametrize(
    "field,value",
    [("claimed_by", "impostor"), ("job_id", "forged"), ("attempt", 99), ("scheduled_for", "2026-11-04T14:01:00+02:00")],
)
def test_forged_context_fields_cannot_create_another_occurrence(tmp_path, field, value):
    _, receipts, context, target, _ = setup(tmp_path)
    with pytest.raises(DispatchConflict):
        receipts.reserve(replace(context, **{field: value}), **target, now=DUE)
    assert len(receipts.pending()) == 1


def test_conflicting_target_and_stale_dispatch_cas_are_rejected(tmp_path):
    _, receipts, context, target, row = setup(tmp_path)
    with pytest.raises(DispatchConflict):
        receipts.reserve(context, **{**target, "configuration_version": "e" * 64}, now=DUE)
    prepared = prepare(receipts, context, row)
    with pytest.raises(DispatchConflict):
        claim(receipts, row)
    assert receipts.get(context.occurrence_id) == prepared


def test_rival_rpc_reservations_have_one_winner_and_launch_marker_before_effect(tmp_path):
    _, receipts, context, _, row = setup(tmp_path)
    row = prepare(receipts, context, row)

    def attempt(_):
        try:
            return claim(receipts, row)
        except DispatchConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [result for result in pool.map(attempt, range(2)) if result is not None]
    assert len(winners) == 1
    winner = winners[0]
    started = []
    # Simulated consumer: no physical effect is possible before this durable CAS succeeds.
    admitted = launch(receipts, winner)
    assert receipts.get(context.occurrence_id)["state"] == "launch_intent"
    started.append(admitted["controller"]["generation"])
    with pytest.raises(DispatchConflict):
        launch(receipts, winner)
        started.append("second")
    assert len(started) == 1


def test_scheduler_retry_invalidates_late_rpc_and_reuses_logical_request(tmp_path):
    store, receipts, context, target, row = setup(tmp_path)
    unknown = prepare(receipts, context, row)
    recovered_context, recovered = retry(store, receipts, target)
    assert recovered["request_id"] == unknown["request_id"]
    with pytest.raises(DispatchConflict):
        claim(receipts, unknown)
    ready = receipts.prepare(
        recovered_context,
        expected_version=recovered["version"],
        controller_instance=INSTANCE,
        now=DUE + timedelta(seconds=11),
    )
    admitted = receipts.claim_admission(
        ready["occurrence_id"],
        expected_version=ready["version"],
        controller_instance=INSTANCE,
        pid=123,
        process_create_time=100.25,
        host="synthetic-host",
        now=DUE + timedelta(seconds=11),
    )
    assert admitted["state"] == "admission_reserved"


def test_lost_start_response_reopens_same_generation_not_another_admission(tmp_path):
    store, receipts, context, target, row = setup(tmp_path)
    row = launch(receipts, claim(receipts, prepare(receipts, context, row)))
    old_generation = row["controller"]["generation"]
    _, recovered = retry(store, receipts, target)
    reopened = DispatchReceipts(SchedulerStore(store.path))
    assert reopened.get(context.occurrence_id)["controller"]["generation"] == old_generation
    with pytest.raises(DispatchConflict):
        reopened.claim_admission(
            context.occurrence_id,
            expected_version=recovered["version"],
            controller_instance=INSTANCE,
            pid=456,
            process_create_time=200,
            host="synthetic-host",
            now=DUE + timedelta(seconds=11),
        )


def test_accepted_result_after_lost_response_and_finished_worker_is_durable(tmp_path):
    store, receipts, context, target, row = setup(tmp_path)
    row = bind(receipts, launch(receipts, claim(receipts, prepare(receipts, context, row))))
    # Lost start ACK: independently verify native thread end before recording task acceptance.
    reopened = DispatchReceipts(SchedulerStore(store.path))
    row = reopened.observe(
        context.occurrence_id,
        **owner(row),
        worker_state="terminal",
        worker_thread_started=True,
        terminal=True,
        now=DUE,
    )
    terminal = complete(reopened, row)
    assert terminal["state"] == "terminal" and terminal["terminal"]["accepted"] is True
    assert terminal["terminal"]["outcome"] == "succeeded"
    assert terminal["controller"]["generation"] == row["controller"]["generation"]
    _, recovered = retry(store, receipts, target)
    assert recovered == terminal
    assert reopened.pending() == []
    with pytest.raises(DispatchConflict):
        claim(reopened, terminal)


@pytest.mark.parametrize("task_id,task_version", [(99, TASK_VERSION), (42, "e" * 64)])
def test_fixed_task_binding_rejects_foreign_queue_task_or_changed_version(tmp_path, task_id, task_version):
    _, receipts, context, _, row = setup(tmp_path)
    row = launch(receipts, claim(receipts, prepare(receipts, context, row)))
    with pytest.raises(DispatchConflict):
        bind(receipts, row, task_id=task_id, task_version=task_version)
    assert receipts.task_bindings(context.occurrence_id) == []


def test_unbound_result_wrong_generation_and_old_status_never_count_as_success(tmp_path):
    _, receipts, context, _, row = setup(tmp_path)
    row = launch(receipts, claim(receipts, prepare(receipts, context, row)))
    with pytest.raises(DispatchConflict):
        complete(receipts, row)
    row = bind(receipts, row)
    with pytest.raises(DispatchConflict):
        receipts.complete_accepted(
            context.occurrence_id,
            **{**owner(row), "generation": "f" * 32},
            task_id=42,
            task_version=TASK_VERSION,
            fence=5,
            result_id=90,
            result_sha256="d" * 64,
            status_revision=7,
            accepted_status_event_id=7,
            acceptance_event_id=8,
            now=DUE,
        )
    with pytest.raises(ValueError):
        complete(receipts, row, accepted_status_event_id=6)
    assert receipts.get(context.occurrence_id)["terminal"] == {}


@pytest.mark.parametrize("field", ["controller_gone", "leases_clear", "traces_closed", "native_admission_absent"])
def test_timeout_or_incomplete_recovery_evidence_cannot_rearm(tmp_path, field):
    _, receipts, context, _, row = setup(tmp_path)
    row = claim(receipts, prepare(receipts, context, row))
    with pytest.raises(DispatchConflict):
        receipts.recover_unlaunched(
            context, expected_version=row["version"], evidence=evidence(row, **{field: False}), now=DUE
        )
    assert receipts.get(context.occurrence_id)["state"] == "admission_reserved"


def test_only_proven_unlaunched_reservation_can_be_recovered(tmp_path):
    _, receipts, context, _, row = setup(tmp_path)
    row = claim(receipts, prepare(receipts, context, row))
    old_generation = row["controller"]["generation"]
    with pytest.raises(DispatchConflict):
        receipts.recover_unlaunched(context, expected_version=row["version"], evidence=evidence(row, pid=999), now=DUE)
    row = receipts.recover_unlaunched(context, expected_version=row["version"], evidence=evidence(row), now=DUE)
    assert row["state"] == "prepared" and row["controller"] == {}
    row = claim(receipts, prepare(receipts, context, row))
    assert row["controller"]["generation"] != old_generation
    row = launch(receipts, row)
    with pytest.raises(DispatchConflict):
        receipts.recover_unlaunched(context, expected_version=row["version"], evidence=evidence(row), now=DUE)


def test_process_loss_after_launch_is_failure_not_proof_of_nonstart(tmp_path):
    _, receipts, context, _, row = setup(tmp_path)
    row = launch(receipts, claim(receipts, prepare(receipts, context, row)))
    row = receipts.observe(
        context.occurrence_id,
        **owner(row),
        worker_state="unconfirmed",
        worker_thread_started=None,
        terminal=False,
        now=DUE,
    )
    terminal = receipts.complete_lost(context.occurrence_id, **owner(row), evidence=evidence(row), now=DUE)
    assert terminal["terminal"]["outcome"] == "failed" and terminal["terminal"]["accepted"] is False
    assert terminal["observation"]["worker_thread_started"] is None
    assert "never_started" not in terminal["terminal"]
    with pytest.raises(DispatchConflict):
        claim(receipts, terminal)


def test_expired_scheduler_lease_cannot_authorize_new_launch_intent(tmp_path):
    _, receipts, context, _, row = setup(tmp_path)
    row = claim(receipts, prepare(receipts, context, row))
    with pytest.raises(DispatchConflict):
        receipts.launch_intent(context.occurrence_id, **owner(row), now=DUE + timedelta(seconds=11))


def test_credentials_raw_terminal_json_and_lease_capabilities_have_no_write_contract(tmp_path):
    _, receipts, context, _, row = setup(tmp_path)
    row = bind(receipts, launch(receipts, claim(receipts, prepare(receipts, context, row))))
    with pytest.raises(TypeError):
        complete(receipts, row, token="must-not-store")
    with pytest.raises(TypeError):
        receipts.complete_accepted(context.occurrence_id, **owner(row), receipt={"lease_id": "must-not-store"})
    for snapshot in receipts.history(context.occurrence_id):
        assert "must-not-store" not in str(snapshot)
        assert snapshot["terminal"] == {}


def test_readonly_missing_database_does_not_initialize(tmp_path):
    import sqlite3

    path = tmp_path / "missing" / "state.db"
    receipts = DispatchReceipts(SchedulerStore(path))
    with pytest.raises(sqlite3.OperationalError):
        receipts.get("a" * 64)
    assert not path.parent.exists()


def test_recurring_appointments_keep_distinct_durable_requests(tmp_path):
    store, receipts, context, target, first = setup(tmp_path)
    store.finish_run(context.run_id, "succeeded", now=DUE)
    later = DUE + timedelta(seconds=60)
    (job,) = store.claim_due("scheduler-a", now=later)
    next_context = store.start_run_context(job["run_id"], worker_id="scheduler-a", now=later)
    second = receipts.reserve(next_context, **target, now=later)
    assert second["job_id"] == first["job_id"]
    assert second["occurrence_id"] != first["occurrence_id"]
    assert second["request_id"] != first["request_id"]
    assert len(DispatchReceipts(SchedulerStore(store.path)).pending()) == 2


@pytest.mark.parametrize(
    "state,started,terminal",
    [
        ("running", True, False),
        ("terminal", False, True),
        ("terminal", None, True),
    ],
)
def test_accepted_task_without_positive_worker_thread_end_is_not_success(tmp_path, state, started, terminal):
    _, receipts, context, _, row = setup(tmp_path)
    row = bind(receipts, launch(receipts, claim(receipts, prepare(receipts, context, row))))
    with pytest.raises(DispatchConflict):
        complete(receipts, row)
    row = receipts.observe(
        context.occurrence_id,
        **owner(row),
        worker_state=state,
        worker_thread_started=started,
        terminal=terminal,
        now=DUE,
    )
    with pytest.raises(DispatchConflict):
        complete(receipts, row)
    assert receipts.get(context.occurrence_id)["terminal"] == {}


def test_terminal_and_positive_start_observations_never_regress(tmp_path):
    _, receipts, context, _, row = setup(tmp_path)
    row = launch(receipts, claim(receipts, prepare(receipts, context, row)))
    row = receipts.observe(
        context.occurrence_id, **owner(row), worker_state="terminal", worker_thread_started=True, terminal=True, now=DUE
    )
    for state, started, terminal in [("running", True, False), ("terminal", False, True), ("terminal", None, True)]:
        with pytest.raises(DispatchConflict):
            receipts.observe(
                context.occurrence_id,
                **owner(row),
                worker_state=state,
                worker_thread_started=started,
                terminal=terminal,
                now=DUE,
            )
    assert receipts.get(context.occurrence_id) == row


@pytest.mark.parametrize("change", [{"task_id": 99}, {"fence": 6}])
def test_fixed_occurrence_accepts_exactly_one_task_binding(tmp_path, change):
    _, receipts, context, _, row = setup(tmp_path)
    row = bind(receipts, launch(receipts, claim(receipts, prepare(receipts, context, row))))
    assert bind(receipts, row) == row
    with pytest.raises(DispatchConflict):
        bind(receipts, row, **change)
    assert len(receipts.task_bindings(context.occurrence_id)) == 1


@pytest.mark.parametrize(
    "reason", ["task_rejected", "task_failed", "no_accepted_result", "cancelled", "review_not_accepted"]
)
def test_normal_failure_requires_positive_physical_end_and_bounded_reason(tmp_path, reason):
    _, receipts, context, _, row = setup(tmp_path)
    row = launch(receipts, claim(receipts, prepare(receipts, context, row)))
    with pytest.raises(DispatchConflict):
        receipts.complete_failure(context.occurrence_id, **owner(row), reason_code=reason, now=DUE)
    row = receipts.observe(
        context.occurrence_id, **owner(row), worker_state="terminal", worker_thread_started=True, terminal=True, now=DUE
    )
    with pytest.raises(ValueError):
        receipts.complete_failure(context.occurrence_id, **owner(row), reason_code="raw exception", now=DUE)
    terminal = receipts.complete_failure(context.occurrence_id, **owner(row), reason_code=reason, now=DUE)
    assert terminal["terminal"] == {"outcome": "failed", "accepted": False, "reason_code": reason}
    with pytest.raises(DispatchConflict):
        complete(receipts, terminal)


@pytest.mark.parametrize(
    "change",
    [
        {"native_admission_rejected": False},
        {"worker_thread_started": None},
        {"worker_thread_started": True},
        {"leases_clear": False},
        {"traces_closed": False},
    ],
)
def test_admission_rejection_needs_positive_native_nonstart_evidence(tmp_path, change):
    _, receipts, context, _, row = setup(tmp_path)
    row = claim(receipts, prepare(receipts, context, row))
    evidence = {
        "native_admission_rejected": True,
        "worker_thread_started": False,
        "leases_clear": True,
        "traces_closed": True,
    }
    with pytest.raises(DispatchConflict):
        receipts.complete_rejected(
            context.occurrence_id, **owner(row), reason_code="scope_denied", **{**evidence, **change}, now=DUE
        )
    terminal = receipts.complete_rejected(
        context.occurrence_id, **owner(row), reason_code="scope_denied", **evidence, now=DUE
    )
    assert terminal["terminal"]["accepted"] is False
    assert terminal["terminal"]["worker_thread_started"] is False


def test_admission_rejection_after_launch_intent_cannot_claim_nonstart(tmp_path):
    _, receipts, context, _, row = setup(tmp_path)
    row = launch(receipts, claim(receipts, prepare(receipts, context, row)))
    with pytest.raises(DispatchConflict):
        receipts.complete_rejected(
            context.occurrence_id,
            **owner(row),
            reason_code="admission_rejected",
            native_admission_rejected=True,
            worker_thread_started=False,
            leases_clear=True,
            traces_closed=True,
            now=DUE,
        )


@pytest.mark.parametrize("bad", ["missing", "foreign", "fence", "duplicate", "untyped"])
def test_queue_success_requires_exact_complete_accepted_binding_set(tmp_path, bad):
    _, receipts, context, _, row = setup(tmp_path, fixed=False)
    row = bind(receipts, launch(receipts, claim(receipts, prepare(receipts, context, row))))
    row = bind(receipts, row, task_id=43, fence=6)
    row = receipts.observe(
        context.occurrence_id, **owner(row), worker_state="terminal", worker_thread_started=True, terminal=True, now=DUE
    )
    first = AcceptedTaskResult(42, TASK_VERSION, 5, 90, "d" * 64, 7, 7, 8)
    second = AcceptedTaskResult(43, TASK_VERSION, 6, 91, "e" * 64, 9, 9, 10)
    with pytest.raises(DispatchConflict):
        complete(receipts, row)
    invalid = {
        "missing": [first],
        "foreign": [first, replace(second, task_id=99)],
        "fence": [first, replace(second, fence=99)],
        "duplicate": [first, first],
        "untyped": [first, {"task_id": 43}],
    }[bad]
    with pytest.raises((DispatchConflict, ValueError)):
        receipts.complete_accepted_results(context.occurrence_id, **owner(row), results=invalid, now=DUE)
    assert receipts.get(context.occurrence_id)["terminal"] == {}
    terminal = receipts.complete_accepted_results(context.occurrence_id, **owner(row), results=[first, second], now=DUE)
    assert terminal["terminal"]["accepted"] is True
    assert {r["task_id"] for r in terminal["terminal"]["results"]} == {42, 43}
    assert all(r["generation"] == row["controller"]["generation"] for r in terminal["terminal"]["results"])
