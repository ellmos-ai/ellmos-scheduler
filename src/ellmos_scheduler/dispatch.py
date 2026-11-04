"""Persistent dispatch correlation; worker/Task authority stays with the consumer.

No credentials, executor effects, process inspection or TaskDB access live here.
The consumer must verify native process/task evidence before recording it.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .context import ExecutionContext
from .events import canonical, stamp, token

DISPATCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS dispatch_occurrences (
 occurrence_id TEXT PRIMARY KEY, version INTEGER NOT NULL,
 job_id TEXT NOT NULL, scheduled_for TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
 target_json TEXT NOT NULL, target_sha256 TEXT NOT NULL,
 scheduler_run_id TEXT NOT NULL REFERENCES runs(run_id),
 scheduler_attempt INTEGER NOT NULL, claimed_by TEXT NOT NULL,
 state TEXT NOT NULL, controller_json TEXT NOT NULL DEFAULT '{}',
 observation_json TEXT NOT NULL DEFAULT '{}', terminal_json TEXT NOT NULL DEFAULT '{}',
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dispatch_history (
 occurrence_id TEXT NOT NULL REFERENCES dispatch_occurrences(occurrence_id),
 version INTEGER NOT NULL, event TEXT NOT NULL, snapshot_json TEXT NOT NULL,
 PRIMARY KEY(occurrence_id, version)
);
CREATE TABLE IF NOT EXISTS dispatch_task_bindings (
 occurrence_id TEXT NOT NULL REFERENCES dispatch_occurrences(occurrence_id),
 generation TEXT NOT NULL, task_id INTEGER NOT NULL, task_version TEXT NOT NULL,
 fence INTEGER NOT NULL, holder TEXT NOT NULL,
 PRIMARY KEY(occurrence_id, task_id, fence)
);
"""


class DispatchConflict(ValueError):
    """A stale occurrence CAS, owner, generation or state cannot authorize an effect."""


@dataclass(frozen=True)
class RecoveryEvidence:
    """Consumer-verified facts, not evidence derived from an RPC observation timeout."""

    controller_instance: str
    generation: str
    pid: int
    process_create_time: float
    controller_gone: bool
    leases_clear: bool
    traces_closed: bool
    native_admission_absent: bool = False


@dataclass(frozen=True)
class AcceptedTaskResult:
    """Consumer-verified metadata only; no result text or lease capability."""

    task_id: int
    task_version: str
    fence: int
    result_id: int
    result_sha256: str
    status_revision: int
    accepted_status_event_id: int
    acceptance_event_id: int


def _integer(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f"positive {label} required")
    return value


def _hex(value, length, label):
    if not isinstance(value, str) or len(value) != length or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"invalid {label}")
    return value


def _instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timezone-aware instant required")
    return result.astimezone(timezone.utc)


class DispatchReceipts:
    """Native occurrence CAS and durable admission intent; never a second scheduler."""

    def __init__(self, store):
        self.store = store

    @staticmethod
    def _snapshot(row):
        return {
            "schema": "ellmos.dispatch-receipt.v1",
            "occurrence_id": row["occurrence_id"],
            "version": row["version"],
            "job_id": row["job_id"],
            "scheduled_for": row["scheduled_for"],
            "request_id": row["request_id"],
            "target": json.loads(row["target_json"]),
            "target_sha256": row["target_sha256"],
            "scheduler_run_id": row["scheduler_run_id"],
            "scheduler_attempt": row["scheduler_attempt"],
            "claimed_by": row["claimed_by"],
            "state": row["state"],
            "controller": json.loads(row["controller_json"]),
            "observation": json.loads(row["observation_json"]),
            "terminal": json.loads(row["terminal_json"]),
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _row(conn, occurrence_id, expected_version=None):
        _hex(occurrence_id, 64, "occurrence_id")
        row = conn.execute("SELECT * FROM dispatch_occurrences WHERE occurrence_id=?", (occurrence_id,)).fetchone()
        if row is None:
            raise KeyError("dispatch occurrence missing")
        if expected_version is not None:
            _integer(expected_version, "expected_version")
            if row["version"] != expected_version:
                raise DispatchConflict("dispatch_version_conflict")
        return row

    @classmethod
    def _record(cls, conn, row, event):
        conn.execute(
            "INSERT INTO dispatch_history VALUES (?,?,?,?)",
            (row["occurrence_id"], row["version"], event, canonical(cls._snapshot(row))),
        )

    @classmethod
    def _save(cls, conn, row, event, when, **changes):
        allowed = {
            "scheduler_run_id",
            "scheduler_attempt",
            "claimed_by",
            "state",
            "controller_json",
            "observation_json",
            "terminal_json",
        }
        if not changes or not set(changes).issubset(allowed):
            raise ValueError("invalid internal receipt transition")
        assignments = ",".join(f"{key}=?" for key in changes)
        changed = conn.execute(
            f"UPDATE dispatch_occurrences SET {assignments},version=version+1,updated_at=? "
            "WHERE occurrence_id=? AND version=?",
            (*changes.values(), when, row["occurrence_id"], row["version"]),
        )
        if changed.rowcount != 1:
            raise DispatchConflict("dispatch_version_conflict")
        updated = cls._row(conn, row["occurrence_id"])
        cls._record(conn, updated, event)
        return cls._snapshot(updated)

    @staticmethod
    def _context(conn, context, when):
        if not isinstance(context, ExecutionContext):
            raise ValueError("native execution context required")
        run = conn.execute("SELECT * FROM runs WHERE run_id=?", (context.run_id,)).fetchone()
        if run is None or run["status"] != "running" or _instant(run["lease_expires_at"]) < _instant(when):
            raise DispatchConflict("scheduler_claim_not_live")
        if type(context.attempt) is not int:
            raise DispatchConflict("scheduler_context_mismatch")
        for field in ("job_id", "run_id", "attempt", "claimed_by"):
            if run[field] != getattr(context, field):
                raise DispatchConflict("scheduler_context_mismatch")
        for field in ("scheduled_for", "lease_expires_at", "started_at"):
            if stamp(_instant(run[field])) != getattr(context, field):
                raise DispatchConflict("scheduler_context_mismatch")
        return run

    @staticmethod
    def _live_scheduler_owner(conn, row, when):
        run = conn.execute("SELECT * FROM runs WHERE run_id=?", (row["scheduler_run_id"],)).fetchone()
        if (
            run is None
            or run["status"] != "running"
            or run["claimed_by"] != row["claimed_by"]
            or _instant(run["lease_expires_at"]) < _instant(when)
        ):
            raise DispatchConflict("scheduler_claim_not_live")

    @classmethod
    def _owner(cls, conn, occurrence_id, expected_version, controller_instance, generation):
        row = cls._row(conn, occurrence_id, expected_version)
        controller = json.loads(row["controller_json"])
        if controller.get("service_instance") != _hex(controller_instance, 32, "controller_instance") or controller.get(
            "generation"
        ) != _hex(generation, 32, "generation"):
            raise DispatchConflict("dispatch_generation_conflict")
        return row, controller

    def get(self, occurrence_id):
        with self.store.read_connection() as conn:
            return self._snapshot(self._row(conn, occurrence_id))

    def history(self, occurrence_id):
        _hex(occurrence_id, 64, "occurrence_id")
        with self.store.read_connection() as conn:
            return [
                json.loads(row[0])
                for row in conn.execute(
                    "SELECT snapshot_json FROM dispatch_history WHERE occurrence_id=? ORDER BY version",
                    (occurrence_id,),
                )
            ]

    def pending(self):
        with self.store.read_connection() as conn:
            return [
                self._snapshot(row)
                for row in conn.execute(
                    "SELECT * FROM dispatch_occurrences WHERE state!='terminal' ORDER BY updated_at,occurrence_id"
                )
            ]

    def reserve(self, context, *, agent_id, configuration_version, task_id=None, task_version=None, now=None):
        token(agent_id, "agent_id")
        _hex(configuration_version, 64, "configuration_version")
        if (task_id is None) != (task_version is None):
            raise ValueError("task identity and version must be supplied together")
        if task_id is not None:
            _integer(task_id, "task_id")
            _hex(task_version, 64, "task_version")
        target = {
            "agent_id": agent_id,
            "configuration_version": configuration_version,
            "task_id": task_id,
            "task_version": task_version,
        }
        target_json = canonical(target)
        digest = hashlib.sha256(target_json.encode("utf-8")).hexdigest()
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            when = stamp(now)
            self._context(conn, context, when)
            existing = conn.execute(
                "SELECT * FROM dispatch_occurrences WHERE occurrence_id=?", (context.occurrence_id,)
            ).fetchone()
            if existing is not None:
                if existing["target_sha256"] != digest:
                    raise DispatchConflict("dispatch_target_conflict")
                if existing["state"] == "terminal" or existing["scheduler_run_id"] == context.run_id:
                    return self._snapshot(existing)
                if context.attempt <= existing["scheduler_attempt"]:
                    raise DispatchConflict("scheduler_attempt_conflict")
                return self._save(
                    conn,
                    existing,
                    "claim_recovered",
                    when,
                    scheduler_run_id=context.run_id,
                    scheduler_attempt=context.attempt,
                    claimed_by=context.claimed_by,
                )
            conn.execute(
                "INSERT INTO dispatch_occurrences(occurrence_id,version,job_id,scheduled_for,request_id,target_json,"
                "target_sha256,scheduler_run_id,scheduler_attempt,claimed_by,state,updated_at) "
                "VALUES (?,1,?,?,?,?,?,?,?,?,'prepared',?)",
                (
                    context.occurrence_id,
                    context.job_id,
                    context.scheduled_for,
                    context.occurrence_id[:32],
                    target_json,
                    digest,
                    context.run_id,
                    context.attempt,
                    context.claimed_by,
                    when,
                ),
            )
            row = self._row(conn, context.occurrence_id)
            self._record(conn, row, "prepared")
            return self._snapshot(row)

    def prepare(self, context, *, expected_version, controller_instance, now=None):
        """Persist send intent before RPC; the intent alone proves no start outcome."""
        instance = _hex(controller_instance, 32, "controller_instance")
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            when = stamp(now)
            self._context(conn, context, when)
            row = self._row(conn, context.occurrence_id, expected_version)
            if row["scheduler_run_id"] != context.run_id or row["state"] not in {"prepared", "start_unknown"}:
                raise DispatchConflict("dispatch_not_preparable")
            return self._save(
                conn,
                row,
                "send_intent",
                when,
                state="start_unknown",
                controller_json=canonical({"service_instance": instance}),
            )

    def claim_admission(
        self, occurrence_id, *, expected_version, controller_instance, pid, process_create_time, host, now=None
    ):
        """Only this CAS winner may continue into the consumer's native admission."""
        _integer(pid, "pid")
        if (
            type(process_create_time) not in (int, float)
            or not math.isfinite(process_create_time)
            or process_create_time <= 0
        ):
            raise ValueError("process creation time required")
        token(host, "host")
        instance = _hex(controller_instance, 32, "controller_instance")
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            when = stamp(now)
            row = self._row(conn, occurrence_id, expected_version)
            if (
                row["state"] != "start_unknown"
                or json.loads(row["controller_json"]).get("service_instance") != instance
            ):
                raise DispatchConflict("dispatch_admission_conflict")
            run = conn.execute("SELECT * FROM runs WHERE run_id=?", (row["scheduler_run_id"],)).fetchone()
            if (
                run is None
                or run["status"] != "running"
                or run["claimed_by"] != row["claimed_by"]
                or _instant(run["lease_expires_at"]) < _instant(when)
            ):
                raise DispatchConflict("scheduler_claim_not_live")
            generation = uuid.uuid4().hex
            controller = {
                "service_instance": instance,
                "pid": pid,
                "process_create_time": process_create_time,
                "host": host,
                "generation": generation,
                "physical_worker_id": "worker-" + generation,
                "lease_worker_id": "worker-" + generation + "@" + host,
            }
            return self._save(
                conn, row, "admission_reserved", when, state="admission_reserved", controller_json=canonical(controller)
            )

    def launch_intent(self, occurrence_id, *, expected_version, controller_instance, generation, now=None):
        """Must commit after native admission and BEFORE Thread.start/provider effects."""
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row, _ = self._owner(conn, occurrence_id, expected_version, controller_instance, generation)
            if row["state"] != "admission_reserved":
                raise DispatchConflict("dispatch_not_launchable")
            self._live_scheduler_owner(conn, row, stamp(now))
            return self._save(conn, row, "launch_intent", stamp(now), state="launch_intent")

    def observe(
        self,
        occurrence_id,
        *,
        expected_version,
        controller_instance,
        generation,
        worker_state,
        worker_thread_started,
        terminal,
        now=None,
    ):
        if (
            worker_state not in {"starting", "running", "stopping", "finishing", "terminal", "unconfirmed"}
            or type(terminal) is not bool
            or terminal != (worker_state == "terminal")
            or (worker_thread_started is not None and type(worker_thread_started) is not bool)
        ):
            raise ValueError("invalid native worker observation")
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row, _ = self._owner(conn, occurrence_id, expected_version, controller_instance, generation)
            if row["state"] not in {"launch_intent", "observed"}:
                raise DispatchConflict("dispatch_not_observable")
            prior = json.loads(row["observation_json"])
            if prior.get("worker_thread_started") is True and worker_thread_started is not True:
                raise DispatchConflict("dispatch_start_evidence_conflict")
            if prior.get("terminal") is True and not terminal:
                raise DispatchConflict("dispatch_terminal_evidence_conflict")
            observation = {
                "worker_state": worker_state,
                "worker_thread_started": worker_thread_started,
                "terminal": terminal,
            }
            return self._save(
                conn,
                row,
                "observed",
                stamp(now),
                state="observed" if worker_thread_started is True else row["state"],
                observation_json=canonical(observation),
            )

    def bind_task(
        self,
        occurrence_id,
        *,
        expected_version,
        controller_instance,
        generation,
        task_id,
        task_version,
        fence,
        holder,
        now=None,
    ):
        _integer(task_id, "task_id")
        _integer(fence, "fence")
        _hex(task_version, 64, "task_version")
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row, controller = self._owner(conn, occurrence_id, expected_version, controller_instance, generation)
            if row["state"] not in {"launch_intent", "observed"} or holder != controller["lease_worker_id"]:
                raise DispatchConflict("dispatch_task_owner_conflict")
            target = json.loads(row["target_json"])
            if target["task_id"] is not None and (
                target["task_id"] != task_id or target["task_version"] != task_version
            ):
                raise DispatchConflict("dispatch_task_target_conflict")
            bindings = conn.execute(
                "SELECT * FROM dispatch_task_bindings WHERE occurrence_id=?", (occurrence_id,)
            ).fetchall()
            for existing in bindings:
                same = (
                    existing["generation"],
                    existing["task_id"],
                    existing["task_version"],
                    existing["fence"],
                    existing["holder"],
                ) == (generation, task_id, task_version, fence, holder)
                if same:
                    return self._snapshot(row)
                if target["task_id"] is not None or (existing["task_id"], existing["fence"]) == (task_id, fence):
                    raise DispatchConflict("dispatch_task_binding_conflict")
            conn.execute(
                "INSERT INTO dispatch_task_bindings VALUES (?,?,?,?,?,?)",
                (occurrence_id, generation, task_id, task_version, fence, holder),
            )
            return self._save(conn, row, "task_bound", stamp(now), state=row["state"])

    def task_bindings(self, occurrence_id):
        _hex(occurrence_id, 64, "occurrence_id")
        with self.store.read_connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM dispatch_task_bindings WHERE occurrence_id=? ORDER BY task_id,fence",
                    (occurrence_id,),
                )
            ]

    @staticmethod
    def _recovery(evidence, controller, *, unlaunched=False):
        if (
            not isinstance(evidence, RecoveryEvidence)
            or any(
                type(getattr(evidence, field)) is not bool
                for field in ("controller_gone", "leases_clear", "traces_closed", "native_admission_absent")
            )
            or not evidence.controller_gone
            or not evidence.leases_clear
            or not evidence.traces_closed
            or (unlaunched and not evidence.native_admission_absent)
        ):
            raise DispatchConflict("dispatch_recovery_unconfirmed")
        if (
            evidence.controller_instance != controller.get("service_instance")
            or evidence.generation != controller.get("generation")
            or type(evidence.pid) is not int
            or evidence.pid != controller.get("pid")
            or type(evidence.process_create_time) not in (int, float)
            or evidence.process_create_time != controller.get("process_create_time")
        ):
            raise DispatchConflict("dispatch_recovery_identity_conflict")

    def recover_unlaunched(self, context, *, expected_version, evidence, now=None):
        """Only positive absence proof BEFORE launch intent permits a first launch retry."""
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            when = stamp(now)
            self._context(conn, context, when)
            row = self._row(conn, context.occurrence_id, expected_version)
            self._recovery(evidence, json.loads(row["controller_json"]), unlaunched=True)
            if row["scheduler_run_id"] != context.run_id or row["state"] != "admission_reserved":
                raise DispatchConflict("dispatch_launch_may_have_happened")
            return self._save(
                conn, row, "unlaunched_recovered", when, state="prepared", controller_json="{}", observation_json="{}"
            )

    def complete_accepted(
        self,
        occurrence_id,
        *,
        expected_version,
        controller_instance,
        generation,
        task_id,
        task_version,
        fence,
        result_id,
        result_sha256,
        status_revision,
        accepted_status_event_id,
        acceptance_event_id,
        now=None,
    ):
        """Single-result compatibility wrapper; cannot omit other bound tasks."""
        result = AcceptedTaskResult(
            task_id,
            task_version,
            fence,
            result_id,
            result_sha256,
            status_revision,
            accepted_status_event_id,
            acceptance_event_id,
        )
        return self.complete_accepted_results(
            occurrence_id,
            expected_version=expected_version,
            controller_instance=controller_instance,
            generation=generation,
            results=(result,),
            now=now,
        )

    def complete_accepted_results(
        self,
        occurrence_id,
        *,
        expected_version,
        controller_instance,
        generation,
        results,
        now=None,
    ):
        """Require canonical accepted metadata for exactly every bound task/fence."""
        if not isinstance(results, (tuple, list)) or not results:
            raise ValueError("accepted task result collection required")
        checked = {}
        for result in results:
            if type(result) is not AcceptedTaskResult:
                raise ValueError("typed accepted task result required")
            for label in ("task_id", "fence", "result_id", "status_revision", "acceptance_event_id"):
                _integer(getattr(result, label), label)
            _hex(result.task_version, 64, "task_version")
            _hex(result.result_sha256, 64, "result_sha256")
            if (
                type(result.accepted_status_event_id) is not int
                or result.accepted_status_event_id != result.status_revision
            ):
                raise ValueError("current accepted status revision required")
            key = (result.task_id, result.fence)
            if key in checked:
                raise ValueError("duplicate accepted task binding")
            checked[key] = result
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row, _ = self._owner(conn, occurrence_id, expected_version, controller_instance, generation)
            observation = json.loads(row["observation_json"])
            if (
                row["state"] != "observed"
                or observation.get("terminal") is not True
                or observation.get("worker_state") != "terminal"
                or observation.get("worker_thread_started") is not True
            ):
                raise DispatchConflict("dispatch_worker_end_unconfirmed")
            bindings = conn.execute(
                "SELECT * FROM dispatch_task_bindings WHERE occurrence_id=? ORDER BY task_id,fence", (occurrence_id,)
            ).fetchall()
            if not bindings or {(r["task_id"], r["fence"]) for r in bindings} != set(checked):
                raise DispatchConflict("dispatch_result_bindings_incomplete")
            accepted = []
            for binding in bindings:
                if binding["generation"] != generation:
                    raise DispatchConflict("dispatch_result_generation_conflict")
                result = checked[(binding["task_id"], binding["fence"])]
                accepted.append(
                    {
                        "generation": generation,
                        "task_id": result.task_id,
                        "claimed_task_version": binding["task_version"],
                        "task_version": result.task_version,
                        "fence": result.fence,
                        "result_id": result.result_id,
                        "result_sha256": result.result_sha256,
                        "status_revision": result.status_revision,
                        "accepted_status_event_id": result.accepted_status_event_id,
                        "acceptance_event_id": result.acceptance_event_id,
                    }
                )
            terminal = {"outcome": "succeeded", "accepted": True, "results": accepted}
            if len(accepted) == 1:
                terminal.update(accepted[0])
            return self._save(
                conn, row, "accepted_result", stamp(now), state="terminal", terminal_json=canonical(terminal)
            )

    def complete_lost(self, occurrence_id, *, expected_version, controller_instance, generation, evidence, now=None):
        """Confirmed controller loss is failure, never proof that no thread ever started."""
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row, controller = self._owner(conn, occurrence_id, expected_version, controller_instance, generation)
            self._recovery(evidence, controller)
            if row["state"] not in {"admission_reserved", "launch_intent", "observed"}:
                raise DispatchConflict("dispatch_not_completable")
            terminal = {
                "outcome": "failed",
                "reason_code": "controller_lost",
                "accepted": False,
                "controller_gone": True,
                "leases_clear": True,
                "traces_closed": True,
            }
            return self._save(
                conn, row, "controller_lost", stamp(now), state="terminal", terminal_json=canonical(terminal)
            )

    def complete_failure(
        self, occurrence_id, *, expected_version, controller_instance, generation, reason_code, now=None
    ):
        """Only verified physical end permits bounded normal failure classification."""
        if reason_code not in {
            "task_rejected",
            "task_failed",
            "no_accepted_result",
            "cancelled",
            "review_not_accepted",
        }:
            raise ValueError("invalid dispatch failure reason")
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row, _ = self._owner(conn, occurrence_id, expected_version, controller_instance, generation)
            observation = json.loads(row["observation_json"])
            if (
                row["state"] != "observed"
                or observation.get("terminal") is not True
                or observation.get("worker_state") != "terminal"
                or observation.get("worker_thread_started") is not True
            ):
                raise DispatchConflict("dispatch_worker_end_unconfirmed")
            terminal = {"outcome": "failed", "accepted": False, "reason_code": reason_code}
            return self._save(
                conn, row, "worker_failed", stamp(now), state="terminal", terminal_json=canonical(terminal)
            )

    def complete_rejected(
        self,
        occurrence_id,
        *,
        expected_version,
        controller_instance,
        generation,
        reason_code,
        native_admission_rejected,
        worker_thread_started,
        leases_clear,
        traces_closed,
        now=None,
    ):
        """Record positive native rejection before launch; never infer rejection from timeout."""
        if reason_code not in {"admission_rejected", "task_unavailable", "scope_denied", "configuration_conflict"}:
            raise ValueError("invalid admission rejection reason")
        if (
            native_admission_rejected is not True
            or worker_thread_started is not False
            or leases_clear is not True
            or traces_closed is not True
        ):
            raise DispatchConflict("dispatch_rejection_unconfirmed")
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row, _ = self._owner(conn, occurrence_id, expected_version, controller_instance, generation)
            if row["state"] != "admission_reserved":
                raise DispatchConflict("dispatch_launch_may_have_happened")
            terminal = {
                "outcome": "failed",
                "accepted": False,
                "reason_code": reason_code,
                "native_admission_rejected": True,
                "worker_thread_started": False,
                "leases_clear": True,
                "traces_closed": True,
            }
            return self._save(
                conn, row, "admission_rejected", stamp(now), state="terminal", terminal_json=canonical(terminal)
            )
