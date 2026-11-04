"""Persistent event delivery; materialized jobs use the ordinary scheduler gates."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

EVENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS event_triggers (
 id TEXT PRIMARY KEY, version INTEGER NOT NULL, config_json TEXT NOT NULL,
 enabled INTEGER NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_deliveries (
 trigger_id TEXT NOT NULL REFERENCES event_triggers(id), event_id TEXT NOT NULL,
 event_json TEXT NOT NULL, job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
 PRIMARY KEY(trigger_id, event_id)
);
"""
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}\Z")


def token(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def stamp(now: datetime | None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def event_job_allowed(conn: Any, job_id: str) -> bool:
    row = conn.execute(
        """SELECT t.id, t.enabled FROM event_deliveries d
        JOIN event_triggers t ON t.id=d.trigger_id WHERE d.job_id=?""",
        (job_id,),
    ).fetchone()
    if row is None:
        return True
    if not row["enabled"]:
        return False
    return not any(
        r["paused"]
        for r in conn.execute("SELECT paused FROM controls WHERE scope IN ('global', ?)", ("trigger:" + row["id"],))
    )


class EventTriggers:
    """Consumer-selected event subscriptions; provenance never grants authority.

    Definitions are immutable except enabled via version CAS. Replace a definition
    by creating a new ID; previously delivered jobs retain the original payload.
    """

    def __init__(self, store: Any):
        self.store = store

    def create(
        self,
        trigger_id: str,
        *,
        event_type: str,
        executor: str,
        payload: dict,
        enabled: bool = True,
        lease_seconds: int = 900,
        timeout_seconds: int = 600,
        authorities: list | None = None,
        now: datetime | None = None,
    ) -> dict:
        token(trigger_id, "trigger_id")
        token(event_type, "event_type")
        token(executor, "executor")
        if not isinstance(payload, dict) or "_scheduler_event" in payload:
            raise ValueError("payload must be an object without reserved _scheduler_event")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        for value in (lease_seconds, timeout_seconds):
            if type(value) is not int or value <= 0:
                raise ValueError("lease and timeout must be positive integers")
        config = {
            "event_type": event_type,
            "executor": executor,
            "payload": payload,
            "lease_seconds": lease_seconds,
            "timeout_seconds": timeout_seconds,
            "authorities": self.store.authority_registry.validate_specs(authorities),
        }
        encoded = canonical(config)
        when = stamp(now)
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM event_triggers WHERE id=?", (trigger_id,)).fetchone():
                raise ValueError("trigger_id already exists")
            conn.execute("INSERT INTO event_triggers VALUES (?, 1, ?, ?, ?)", (trigger_id, encoded, int(enabled), when))
        return {"id": trigger_id, "version": 1, "enabled": enabled, **config}

    def list(self) -> list[dict]:
        with self.store.read_connection() as conn:
            rows = conn.execute("SELECT * FROM event_triggers ORDER BY id").fetchall()
        return [
            {"id": r["id"], "version": r["version"], "enabled": bool(r["enabled"]), **json.loads(r["config_json"])}
            for r in rows
        ]

    def set_enabled(self, trigger_id: str, enabled: bool, *, expected_version: int, now: datetime | None = None) -> int:
        token(trigger_id, "trigger_id")
        if type(enabled) is not bool or type(expected_version) is not int or expected_version < 1:
            raise ValueError("boolean enabled and positive expected_version required")
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = conn.execute(
                """UPDATE event_triggers SET enabled=?, version=version+1,
                updated_at=? WHERE id=? AND version=?""",
                (int(enabled), stamp(now), trigger_id, expected_version),
            )
            if result.rowcount != 1:
                raise ValueError("definition version conflict or missing trigger")
        return expected_version + 1

    def deliver(
        self,
        trigger_id: str,
        *,
        event_id: str,
        event_type: str,
        source: str,
        lineage: list[str] | None = None,
        now: datetime | None = None,
    ) -> dict:
        for field, value in (
            ("trigger_id", trigger_id),
            ("event_id", event_id),
            ("event_type", event_type),
            ("source", source),
        ):
            token(value, field)
        lineage = [] if lineage is None else lineage
        if not isinstance(lineage, list) or len(lineage) >= 8:
            raise ValueError("event chain limit exceeded")
        for ancestor in lineage:
            token(ancestor, "lineage")
        if trigger_id in lineage or len(set(lineage)) != len(lineage):
            raise ValueError("recursive event chain")
        event = {
            "trigger_id": trigger_id,
            "event_id": event_id,
            "event_type": event_type,
            "source": source,
            "lineage": [*lineage, trigger_id],
        }
        encoded = canonical(event)
        when = stamp(now)
        job_id = "event-" + hashlib.sha256(canonical([trigger_id, event_id]).encode()).hexdigest()
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            trigger = conn.execute("SELECT * FROM event_triggers WHERE id=?", (trigger_id,)).fetchone()
            if trigger is None:
                raise KeyError(trigger_id)
            config = json.loads(trigger["config_json"])
            if config["event_type"] != event_type:
                raise ValueError("event type does not match definition")
            prior = conn.execute(
                "SELECT * FROM event_deliveries WHERE trigger_id=? AND event_id=?", (trigger_id, event_id)
            ).fetchone()
            if prior:
                if prior["event_json"] != encoded:
                    raise ValueError("event ID conflict: provenance differs")
                return {"job_id": prior["job_id"], "duplicate": True, "state": "materialized"}
            payload = {**config["payload"], "_scheduler_event": event}
            conn.execute(
                """INSERT INTO jobs (id,schedule_json,executor,payload_json,enabled,
                next_due_at,lease_seconds,timeout_seconds,authorities_json,created_at,updated_at)
                VALUES (?,?,?,?,1,?,?,?,?,?,?)""",
                (
                    job_id,
                    canonical({"kind": "once", "at": when}),
                    config["executor"],
                    canonical(payload),
                    when,
                    config["lease_seconds"],
                    config["timeout_seconds"],
                    canonical(config["authorities"]),
                    when,
                    when,
                ),
            )
            conn.execute("INSERT INTO event_deliveries VALUES (?,?,?,?)", (trigger_id, event_id, encoded, job_id))
        return {"job_id": job_id, "duplicate": False, "state": "materialized"}

    def deliveries(self, trigger_id: str) -> list[dict]:
        token(trigger_id, "trigger_id")
        with self.store.read_connection() as conn:
            rows = conn.execute(
                "SELECT event_json,job_id FROM event_deliveries WHERE trigger_id=? ORDER BY event_id", (trigger_id,)
            ).fetchall()
        return [{**json.loads(r["event_json"]), "job_id": r["job_id"]} for r in rows]
