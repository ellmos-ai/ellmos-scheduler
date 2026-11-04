"""Native run metadata, separate from user configuration and payload context."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from ellmos_scheduler import ExecutionContext, ExecutionResult, ExecutorRegistry, SchedulerService, SchedulerStore
from ellmos_scheduler.store import RunStateConflict

BASE = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
DUE = BASE + timedelta(seconds=60)


def store_with_job(tmp_path, *, payload=None, authorities=None):
    store = SchedulerStore(tmp_path / "state.db")
    store.init()
    store.add_job(
        "actual-job",
        {"kind": "interval", "seconds": 60},
        "contextual",
        payload or {},
        now=BASE,
        lease_seconds=10,
        authorities=authorities,
    )
    return store


def contextual_registry(seen):
    registry = ExecutorRegistry(include_standard=False)

    def execute(payload, timeout, context):
        seen.append((payload, timeout, context))
        return ExecutionResult("succeeded", output="synthetic")

    registry.register_contextual("contextual", execute)
    return registry


def test_payload_cannot_forge_separate_immutable_native_context(tmp_path):
    forged = {
        "job_id": "forged",
        "run_id": "forged",
        "scheduled_for": "fake",
        "attempt": 999,
        "claimed_by": "other",
        "lease_expires_at": "2099",
        "occurrence_id": "forged",
    }
    payload = {**forged, "context": forged, "_execution_context": forged}
    store = store_with_job(tmp_path, payload=payload)
    seen = []
    (result,) = SchedulerService(store, "real-worker", contextual_registry(seen)).tick(now=DUE)
    actual_payload, _timeout, context = seen[0]
    assert actual_payload == payload
    assert isinstance(context, ExecutionContext)
    assert context.job_id == "actual-job" and context.run_id == result["run_id"]
    assert context.claimed_by == "real-worker" and context.attempt == 1
    assert context.scheduled_for == "2026-11-04T12:01:00Z"
    assert context.started_at == "2026-11-04T12:01:00Z"
    assert context.lease_expires_at == "2026-11-04T12:01:10Z"
    (persisted,) = store.recent_runs()
    for field in ("job_id", "run_id", "claimed_by", "scheduled_for", "attempt", "started_at", "lease_expires_at"):
        assert getattr(context, field) == persisted[field]
    assert len(context.occurrence_id) == 64 and context.occurrence_id != "forged"
    with pytest.raises(FrozenInstanceError):
        context.attempt = 999


def test_retry_context_keeps_logical_occurrence_but_changes_claim_and_run(tmp_path):
    store = store_with_job(tmp_path)
    (first,) = store.claim_due("first-worker", now=DUE)
    initial = store.start_run_context(first["run_id"], worker_id="first-worker", now=DUE)
    reopened = SchedulerStore(store.path)
    reopened.init()
    retry_time = DUE + timedelta(seconds=11)
    (retry,) = reopened.claim_due("recovery-worker", now=retry_time)
    recovered = reopened.start_run_context(retry["run_id"], worker_id="recovery-worker", now=retry_time)
    assert initial.occurrence_id == recovered.occurrence_id
    assert initial.scheduled_for == recovered.scheduled_for
    assert initial.run_id != recovered.run_id
    assert recovered.attempt == 2 and recovered.claimed_by == "recovery-worker"
    assert initial.lease_expires_at != recovered.lease_expires_at
    with pytest.raises(RunStateConflict):
        reopened.start_run_context(first["run_id"], worker_id="first-worker", now=retry_time)


def test_recurring_occurrences_have_distinct_stable_ids(tmp_path):
    store = store_with_job(tmp_path)
    seen = []
    registry = contextual_registry(seen)
    SchedulerService(store, "worker-a", registry).tick(now=DUE)
    SchedulerService(SchedulerStore(store.path), "worker-b", registry).tick(now=DUE + timedelta(seconds=60))
    assert len(seen) == 2
    first, second = (entry[2] for entry in seen)
    assert first.job_id == second.job_id
    assert first.occurrence_id != second.occurrence_id
    assert first.attempt == second.attempt == 1


@pytest.mark.parametrize("reason", ["wrong-worker", "expired", "missing"])
def test_context_admission_requires_current_owned_live_claim(tmp_path, reason):
    store = store_with_job(tmp_path)
    (job,) = store.claim_due("owner", now=DUE)
    worker, when, run_id = "owner", DUE, job["run_id"]
    if reason == "wrong-worker":
        worker = "impostor"
    if reason == "expired":
        when += timedelta(seconds=11)
    if reason == "missing":
        run_id = "0" * 64
    with pytest.raises(RunStateConflict):
        store.start_run_context(run_id, worker_id=worker, now=when)
    assert store.recent_runs()[0]["status"] == "claimed"


def test_context_admission_keeps_agent_definition_pause_gate(tmp_path):
    from ellmos_scheduler import AgentTriggers

    store = SchedulerStore(tmp_path / "state.db")
    store.init()
    triggers = AgentTriggers(store)
    triggers.create(
        "def",
        agent_id="agent",
        schedule={"kind": "once", "at": DUE.isoformat()},
        executor="contextual",
        enabled=True,
        now=BASE,
    )
    (job,) = store.claim_due("owner", now=DUE)
    store.set_pause("definition:def", True, now=DUE)
    with pytest.raises(RunStateConflict):
        store.start_run_context(job["run_id"], worker_id="owner", now=DUE)
    assert store.recent_runs()[0]["status"] == "claimed"


def test_required_authority_failure_prevents_contextual_executor(tmp_path):
    authority = {
        "id": "policy",
        "type": "policy",
        "required": True,
        "resolver": "file",
        "source": {"path": str(tmp_path / "missing.md")},
    }
    store = store_with_job(tmp_path, authorities=[authority])
    seen = []
    (result,) = SchedulerService(store, "worker", contextual_registry(seen)).tick(now=DUE)
    assert result["status"] == "failed" and result["phase"] == "authority-resolution"
    assert seen == []
    assert store.recent_runs()[0]["status"] == "failed"


def test_registry_missing_or_payload_context_never_invokes_contextual_callback():
    seen = []
    registry = contextual_registry(seen)
    assert registry.execute("contextual", {"context": {"run_id": "fake"}}, 10).status == "failed"
    assert registry.execute("contextual", {}, 10, context={"run_id": "fake"}).status == "failed"
    assert seen == []


def test_context_registry_conflicts_explicit_replacement_and_legacy_compatibility():
    registry = ExecutorRegistry(include_standard=False)

    def callback(payload, timeout, context):
        return ExecutionResult("succeeded")

    def legacy(payload, timeout):
        return ExecutionResult("succeeded", output="legacy")

    registry.register_contextual("adapter", callback)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("adapter", legacy)
    with pytest.raises(ValueError, match="already registered"):
        registry.register_contextual("adapter", callback)
    registry.register("adapter", legacy, replace=True)
    assert not registry.requires_context("adapter")
    assert registry.execute("adapter", {}, 1).output == "legacy"
    registry.register_contextual("adapter", callback, replace=True)
    assert registry.requires_context("adapter")
    assert registry.unregister("adapter") is callback
    assert not registry.requires_context("adapter")
    registry.register("adapter", legacy)
    assert registry.execute("adapter", {}, 1).output == "legacy"


def test_required_authority_resolved_before_native_context_callback(tmp_path):
    authority_path = tmp_path / "policy.md"
    authority_path.write_text("synthetic policy", encoding="utf-8")
    authority = {
        "id": "policy",
        "type": "policy",
        "required": True,
        "resolver": "file",
        "source": {"path": str(authority_path)},
    }
    store = store_with_job(tmp_path, authorities=[authority])
    seen = []
    registry = ExecutorRegistry(include_standard=False)

    def execute(payload, timeout, context):
        receipt = store.authority_receipt(context.run_id)
        assert receipt["authority_error"] == ""
        assert receipt["authorities"][0]["status"] == "resolved"
        seen.append(context)
        return ExecutionResult("succeeded")

    registry.register_contextual("contextual", execute)
    (result,) = SchedulerService(store, "worker", registry).tick(now=DUE)
    assert result["status"] == "succeeded" and len(seen) == 1


def test_contextual_global_registration_requires_context_and_cleans_up():
    from ellmos_scheduler import register_contextual_executor, unregister_executor
    from ellmos_scheduler.executors import DEFAULT_REGISTRY

    def callback(payload, timeout, context):
        raise AssertionError("missing context must not execute callback")

    register_contextual_executor("test-context", callback)
    try:
        assert DEFAULT_REGISTRY.requires_context("test-context")
        assert DEFAULT_REGISTRY.execute("test-context", {}, 1).status == "failed"
    finally:
        assert unregister_executor("test-context") is callback
    assert not DEFAULT_REGISTRY.requires_context("test-context")
