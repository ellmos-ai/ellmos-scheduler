# SPDX-License-Identifier: MIT
"""Host-neutral projection of native trigger configuration, with no HTTP or auth imports.

The historical bach.agent-triggers.v1 wire namespace is retained for shared GUI
compatibility. Hosts must authenticate and enforce write authority before calls,
and supply canonical transport credentials for input/output leak prevention.
This module never initializes storage or executes an executor.
"""
from __future__ import annotations

import json
import re
import sqlite3

from .definitions import AgentTriggers, DefinitionConflict
from .executors import executor_names as default_executor_names

SCHEMA = "bach.agent-triggers.v1"

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}\Z")

_CONFIG = {
    "agent_id",
    "schedule",
    "executor",
    "payload",
    "enabled",
    "authorities",
    "lease_seconds",
    "timeout_seconds",
}

_FIELDS = _CONFIG | {"id", "version", "revision", "deleted"}

_SECRET_KEYS = {
    "token",
    "api_key",
    "apikey",
    "password",
    "secret",
    "authorization",
    "access_token",
    "refresh_token",
    "device_token",
    "operator_token",
}


class TriggerProjectionError(ValueError):
    """Bounded wire error; provider exception strings are never exposed."""

    def __init__(self, status, state, reason_code):
        super().__init__(reason_code)
        self.status = status
        self.state = state
        self.reason_code = reason_code

    def detail(self):
        return {"schema": "bach.agent-triggers.error.v1", "state": self.state,
                "reason_code": self.reason_code}


def _error(status, state, reason):
    raise TriggerProjectionError(status, state, reason)



def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        _error(400, "invalid", "invalid_identifier")
    return value


def _version(value, *, create=False):
    if type(value) is not int or (value != 0 if create else value < 1):
        _error(400, "invalid", "invalid_expected_version")
    return value


def _no_credentials(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower().replace("-", "_") in _SECRET_KEYS:
                raise ValueError("credential_field")
            _no_credentials(child)
    elif isinstance(value, list):
        for child in value:
            _no_credentials(child)


def _snapshot(value):
    if not isinstance(value, dict) or not _FIELDS.issubset(value):
        _error(503, "unavailable", "invalid_provider_snapshot")
    if (
        not isinstance(value["id"], str)
        or not _ID.fullmatch(value["id"])
        or not isinstance(value["agent_id"], str)
        or not _ID.fullmatch(value["agent_id"])
        or type(value["version"]) is not int
        or value["version"] < 1
        or type(value["revision"]) is not int
        or value["revision"] < 1
        or type(value["enabled"]) is not bool
        or type(value["deleted"]) is not bool
        or not isinstance(value["schedule"], dict)
        or not isinstance(value["payload"], dict)
        or not isinstance(value["authorities"], list)
        or not isinstance(value["executor"], str)
        or type(value["lease_seconds"]) is not int
        or value["lease_seconds"] <= 0
        or type(value["timeout_seconds"]) is not int
        or value["timeout_seconds"] <= 0
    ):
        _error(503, "unavailable", "invalid_provider_snapshot")
    # Never expose provider-specific fields, exception text, filesystem paths or credentials.
    result = {key: value[key] for key in _FIELDS}
    try:
        _no_credentials(result)
    except (ValueError, TypeError, AttributeError):
        _error(503, "unavailable", "invalid_provider_snapshot")
    return result


def _response(**values):
    return {
        "schema": SCHEMA,
        "provider": "ellmos-scheduler",
        "source": "external_scheduler",
        "state": "available",
        **values,
    }


def _config(value, registered_executors):
    if not isinstance(value, dict) or not value or not set(value).issubset(_CONFIG):
        _error(400, "invalid", "invalid_changes")
    if "agent_id" in value:
        _identifier(value["agent_id"])
    if "enabled" in value and type(value["enabled"]) is not bool:
        _error(400, "invalid", "invalid_enabled")
    if "executor" in value and value["executor"] not in registered_executors:
        _error(400, "invalid", "unknown_executor")
    _no_credentials(value)
    return value


def _execute_trigger_request(store, operation, identifier=None, payload=None, agent_id=None, *, registered_executors=None):
    """Project one authenticated host request against the native store.

    registered_executors is a host-registry name snapshot, never callbacks.
    Creation requires matching identifier and payload.id; writes use native CAS
    plus a separate readback. A missing store/schema remains unavailable.
    """
    try:
        if not isinstance(operation, str) or operation not in {"list", "get", "create", "update", "delete", "deliver"}:
            _error(400, "invalid", "unknown_operation")
        if registered_executors is None:
            registered_executors = default_executor_names()
        if not isinstance(registered_executors, (tuple, list, set, frozenset)) or not all(isinstance(name, str) for name in registered_executors):
            _error(503, "unavailable", "invalid_executor_registry")
        registered_executors = frozenset(registered_executors)
        triggers = AgentTriggers(store)
        if operation == "list":
            if agent_id is not None:
                _identifier(agent_id)
            return _response(
                triggers=[_snapshot(row) for row in triggers.list(agent_id=agent_id)]
            )
        identifier = _identifier(identifier)
        if operation == "get":
            current = _snapshot(triggers.get(identifier))
            if current["id"] != identifier:
                _error(503, "unavailable", "readback_unverified")
            return _response(trigger=current)
        if not isinstance(payload, dict):
            _error(400, "invalid", "invalid_request")
        _no_credentials(payload)
        # Readiness uses the provider's native RO API: a missing store/schema must
        # not be created as a side effect of attempting a write.
        triggers.list()
        expected = _version(
            payload.get("expected_version"), create=operation == "create"
        )
        if operation == "create":
            if payload.get("id") != identifier:
                _error(400, "invalid", "identifier_mismatch")
            if not {
                "id",
                "expected_version",
                "agent_id",
                "schedule",
                "executor",
            }.issubset(payload):
                _error(400, "invalid", "missing_fields")
            if not set(payload).issubset(_CONFIG | {"id", "expected_version"}):
                _error(400, "invalid", "unknown_fields")
            config = _config(
                {key: val for key, val in payload.items() if key in _CONFIG}, registered_executors
            )
            mutation = triggers.create(identifier, **config)
        elif operation == "update":
            if set(payload) != {"expected_version", "changes"}:
                _error(400, "invalid", "unknown_fields")
            mutation = triggers.update(
                identifier,
                expected_version=expected,
                changes=_config(payload["changes"], registered_executors),
            )
        elif operation == "delete":
            if set(payload) != {"expected_version"}:
                _error(400, "invalid", "unknown_fields")
            mutation = triggers.delete(identifier, expected_version=expected)
        else:
            required = {"expected_version", "event_id", "event_type", "source"}
            if not required.issubset(payload) or not set(payload).issubset(
                required | {"lineage"}
            ):
                _error(400, "invalid", "invalid_delivery")
            before = _snapshot(triggers.get(identifier))
            delivery = triggers.deliver(identifier, **payload)
            after = _snapshot(triggers.get(identifier))
            if before != after or after["version"] != expected:
                _error(503, "unavailable", "readback_unverified")
            if (
                not isinstance(delivery, dict)
                or delivery.get("state") != "materialized"
                or type(delivery.get("duplicate")) is not bool
                or not isinstance(delivery.get("job_id"), str)
            ):
                _error(503, "unavailable", "delivery_unverified")
            materialized = next(
                (
                    row
                    for row in store.list_jobs()
                    if row.get("id") == delivery["job_id"]
                ),
                None,
            )
            try:
                job_payload = json.loads(materialized["payload_json"])
                provenance = job_payload["_scheduler_event"]
                definition = job_payload["_agent_trigger"]
                verified = (
                    definition["id"] == identifier
                    and provenance["trigger_id"] == identifier
                    and all(
                        provenance[key] == payload[key]
                        for key in ("event_id", "event_type", "source")
                    )
                    and provenance["lineage"]
                    == [*(payload.get("lineage") or []), identifier]
                    and (
                        delivery["duplicate"]
                        or definition["revision"] == after["revision"]
                    )
                )
            except (KeyError, TypeError, ValueError):
                verified = False
            if not verified:
                _error(503, "unavailable", "delivery_unverified")
            return _response(
                trigger=after,
                delivery={
                    key: delivery[key] for key in ("job_id", "duplicate", "state")
                },
                ack={
                    "configuration_saved": False,
                    "readback_verified": True,
                    "worker_started": False,
                },
            )
        confirmed = _snapshot(triggers.get(identifier))
        expected_next = 1 if operation == "create" else expected + 1
        if (
            confirmed["id"] != identifier
            or _snapshot(mutation) != confirmed
            or confirmed["version"] != expected_next
            or (operation == "delete" and not confirmed["deleted"])
        ):
            _error(503, "unavailable", "readback_unverified")
        return _response(
            trigger=confirmed,
            ack={
                "configuration_saved": True,
                "readback_verified": True,
                "worker_started": False,
            },
        )
    except TriggerProjectionError:
        raise
    except Exception as exc:  # Provider exceptions may contain private data.
        if isinstance(exc, DefinitionConflict):
            _error(409, "conflict", "version_conflict")
        if isinstance(exc, KeyError):
            _error(404, "not_found", "trigger_not_found")
        if isinstance(exc, ValueError):
            _error(400, "invalid", "invalid_request")
        if isinstance(exc, sqlite3.Error):
            _error(503, "unavailable", "schema_unavailable")
        _error(503, "unavailable", "provider_unavailable")


def _contains_credential(value, credentials):
    if isinstance(value, str):
        return any(credential in value for credential in credentials)
    if isinstance(value, dict):
        return any(_contains_credential(key, credentials) or _contains_credential(child, credentials)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_credential(child, credentials) for child in value)
    return False


def execute_trigger_request(store, operation, identifier=None, payload=None, agent_id=None, *,
                            registered_executors=None, transport_credentials=()):
    """Shared host projection; authentication/write authority remain host responsibilities.

    HTTP hosts supply the exact canonical values accepted by their authenticator.
    Noncanonical values fail closed rather than repeating a whitespace bypass.
    No credential is saved, returned, or included in an error's detail.
    """
    if not isinstance(transport_credentials, (tuple, list)) or not all(
        isinstance(value, str) and value and value == value.strip() for value in transport_credentials
    ):
        _error(503, "unavailable", "invalid_credential_context")
    credentials = tuple(dict.fromkeys(transport_credentials))
    if _contains_credential(payload, credentials):
        _error(400, "invalid", "credential_in_payload")
    result = _execute_trigger_request(store, operation, identifier, payload, agent_id,
                                     registered_executors=registered_executors)
    if _contains_credential(result, credentials):
        _error(503, "unavailable", "credential_in_response")
    return result
