"""Versioned shared agent-trigger definitions, using only native scheduler jobs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from .events import canonical, stamp, token
from .schedules import next_after, once_at

DEFINITION_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_trigger_definitions (
 id TEXT PRIMARY KEY, version INTEGER NOT NULL, revision INTEGER NOT NULL,
 config_json TEXT NOT NULL, enabled INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_trigger_history (
 definition_id TEXT NOT NULL REFERENCES agent_trigger_definitions(id), version INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL, PRIMARY KEY(definition_id,version)
);
CREATE TABLE IF NOT EXISTS agent_trigger_jobs (
 job_id TEXT PRIMARY KEY REFERENCES jobs(id), definition_id TEXT NOT NULL
 REFERENCES agent_trigger_definitions(id), revision INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_trigger_deliveries (
 definition_id TEXT NOT NULL REFERENCES agent_trigger_definitions(id), event_id TEXT NOT NULL,
 event_json TEXT NOT NULL, job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
 PRIMARY KEY(definition_id,event_id)
);
"""


class DefinitionConflict(ValueError):
    """A stale version, deleted definition, or reused event ID cannot mutate state."""


def consume_terminal_once(conn: Any, run_id: str) -> None:
    """Consume the stable appointment atomically with its successful terminal CAS."""
    finished = conn.execute(
        "SELECT j.schedule_json,j.payload_json,m.definition_id FROM runs r "
        "JOIN jobs j ON j.id=r.job_id JOIN agent_trigger_jobs m ON m.job_id=j.id "
        "WHERE r.run_id=? AND r.status IN ('succeeded','failed','timed_out')",
        (run_id,),
    ).fetchone()
    if finished is None:
        return
    config = json.loads(finished["schedule_json"])
    if (
        config.get("kind") != "once"
        or json.loads(finished["payload_json"]).get("_agent_trigger", {}).get("kind") != "once"
    ):
        return
    instant = once_at(config)
    candidates = conn.execute(
        "SELECT j.id,j.schedule_json,j.payload_json FROM jobs j "
        "JOIN agent_trigger_jobs m ON m.job_id=j.id WHERE m.definition_id=?",
        (finished["definition_id"],),
    ).fetchall()
    for candidate in candidates:
        schedule = json.loads(candidate["schedule_json"])
        if (
            schedule.get("kind") == "once"
            and json.loads(candidate["payload_json"]).get("_agent_trigger", {}).get("kind") == "once"
            and once_at(schedule) == instant
        ):
            conn.execute("UPDATE jobs SET exhausted=1 WHERE id=?", (candidate["id"],))


def definition_job_allowed(conn: Any, job_id: str, *, now: str, run_id: str | None = None) -> bool:
    row = conn.execute(
        """SELECT d.*,m.revision AS job_revision FROM agent_trigger_jobs m
        JOIN agent_trigger_definitions d ON d.id=m.definition_id WHERE m.job_id=?""",
        (job_id,),
    ).fetchone()
    if row is None:
        return True
    if row["deleted"] or not row["enabled"] or row["revision"] != row["job_revision"]:
        return False
    if any(
        r["paused"]
        for r in conn.execute("SELECT paused FROM controls WHERE scope IN ('global', ?)", ("definition:" + row["id"],))
    ):
        return False
    active = conn.execute(
        """SELECT 1 FROM runs r JOIN agent_trigger_jobs m ON m.job_id=r.job_id
        WHERE m.definition_id=? AND r.status IN ('claimed','running')
        AND scheduler_utc(r.lease_expires_at)>=scheduler_utc(?)
        AND (? IS NULL OR r.run_id!=?) LIMIT 1""",
        (row["id"], now, run_id, run_id),
    ).fetchone()
    return active is None


class AgentTriggers:
    """Shared CAS CRUD. Reads do not create a database or initialize schema."""

    def __init__(self, store: Any):
        self.store = store

    @staticmethod
    def _snapshot(row: Any) -> dict:
        return {
            "id": row["id"],
            "version": row["version"],
            "revision": row["revision"],
            "enabled": bool(row["enabled"]),
            "deleted": bool(row["deleted"]),
            **json.loads(row["config_json"]),
        }

    def _config(self, config: dict, now: str) -> dict:
        config = dict(config)
        token(config.get("agent_id"), "agent_id")
        token(config.get("executor"), "executor")
        payload = config.get("payload")
        if not isinstance(payload, dict) or any(k in payload for k in ("_agent_trigger", "_scheduler_event")):
            raise ValueError("payload must be an object without scheduler-reserved keys")
        if "agent_id" in payload and payload["agent_id"] != config["agent_id"]:
            raise ValueError("payload agent_id conflicts with definition")
        schedule = config.get("schedule")
        if not isinstance(schedule, dict):
            raise ValueError("schedule object required")
        if schedule.get("kind") == "event":
            if set(schedule) != {"kind", "event_type"}:
                raise ValueError("event schedule requires only kind and event_type")
            token(schedule["event_type"], "event_type")
        elif schedule.get("kind") == "once":
            once_at(schedule)
        else:
            next_after(schedule, datetime.fromisoformat(now.replace("Z", "+00:00")))
        for key in ("lease_seconds", "timeout_seconds"):
            if type(config.get(key)) is not int or config[key] <= 0:
                raise ValueError("lease/timeout must be positive integers")
        config["authorities"] = self.store.authority_registry.validate_specs(config.get("authorities"))
        canonical(config)
        return config

    @staticmethod
    def _record(conn: Any, row: Any) -> None:
        conn.execute(
            "INSERT INTO agent_trigger_history VALUES (?,?,?)",
            (row["id"], row["version"], canonical(AgentTriggers._snapshot(row))),
        )

    def _job(self, conn: Any, row: Any, *, now: str, event: dict | None = None, exhausted: bool = False) -> str:
        config = json.loads(row["config_json"])
        material = [row["id"], row["revision"], event["event_id"] if event else "schedule"]
        job_id = "trigger-" + hashlib.sha256(canonical(material).encode("utf-8")).hexdigest()
        schedule = {"kind": "once", "at": now} if event else config["schedule"]
        instant = (
            once_at(schedule)
            if schedule["kind"] == "once"
            else next_after(schedule, datetime.fromisoformat(now.replace("Z", "+00:00")))
        )
        due = stamp(instant)
        payload = {
            **config["payload"],
            "agent_id": config["agent_id"],
            "_agent_trigger": {"id": row["id"], "revision": row["revision"], "kind": config["schedule"]["kind"]},
        }
        if event:
            payload["_scheduler_event"] = event
        conn.execute(
            """INSERT INTO jobs(id,schedule_json,executor,payload_json,enabled,next_due_at,
            lease_seconds,timeout_seconds,authorities_json,created_at,updated_at,exhausted)
            VALUES (?,?,?,?,1,?,?,?,?,?,?,?)""",
            (
                job_id,
                canonical(schedule),
                config["executor"],
                canonical(payload),
                due,
                config["lease_seconds"],
                config["timeout_seconds"],
                canonical(config["authorities"]),
                now,
                now,
                int(exhausted),
            ),
        )
        conn.execute("INSERT INTO agent_trigger_jobs VALUES (?,?,?)", (job_id, row["id"], row["revision"]))
        return job_id

    @staticmethod
    def _once_consumed(conn: Any, definition_id: str, schedule: dict) -> bool:
        if schedule.get("kind") != "once":
            return False
        instant = once_at(schedule)
        rows = conn.execute(
            "SELECT j.schedule_json,j.payload_json FROM jobs j JOIN agent_trigger_jobs m ON m.job_id=j.id "
            "WHERE m.definition_id=? AND EXISTS (SELECT 1 FROM runs r WHERE r.job_id=j.id "
            "AND r.status IN ('succeeded','failed','timed_out'))",
            (definition_id,),
        ).fetchall()
        return any(
            json.loads(row["payload_json"]).get("_agent_trigger", {}).get("kind") == "once"
            and (old := json.loads(row["schedule_json"])).get("kind") == "once"
            and once_at(old) == instant
            for row in rows
        )

    def create(
        self,
        definition_id: str,
        *,
        agent_id: str,
        schedule: dict,
        executor: str,
        payload: dict | None = None,
        enabled: bool = False,
        authorities: list | None = None,
        lease_seconds: int = 900,
        timeout_seconds: int = 600,
        now: datetime | None = None,
    ) -> dict:
        token(definition_id, "definition_id")
        if type(enabled) is not bool:
            raise ValueError("enabled must be boolean")
        when = stamp(now)
        config = self._config(
            {
                "agent_id": agent_id,
                "schedule": schedule,
                "executor": executor,
                "payload": {} if payload is None else payload,
                "authorities": authorities,
                "lease_seconds": lease_seconds,
                "timeout_seconds": timeout_seconds,
            },
            when,
        )
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM agent_trigger_definitions WHERE id=?", (definition_id,)).fetchone():
                raise DefinitionConflict("definition ID already used, including tombstones")
            conn.execute(
                "INSERT INTO agent_trigger_definitions VALUES (?,1,1,?,?,0,?)",
                (definition_id, canonical(config), int(enabled), when),
            )
            row = conn.execute("SELECT * FROM agent_trigger_definitions WHERE id=?", (definition_id,)).fetchone()
            self._record(conn, row)
            if schedule["kind"] != "event":
                self._job(conn, row, now=when)
            return self._snapshot(row)

    def get(self, definition_id: str) -> dict:
        token(definition_id, "definition_id")
        with self.store.read_connection() as conn:
            row = conn.execute("SELECT * FROM agent_trigger_definitions WHERE id=?", (definition_id,)).fetchone()
        if row is None:
            raise KeyError(definition_id)
        return self._snapshot(row)

    def list(self, *, agent_id: str | None = None, include_deleted: bool = False) -> list[dict]:
        if type(include_deleted) is not bool:
            raise ValueError("include_deleted must be boolean")
        if agent_id is not None:
            token(agent_id, "agent_id")
        with self.store.read_connection() as conn:
            rows = conn.execute("SELECT * FROM agent_trigger_definitions ORDER BY id").fetchall()
        return [
            self._snapshot(r)
            for r in rows
            if (include_deleted or not r["deleted"])
            and (agent_id is None or json.loads(r["config_json"])["agent_id"] == agent_id)
        ]

    @staticmethod
    def _current(conn: Any, definition_id: str, expected_version: int) -> Any:
        token(definition_id, "definition_id")
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("positive expected_version required")
        row = conn.execute("SELECT * FROM agent_trigger_definitions WHERE id=?", (definition_id,)).fetchone()
        if row is None or row["deleted"] or row["version"] != expected_version:
            raise DefinitionConflict("missing/deleted definition or stale version")
        return row

    def update(self, definition_id: str, *, expected_version: int, changes: dict, now: datetime | None = None) -> dict:
        allowed = {
            "agent_id",
            "schedule",
            "executor",
            "payload",
            "authorities",
            "lease_seconds",
            "timeout_seconds",
            "enabled",
        }
        if not isinstance(changes, dict) or not changes or set(changes) - allowed:
            raise ValueError("known, non-empty changes required")
        when = stamp(now)
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._current(conn, definition_id, expected_version)
            enabled = changes.get("enabled", bool(row["enabled"]))
            if type(enabled) is not bool:
                raise ValueError("enabled must be boolean")
            config = {**json.loads(row["config_json"]), **{k: v for k, v in changes.items() if k != "enabled"}}
            encoded = canonical(self._config(config, when))
            changed = encoded != row["config_json"]
            revision = expected_version + 1 if changed else row["revision"]
            conn.execute(
                "UPDATE agent_trigger_definitions SET version=version+1,revision=?,config_json=?,enabled=?,updated_at=? WHERE id=?",
                (revision, encoded, int(enabled), when, definition_id),
            )
            current = conn.execute("SELECT * FROM agent_trigger_definitions WHERE id=?", (definition_id,)).fetchone()
            self._record(conn, current)
            if changed and config["schedule"]["kind"] != "event":
                self._job(
                    conn, current, now=when, exhausted=self._once_consumed(conn, definition_id, config["schedule"])
                )
            return self._snapshot(current)

    def delete(self, definition_id: str, *, expected_version: int, now: datetime | None = None) -> dict:
        when = stamp(now)
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._current(conn, definition_id, expected_version)
            conn.execute(
                "UPDATE agent_trigger_definitions SET version=version+1,enabled=0,deleted=1,updated_at=? WHERE id=?",
                (when, definition_id),
            )
            row = conn.execute("SELECT * FROM agent_trigger_definitions WHERE id=?", (definition_id,)).fetchone()
            self._record(conn, row)
            return self._snapshot(row)

    def deliver(
        self,
        definition_id: str,
        *,
        expected_version: int,
        event_id: str,
        event_type: str,
        source: str,
        lineage: list[str] | None = None,
        now: datetime | None = None,
    ) -> dict:
        for key, value in (("event_id", event_id), ("event_type", event_type), ("source", source)):
            token(value, key)
        lineage = [] if lineage is None else lineage
        if not isinstance(lineage, list) or len(lineage) >= 8:
            raise ValueError("event chain limit")
        for value in lineage:
            token(value, "lineage")
        if definition_id in lineage or len(set(lineage)) != len(lineage):
            raise ValueError("recursive event chain")
        event = {
            "trigger_id": definition_id,
            "event_id": event_id,
            "event_type": event_type,
            "source": source,
            "lineage": [*lineage, definition_id],
        }
        encoded = canonical(event)
        when = stamp(now)
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._current(conn, definition_id, expected_version)
            schedule = json.loads(row["config_json"])["schedule"]
            if schedule != {"kind": "event", "event_type": event_type}:
                raise ValueError("event type does not match definition")
            prior = conn.execute(
                "SELECT * FROM agent_trigger_deliveries WHERE definition_id=? AND event_id=?", (definition_id, event_id)
            ).fetchone()
            if prior:
                if prior["event_json"] != encoded:
                    raise DefinitionConflict("event ID provenance conflict")
                return {"job_id": prior["job_id"], "duplicate": True, "state": "materialized"}
            job_id = self._job(conn, row, now=when, event=event)
            conn.execute(
                "INSERT INTO agent_trigger_deliveries VALUES (?,?,?,?)", (definition_id, event_id, encoded, job_id)
            )
            return {"job_id": job_id, "duplicate": False, "state": "materialized"}

    def history(self, definition_id: str) -> list[dict]:
        token(definition_id, "definition_id")
        with self.store.read_connection() as conn:
            rows = conn.execute(
                "SELECT snapshot_json FROM agent_trigger_history WHERE definition_id=? ORDER BY version",
                (definition_id,),
            ).fetchall()
        return [json.loads(r[0]) for r in rows]
