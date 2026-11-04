import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pytest
from ellmos_scheduler import EventTriggers, SchedulerStore, SchedulerService

AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def setup(tmp_path, enabled=True, authorities=None):
    s = SchedulerStore(tmp_path / "events.db")
    s.init()
    e = EventTriggers(s)
    e.create(
        "agent-trigger",
        event_type="task.accepted",
        executor="noop",
        payload={"agent_id": "agent-1"},
        enabled=enabled,
        authorities=authorities,
        lease_seconds=1,
        now=AT,
    )
    return s, e


def deliver(e, **kw):
    return e.deliver(
        "agent-trigger",
        event_id=kw.pop("event_id", "evt-1"),
        event_type=kw.pop("event_type", "task.accepted"),
        source=kw.pop("source", "native-task-adapter"),
        now=AT,
        **kw,
    )


def test_delivery_duplicate_restart_and_terminal(tmp_path):
    s, e = setup(tmp_path)
    first = deliver(e)
    e = EventTriggers(SchedulerStore(s.path))
    assert deliver(e)["duplicate"]
    job = s.list_jobs()[0]
    event = json.loads(job["payload_json"])["_scheduler_event"]
    assert json.loads(job["payload_json"])["agent_id"] == "agent-1"
    assert event["event_id"] == "evt-1" and event["lineage"] == ["agent-trigger"]
    assert len(SchedulerService(s).tick(now=AT)) == 1
    assert not SchedulerService(s).tick(now=AT + timedelta(days=1))
    assert deliver(e)["job_id"] == first["job_id"]
    assert e.deliveries("agent-trigger")[0]["job_id"] == first["job_id"]


def test_distinct_events_and_concurrent_duplicates(tmp_path):
    s, e = setup(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as p:
        results = list(p.map(lambda _: deliver(e), range(4)))
    assert sum(not r["duplicate"] for r in results) == 1
    deliver(e, event_id="evt-2")
    assert len(s.claim_due("a", now=AT)) == 2
    assert s.claim_due("b", now=AT) == []


def test_disabled_pause_cas_recovery(tmp_path):
    s, e = setup(tmp_path, enabled=False)
    deliver(e)
    assert not s.claim_due("a", now=AT)
    assert e.set_enabled("agent-trigger", True, expected_version=1, now=AT) == 2
    with pytest.raises(ValueError):
        e.set_enabled("agent-trigger", False, expected_version=1)
    s.set_pause("trigger:agent-trigger", True)
    assert not s.claim_due("a", now=AT)
    s.set_pause("trigger:agent-trigger", False)
    (a,) = s.claim_due("a", now=AT)
    e.set_enabled("agent-trigger", False, expected_version=2)
    assert not s.claim_due("b", now=AT + timedelta(seconds=2))
    e.set_enabled("agent-trigger", True, expected_version=3)
    (b,) = s.claim_due("b", now=AT + timedelta(seconds=3))
    assert b["attempt"] == 2 and a["scheduled_for"] == b["scheduled_for"]


@pytest.mark.parametrize(
    "kw",
    [
        {"event_id": ""},
        {"source": "bad\nsource"},
        {"event_type": "other"},
        {"lineage": ["agent-trigger"]},
        {"lineage": ["x"] * 8},
        {"lineage": ["x", "x"]},
    ],
)
def test_invalid_delivery_no_job(tmp_path, kw):
    s, e = setup(tmp_path)
    with pytest.raises(ValueError):
        deliver(e, **kw)
    assert not s.list_jobs()


def test_conflict_and_immutable_definition(tmp_path):
    s, e = setup(tmp_path)
    deliver(e)
    with pytest.raises(ValueError):
        deliver(e, source="other-source")
    with pytest.raises(ValueError):
        e.create("agent-trigger", event_type="task.accepted", executor="noop", payload={})
    assert len(s.list_jobs()) == 1


def test_authority_gate_and_no_starvation(tmp_path):
    s, e = setup(tmp_path, enabled=False)
    deliver(e)
    s.add_job("z-normal", {"kind": "once", "at": AT.isoformat()}, "noop", {}, now=AT)
    assert s.claim_due("a", now=AT, limit=1)[0]["id"] == "z-normal"
    e.set_enabled("agent-trigger", True, expected_version=1)
    results = SchedulerService(s, require_authorities=True).tick(now=AT)
    assert results[0]["status"] == "failed"
    assert (
        next(r for r in s.recent_runs() if r["job_id"].startswith("event-"))["authority_error"]
        == "authority_configuration_required"
    )


def test_disable_and_pause_between_claim_and_start(tmp_path):
    from ellmos_scheduler.store import RunStateConflict

    s, e = setup(tmp_path)
    deliver(e)
    (run,) = s.claim_due("a", now=AT)
    e.set_enabled("agent-trigger", False, expected_version=1)
    with pytest.raises(RunStateConflict):
        s.start_run(run["run_id"], now=AT)
    e.set_enabled("agent-trigger", True, expected_version=2)
    s.set_pause("trigger:agent-trigger", True)
    with pytest.raises(RunStateConflict):
        s.start_run(run["run_id"], now=AT)
    s.set_pause("trigger:agent-trigger", False)
    s.start_run(run["run_id"], now=AT)
    e.set_enabled("agent-trigger", False, expected_version=3)
    s.finish_run(run["run_id"], "succeeded", now=AT)
    assert s.recent_runs()[0]["status"] == "succeeded"
