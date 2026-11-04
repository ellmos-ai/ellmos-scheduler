"""Native GUI projection contract without a host, HTTP framework or executor effects."""

from copy import deepcopy

import pytest

from ellmos_scheduler import AgentTriggers, SchedulerStore, TriggerProjectionError, execute_trigger_request


@pytest.fixture
def store(tmp_path, monkeypatch):
    value = SchedulerStore(tmp_path / "scheduler.db")
    value.init()
    monkeypatch.setattr(SchedulerStore, "init", lambda self: pytest.fail("projection must not initialize"))
    return value


def definition(identifier="shared/a", **changes):
    return {
        "id": identifier,
        "expected_version": 0,
        "agent_id": "native-agent",
        "schedule": {"kind": "once", "at": "2099-01-01T12:00:00Z"},
        "executor": "noop",
        "payload": {"message": "synthetic"},
        **changes,
    }


def create(store, identifier="shared/a", **changes):
    return execute_trigger_request(store, "create", identifier, definition(identifier, **changes))


def assert_error(status, reason, callback):
    with pytest.raises(TriggerProjectionError) as observed:
        callback()
    assert observed.value.status == status
    assert observed.value.reason_code == reason
    assert observed.value.detail()["reason_code"] == reason
    return observed.value


def test_shared_crud_readback_cas_tombstones_and_no_execution(store):
    saved = create(store)
    assert saved["schema"] == "bach.agent-triggers.v1"  # historical shared-GUI wire namespace
    assert saved["provider"] == "ellmos-scheduler" and saved["state"] == "available"
    assert saved["trigger"]["version"] == 1 and saved["trigger"]["enabled"] is False
    assert saved["ack"] == {"configuration_saved": True, "readback_verified": True, "worker_started": False}
    assert execute_trigger_request(store, "get", "shared/a")["trigger"] == saved["trigger"]
    assert execute_trigger_request(store, "list", agent_id="other")["triggers"] == []
    changed = execute_trigger_request(store, "update", "shared/a", {"expected_version": 1, "changes": {"enabled": True}})
    assert changed["trigger"]["version"] == 2
    assert_error(409, "version_conflict", lambda: execute_trigger_request(
        store, "update", "shared/a", {"expected_version": 1, "changes": {"enabled": False}}))
    deleted = execute_trigger_request(store, "delete", "shared/a", {"expected_version": 2})
    assert deleted["trigger"]["deleted"] is True and deleted["trigger"]["version"] == 3
    assert execute_trigger_request(store, "get", "shared/a")["trigger"] == deleted["trigger"]
    assert store.recent_runs() == []


@pytest.mark.parametrize("operation", ["list", "get", "create", "update", "delete", "deliver"])
def test_missing_store_stays_unavailable_without_creation(tmp_path, operation):
    path = tmp_path / "missing" / "state.db"
    error = assert_error(503, "schema_unavailable", lambda: execute_trigger_request(
        SchedulerStore(path), operation, "shared/a", definition()))
    assert str(path) not in str(error.detail())
    assert not path.parent.exists()


@pytest.mark.parametrize("operation", ["", "unknown", None, ["deliver"]])
def test_unknown_operation_cannot_materialize_an_event(store, operation):
    create(store, schedule={"kind": "event", "event_type": "task.accepted"})
    assert_error(400, "unknown_operation", lambda: execute_trigger_request(
        store, operation, "shared/a", {"expected_version": 1, "event_id": "event-1",
        "event_type": "task.accepted", "source": "synthetic"}))
    assert store.list_jobs() == [] and store.recent_runs() == []


def test_identifier_mismatch_does_not_create_another_identity(store):
    assert_error(400, "identifier_mismatch", lambda: execute_trigger_request(
        store, "create", "other", definition()))
    assert execute_trigger_request(store, "list")["triggers"] == []


def test_registry_names_are_explicit_host_metadata_not_callbacks(store):
    assert_error(400, "unknown_executor", lambda: create(store, executor="host-agent"))
    saved = execute_trigger_request(store, "create", "custom", definition("custom", executor="host-agent"),
                                   registered_executors=("host-agent",))
    assert saved["trigger"]["executor"] == "host-agent"
    assert_error(503, "invalid_executor_registry", lambda: execute_trigger_request(
        store, "list", registered_executors={"host-agent": lambda: pytest.fail("callback must not run")}))
    assert store.recent_runs() == []


@pytest.mark.parametrize("payload", [{"authorization": "private"}, {"nested": [{"API-KEY": "private"}]}])
def test_credential_fields_cannot_be_stored_or_exposed(store, monkeypatch, payload):
    assert_error(400, "invalid_request", lambda: create(store, payload=payload))
    assert execute_trigger_request(store, "list")["triggers"] == []
    saved = create(store)
    original = AgentTriggers.get
    def leaking(self, identifier):
        row = original(self, identifier)
        row["payload"] = payload
        return row
    monkeypatch.setattr(AgentTriggers, "get", leaking)
    error = assert_error(503, "invalid_provider_snapshot", lambda: execute_trigger_request(store, "get", saved["trigger"]["id"]))
    assert "private" not in str(error.detail())


def test_mutation_is_not_acknowledged_without_matching_independent_readback(store, monkeypatch):
    original = AgentTriggers.get
    calls = []
    def changed(self, identifier):
        row = original(self, identifier)
        calls.append(identifier)
        row = deepcopy(row)
        row["version"] += 1
        return row
    monkeypatch.setattr(AgentTriggers, "get", changed)
    assert_error(503, "readback_unverified", lambda: create(store))
    assert calls  # error is a failed readback, never a saved acknowledgement
    assert store.recent_runs() == []


def test_event_materialization_has_independent_provenance_and_dedupe_without_runs(store):
    create(store, schedule={"kind": "event", "event_type": "task.accepted"})
    payload = {"expected_version": 1, "event_id": "event-1", "event_type": "task.accepted", "source": "synthetic"}
    first = execute_trigger_request(store, "deliver", "shared/a", payload)
    second = execute_trigger_request(store, "deliver", "shared/a", payload)
    assert first["delivery"]["state"] == "materialized" and first["delivery"]["duplicate"] is False
    assert second["delivery"]["duplicate"] is True
    assert first["delivery"]["job_id"] == second["delivery"]["job_id"]
    assert first["ack"] == {"configuration_saved": False, "readback_verified": True, "worker_started": False}
    assert store.recent_runs() == []


@pytest.mark.parametrize("payload", [{"note": "prefix synthetic-secret suffix"}, {"nested": [{"synthetic-secret": "note"}]}])
def test_host_canonical_transport_credentials_cannot_be_persisted_or_echoed(store, payload):
    secret = "synthetic-secret"
    error = assert_error(400, "credential_in_payload", lambda: execute_trigger_request(
        store, "create", "secret-test", definition("secret-test", payload=payload), transport_credentials=(secret,)))
    assert secret not in str(error.detail()) and execute_trigger_request(store, "list")["triggers"] == []
    AgentTriggers(store).create("existing", agent_id="worker", schedule={"kind": "once", "at": "2099-01-01T12:00:00Z"},
                                executor="noop", payload=payload)
    for operation, identifier in [("get", "existing"), ("list", None)]:
        error = assert_error(503, "credential_in_response", lambda operation=operation, identifier=identifier: execute_trigger_request(
            store, operation, identifier, transport_credentials=(secret,)))
        assert secret not in str(error.detail())


@pytest.mark.parametrize("credentials", ["synthetic-secret", (" synthetic-secret ",), ("",), (None,)])
def test_uncanonical_transport_context_is_rejected_before_mutation(store, credentials):
    error = assert_error(503, "invalid_credential_context", lambda: execute_trigger_request(
        store, "create", "secret-test", definition("secret-test"), transport_credentials=credentials))
    assert "synthetic-secret" not in str(error.detail())
    assert execute_trigger_request(store, "list")["triggers"] == []
