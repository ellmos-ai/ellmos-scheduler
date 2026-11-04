from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import pytest
from ellmos_scheduler import AgentTriggers, DefinitionConflict, SchedulerStore
from ellmos_scheduler.store import RunStateConflict

AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
ONCE = {"kind": "once", "at": AT.isoformat()}
EVENT = {"kind": "event", "event_type": "task.accepted"}


def setup(tmp_path, schedule=ONCE, enabled=True):
    s = SchedulerStore(tmp_path / "state.db")
    s.init()
    a = AgentTriggers(s)
    a.create("stable", agent_id="agent-1", schedule=schedule, executor="noop", enabled=enabled, now=AT, lease_seconds=1)
    return s, a


def deliver(a, version=1, event_id="evt-1", source="native"):
    return a.deliver(
        "stable", expected_version=version, event_id=event_id, event_type="task.accepted", source=source, now=AT
    )


def test_shared_crud_versions_and_readback(tmp_path):
    s, a = setup(tmp_path)
    assert a.get("stable") == a.list(agent_id="agent-1")[0]
    updated = a.update("stable", expected_version=1, changes={"payload": {"task_id": 42}}, now=AT)
    assert updated["id"] == "stable" and updated["version"] == 2 and updated["revision"] == 2
    with pytest.raises(DefinitionConflict):
        a.update("stable", expected_version=1, changes={"enabled": False})
    (run,) = s.claim_due("a", now=AT)
    assert json.loads(run["payload_json"])["task_id"] == 42
    assert json.loads(run["payload_json"])["_agent_trigger"]["revision"] == 2
    assert len(a.history("stable")) == 2


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_edit_or_delete_between_claim_start(tmp_path, operation):
    s, a = setup(tmp_path)
    (run,) = s.claim_due("a", now=AT)
    if operation == "update":
        a.update("stable", expected_version=1, changes={"agent_id": "agent-2"}, now=AT)
    else:
        a.delete("stable", expected_version=1, now=AT)
    with pytest.raises(RunStateConflict):
        s.start_run(run["run_id"], now=AT)
    # Obsolete claimed lease blocks replacement until recovery expires it.
    assert not s.claim_due("b", now=AT)
    claimed = s.claim_due("b", now=AT + timedelta(seconds=2))
    assert len(claimed) == (1 if operation == "update" else 0)


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_running_snapshot_can_finish_without_overlap(tmp_path, operation):
    s, a = setup(tmp_path)
    (run,) = s.claim_due("a", now=AT)
    s.start_run(run["run_id"], now=AT)
    if operation == "update":
        a.update("stable", expected_version=1, changes={"agent_id": "agent-2"}, now=AT)
    else:
        a.delete("stable", expected_version=1, now=AT)
    assert not s.claim_due("b", now=AT)
    s.finish_run(run["run_id"], "succeeded", now=AT)
    newer = s.claim_due("b", now=AT)
    assert len(newer) == (1 if operation == "update" else 0)
    assert json.loads(run["payload_json"])["agent_id"] == "agent-1"


def test_enable_is_not_rearm_once_and_restart(tmp_path):
    s, a = setup(tmp_path)
    (run,) = s.claim_due("a", now=AT)
    s.start_run(run["run_id"], now=AT)
    s.finish_run(run["run_id"], "succeeded", now=AT)
    a.update("stable", expected_version=1, changes={"enabled": False}, now=AT)
    enabled = a.update("stable", expected_version=2, changes={"enabled": True}, now=AT)
    assert enabled["revision"] == 1
    reopened = SchedulerStore(s.path)
    reopened.init()
    assert not reopened.claim_due("b", now=AT + timedelta(days=1))
    # Identical configuration also preserves exhausted state.
    a.update("stable", expected_version=3, changes={"schedule": ONCE}, now=AT)
    assert len(s.list_jobs()) == 1


def test_tombstone_never_reuses_id_and_retains_audit(tmp_path):
    s, a = setup(tmp_path)
    a.delete("stable", expected_version=1, now=AT)
    assert a.list() == [] and a.get("stable")["deleted"]
    assert a.list(include_deleted=True)[0]["version"] == 2
    with pytest.raises(DefinitionConflict):
        a.create("stable", agent_id="x", schedule=ONCE, executor="noop")
    assert len(a.history("stable")) == 2 and len(s.list_jobs()) == 1
    assert not s.claim_due("b", now=AT + timedelta(days=1))


def test_event_dedupe_across_revisions_and_changed_payload(tmp_path):
    s, a = setup(tmp_path, schedule=EVENT)
    first = deliver(a)
    a.update("stable", expected_version=1, changes={"payload": {"task_id": 42}}, now=AT)
    duplicate = deliver(a, 2)
    assert duplicate["duplicate"] and duplicate["job_id"] == first["job_id"]
    with pytest.raises(DefinitionConflict):
        deliver(a, 2, source="other")
    assert not s.claim_due("a", now=AT)  # obsolete pending old event blocked
    deliver(a, 2, event_id="evt-2")
    (run,) = s.claim_due("a", now=AT)
    assert json.loads(run["payload_json"])["task_id"] == 42


def test_cas_race_and_paused_no_starvation(tmp_path):
    s, a = setup(tmp_path)

    def update(value):
        try:
            return a.update("stable", expected_version=1, changes={"payload": {"v": value}}, now=AT)
        except DefinitionConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, [1, 2]))
    assert sum(r is not None for r in results) == 1
    s.set_pause("definition:stable", True)
    s.add_job("z-normal", ONCE, "noop", {}, now=AT)
    assert s.claim_due("a", now=AT, limit=1)[0]["id"] == "z-normal"
    s.set_pause("definition:stable", False)
    (run,) = s.claim_due("b", now=AT)
    s.set_pause("definition:stable", True)
    with pytest.raises(RunStateConflict):
        s.start_run(run["run_id"], now=AT)


def test_readonly_does_not_create_database(tmp_path):
    path = tmp_path / "absent.db"
    a = AgentTriggers(SchedulerStore(path))
    with pytest.raises(sqlite3.OperationalError):
        a.list()
    assert not path.exists()


@pytest.mark.parametrize(
    "schedule",
    [
        {"kind": "daily", "time": "13:00", "timezone": "UTC"},
        {"kind": "cron", "expression": "0 13 * * *", "timezone": "UTC"},
    ],
)
def test_recurring_definition_materializes_existing_schedule(tmp_path, schedule):
    s, _a = setup(tmp_path, schedule=schedule)
    at = AT + timedelta(hours=1)
    (r,) = s.claim_due("a", now=at)
    s.start_run(r["run_id"], now=at)
    s.finish_run(r["run_id"], "succeeded", now=at)
    next_day = at + timedelta(days=1)
    assert len(s.claim_due("b", now=next_day)) == 1


def test_multiple_events_same_definition_never_overlap_in_batch(tmp_path):
    s, a = setup(tmp_path, schedule=EVENT)
    deliver(a, event_id="evt-1")
    deliver(a, event_id="evt-2")
    (first,) = s.claim_due("a", now=AT, limit=20)
    assert not s.claim_due("b", now=AT)
    s.start_run(first["run_id"], now=AT)
    assert not s.claim_due("b", now=AT)
    s.finish_run(first["run_id"], "succeeded", now=AT)
    (second,) = s.claim_due("b", now=AT)
    assert second["id"] != first["id"]
