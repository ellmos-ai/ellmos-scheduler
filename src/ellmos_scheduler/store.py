from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .schedules import next_after


UTC = timezone.utc


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    schedule_json TEXT NOT NULL,
    executor TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    generation INTEGER NOT NULL DEFAULT 1,
    next_due_at TEXT NOT NULL,
    lease_seconds INTEGER NOT NULL DEFAULT 900,
    timeout_seconds INTEGER NOT NULL DEFAULT 600,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    scheduled_for TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    claimed_by TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    exit_code INTEGER,
    output TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_runs_job_time ON runs(job_id, scheduled_for DESC);
CREATE TABLE IF NOT EXISTS controls (
    scope TEXT PRIMARY KEY,
    paused INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    steer_message TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SchedulerStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def add_job(
        self,
        job_id: str,
        schedule: dict[str, Any],
        executor: str,
        payload: dict[str, Any],
        *,
        now: datetime | None = None,
        enabled: bool = True,
        next_due_at: datetime | None = None,
        lease_seconds: int = 900,
        timeout_seconds: int = 600,
    ) -> None:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        due = (
            next_after(schedule, now)
            if next_due_at is None
            else next_due_at.astimezone(UTC)
        )
        stamp = iso(now)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(
                    id, schedule_json, executor, payload_json, enabled, next_due_at,
                    lease_seconds, timeout_seconds, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    json.dumps(schedule, sort_keys=True),
                    executor,
                    json.dumps(payload, sort_keys=True),
                    int(enabled),
                    iso(due),
                    lease_seconds,
                    timeout_seconds,
                    stamp,
                    stamp,
                ),
            )

    def list_jobs(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def set_enabled(
        self, job_id: str, enabled: bool, *, now: datetime | None = None
    ) -> None:
        stamp = iso(now or datetime.now(UTC))
        with self.connect() as conn:
            result = conn.execute(
                "UPDATE jobs SET enabled = ?, updated_at = ? WHERE id = ?",
                (int(enabled), stamp, job_id),
            )
            if result.rowcount != 1:
                raise KeyError(job_id)

    def set_pause(
        self,
        scope: str,
        paused: bool,
        reason: str = "",
        *,
        now: datetime | None = None,
    ) -> None:
        stamp = iso(now or datetime.now(UTC))
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO controls(scope, paused, reason, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scope) DO UPDATE SET
                    paused = excluded.paused,
                    reason = excluded.reason,
                    updated_at = excluded.updated_at
                """,
                (scope, int(paused), reason, stamp),
            )

    def is_paused(self, conn: sqlite3.Connection, job_id: str) -> bool:
        rows = conn.execute(
            "SELECT paused FROM controls WHERE scope IN ('global', ?)",
            (f"job:{job_id}",),
        ).fetchall()
        return any(row["paused"] for row in rows)

    @staticmethod
    def _run_id(job_id: str, generation: int, scheduled_for: str, attempt: int) -> str:
        material = f"{job_id}|{generation}|{scheduled_for}|{attempt}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def claim_due(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        now = (now or datetime.now(UTC)).astimezone(UTC)
        claimed: list[dict[str, Any]] = []
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            expired = conn.execute(
                """
                SELECT job_id, scheduled_for
                FROM runs
                WHERE status IN ('claimed', 'running') AND lease_expires_at < ?
                """,
                (iso(now),),
            ).fetchall()
            conn.execute(
                """
                UPDATE runs
                SET status = 'abandoned', finished_at = ?
                WHERE status IN ('claimed', 'running') AND lease_expires_at < ?
                """,
                (iso(now), iso(now)),
            )
            for expired_run in expired:
                current = conn.execute(
                    "SELECT next_due_at FROM jobs WHERE id = ?",
                    (expired_run["job_id"],),
                ).fetchone()
                if current and parse_iso(expired_run["scheduled_for"]) < parse_iso(
                    current["next_due_at"]
                ):
                    conn.execute(
                        "UPDATE jobs SET next_due_at = ?, updated_at = ? WHERE id = ?",
                        (expired_run["scheduled_for"], iso(now), expired_run["job_id"]),
                    )
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE enabled = 1 AND next_due_at <= ?
                ORDER BY next_due_at, id
                LIMIT ?
                """,
                (iso(now), limit),
            ).fetchall()
            for row in rows:
                if self.is_paused(conn, row["id"]):
                    continue
                scheduled_for = row["next_due_at"]
                attempt_row = conn.execute(
                    "SELECT COUNT(*) AS count FROM runs WHERE job_id = ? AND scheduled_for = ?",
                    (row["id"], scheduled_for),
                ).fetchone()
                attempt = int(attempt_row["count"]) + 1
                run_id = self._run_id(
                    row["id"], row["generation"], scheduled_for, attempt
                )
                lease_expires = now + timedelta(seconds=row["lease_seconds"])
                conn.execute(
                    """
                    INSERT INTO runs(
                        run_id, job_id, scheduled_for, attempt, claimed_by,
                        lease_expires_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 'claimed')
                    """,
                    (
                        run_id,
                        row["id"],
                        scheduled_for,
                        attempt,
                        worker_id,
                        iso(lease_expires),
                    ),
                )
                schedule = json.loads(row["schedule_json"])
                next_due = next_after(schedule, parse_iso(scheduled_for))
                conn.execute(
                    "UPDATE jobs SET next_due_at = ?, updated_at = ? WHERE id = ?",
                    (iso(next_due), iso(now), row["id"]),
                )
                item = dict(row)
                item.update(
                    {
                        "run_id": run_id,
                        "scheduled_for": scheduled_for,
                        "attempt": attempt,
                        "lease_expires_at": iso(lease_expires),
                    }
                )
                claimed.append(item)
            conn.execute(
                """
                INSERT INTO meta(key, value) VALUES ('last_tick_at', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (iso(now),),
            )
        return claimed

    def start_run(self, run_id: str, *, now: datetime | None = None) -> None:
        stamp = iso(now or datetime.now(UTC))
        with self.connect() as conn:
            result = conn.execute(
                "UPDATE runs SET status = 'running', started_at = ? WHERE run_id = ? AND status = 'claimed'",
                (stamp, run_id),
            )
            if result.rowcount != 1:
                raise RuntimeError(f"run cannot start: {run_id}")

    def finish_run(
        self,
        run_id: str,
        status: str,
        *,
        exit_code: int | None = None,
        output: str = "",
        error: str = "",
        now: datetime | None = None,
    ) -> None:
        if status not in {"succeeded", "failed", "timed_out"}:
            raise ValueError(status)
        stamp = iso(now or datetime.now(UTC))
        with self.connect() as conn:
            result = conn.execute(
                """
                UPDATE runs SET status = ?, finished_at = ?, exit_code = ?,
                    output = ?, error = ?
                WHERE run_id = ? AND status = 'running'
                """,
                (status, stamp, exit_code, output[-20000:], error[-20000:], run_id),
            )
            if result.rowcount != 1:
                raise RuntimeError(f"run cannot finish: {run_id}")

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY scheduled_for DESC, attempt DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_runs_by_job(self) -> dict[str, dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT r.*
                FROM runs r
                WHERE r.run_id = (
                    SELECT latest.run_id
                    FROM runs latest
                    WHERE latest.job_id = r.job_id
                    ORDER BY latest.scheduled_for DESC, latest.attempt DESC
                    LIMIT 1
                )
                """
            ).fetchall()
        return {str(row["job_id"]): dict(row) for row in rows}

    def status(self) -> dict[str, Any]:
        with self.connect() as conn:
            jobs = conn.execute(
                "SELECT COUNT(*) total, SUM(enabled) enabled FROM jobs"
            ).fetchone()
            runs = conn.execute(
                """
                SELECT COUNT(*) total,
                    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) succeeded,
                    SUM(CASE WHEN status IN ('failed', 'timed_out') THEN 1 ELSE 0 END) failed,
                    SUM(CASE WHEN status IN ('claimed', 'running') THEN 1 ELSE 0 END) active
                FROM runs
                """
            ).fetchone()
            control = conn.execute(
                "SELECT paused, reason FROM controls WHERE scope = 'global'"
            ).fetchone()
            tick = conn.execute(
                "SELECT value FROM meta WHERE key = 'last_tick_at'"
            ).fetchone()
        return {
            "database": str(self.path),
            "jobs": {
                "total": jobs["total"] or 0,
                "enabled": jobs["enabled"] or 0,
            },
            "runs": {
                "total": runs["total"] or 0,
                "succeeded": runs["succeeded"] or 0,
                "failed": runs["failed"] or 0,
                "active": runs["active"] or 0,
            },
            "control": {
                "paused": bool(control["paused"]) if control else False,
                "reason": control["reason"] if control else "",
            },
            "last_tick_at": tick["value"] if tick else None,
        }
