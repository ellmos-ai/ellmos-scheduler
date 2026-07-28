from __future__ import annotations

import json
import os
import shlex
import shutil
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .executors import DEFAULT_REGISTRY, ExecutorRegistry
from .schedules import _first_valid_local, next_after
from .service import SchedulerService
from .store import SchedulerStore, parse_iso


UTC = timezone.utc
_SHELL_OPERATORS = {
    "&",
    "&&",
    "|",
    "||",
    ";",
    "<",
    ">",
    ">>",
    "2>",
    "2>>",
}
_SHELL_EXPANSION_CHARACTERS = frozenset("$%!*?[]{}^`")
_SHELL_OPERATOR_CHARACTERS = frozenset("|&;<>()~")


class LegacyJobUnsupported(ValueError):
    """A legacy job cannot be migrated without changing its semantics or safety."""


@dataclass(frozen=True)
class MigratedJob:
    job_id: str
    schedule: dict[str, Any]
    executor: str
    payload: dict[str, Any]
    enabled: bool
    timeout_seconds: int
    next_due_at: datetime


@dataclass(frozen=True)
class MigrationItem:
    source_job_id: str
    target_job_id: str
    action: str
    reason: str = ""


@dataclass(frozen=True)
class MigrationReport:
    source_db: str
    target_db: str | None
    dry_run: bool
    total: int
    imported: int
    ready: int
    skipped: int
    items: tuple[MigrationItem, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["items"] = [asdict(item) for item in self.items]
        return result


def parse_legacy_interval(value: str) -> timedelta:
    """Parse exactly the s/m/h/d interval notation accepted by BACH."""
    if not isinstance(value, str) or len(value) < 2:
        raise LegacyJobUnsupported("invalid BACH interval")
    try:
        amount = int(value[:-1])
    except ValueError as exc:
        raise LegacyJobUnsupported(f"invalid BACH interval: {value!r}") from exc
    units = {
        "s": timedelta(seconds=amount),
        "m": timedelta(minutes=amount),
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
    }
    try:
        interval = units[value[-1].lower()]
    except KeyError:
        raise LegacyJobUnsupported(f"invalid BACH interval unit: {value!r}") from None
    if interval <= timedelta(0):
        raise LegacyJobUnsupported("BACH interval must be positive")
    return interval


def _aware_legacy_datetime(value: Any, zone: ZoneInfo) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise LegacyJobUnsupported(f"invalid legacy datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(zone)


def legacy_next_due(
    job_type: str,
    schedule: str,
    *,
    now: datetime,
    last_run: Any = None,
    timezone_name: str = "UTC",
) -> datetime:
    """Reproduce the due calculation in BACH's daemon_service.py."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    zone = ZoneInfo(timezone_name)
    local_now = now.astimezone(zone)
    if job_type == "interval":
        interval = parse_legacy_interval(schedule)
        previous = _aware_legacy_datetime(last_run, zone)
        candidate = previous + interval if previous else local_now + interval
        if candidate < local_now:
            candidate = local_now + interval
        candidate = _first_valid_local(candidate, zone)
        return candidate.astimezone(UTC)
    if job_type == "cron":
        return next_after(
            {
                "kind": "cron",
                "expression": schedule,
                "timezone": timezone_name,
            },
            now,
        )
    raise LegacyJobUnsupported(f"unsupported BACH job type: {job_type!r}")


def _split_legacy_command(value: str) -> list[str]:
    quote: str | None = None
    for character in value:
        if character in "\r\n" or character in _SHELL_EXPANSION_CHARACTERS:
            raise LegacyJobUnsupported(
                "shell expansion or metacharacters require manual argv conversion"
            )
        if character in {"'", '"'}:
            quote = (
                None if quote == character else (character if quote is None else quote)
            )
        elif quote is None and character in _SHELL_OPERATOR_CHARACTERS:
            raise LegacyJobUnsupported("shell operators require manual argv conversion")
    try:
        argv = shlex.split(value, posix=(os.name != "nt"))
    except ValueError as exc:
        raise LegacyJobUnsupported(f"command cannot be parsed safely: {exc}") from exc
    if os.name == "nt":
        argv = [
            token[1:-1]
            if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}
            else token
            for token in argv
        ]
    if not argv:
        raise LegacyJobUnsupported("legacy command is empty")
    if any(
        token in _SHELL_OPERATORS
        or any(operator in token for operator in ("&&", "||", "|", "&", ";", "<", ">"))
        for token in argv
    ):
        raise LegacyJobUnsupported("shell operators require manual argv conversion")
    return argv


def _require_executable(argv: list[str], bach_root: str | Path | None) -> None:
    executable = argv[0]
    candidate = Path(executable)
    if candidate.is_absolute():
        if not candidate.is_file():
            raise LegacyJobUnsupported(
                f"command executable does not exist: {executable}"
            )
        return
    if any(separator in executable for separator in ("/", "\\")):
        if bach_root is None:
            raise LegacyJobUnsupported(
                "relative command path requires an explicit BACH root"
            )
        resolved = Path(bach_root) / candidate
        if not resolved.is_file():
            raise LegacyJobUnsupported(
                f"relative command executable does not exist: {executable}"
            )
        return
    if shutil.which(executable) is None:
        raise LegacyJobUnsupported(
            f"command is not an executable on PATH: {executable!r}"
        )


def map_legacy_job(
    row: Mapping[str, Any],
    *,
    now: datetime,
    timezone_name: str = "UTC",
    bach_root: str | Path | None = None,
) -> MigratedJob:
    """Map one BACH scheduler_jobs row without writing either database."""
    source_id = str(row.get("id", "")).strip()
    if not source_id:
        raise LegacyJobUnsupported("legacy job has no id")
    job_type = str(row.get("job_type") or "").strip().lower()
    schedule_text = str(row.get("schedule") or "").strip()
    if job_type == "interval":
        interval = parse_legacy_interval(schedule_text)
        schedule = {"kind": "interval", "seconds": int(interval.total_seconds())}
    elif job_type == "cron":
        if not schedule_text:
            raise LegacyJobUnsupported("cron job has no expression")
        schedule = {
            "kind": "cron",
            "expression": schedule_text,
            "timezone": timezone_name,
        }
    else:
        raise LegacyJobUnsupported(
            f"BACH job type {job_type or '<empty>'!r} has no automatic due parity"
        )

    arguments = str(row.get("arguments") or "").strip()
    script_path = str(row.get("script_path") or "").strip()
    command = str(row.get("command") or "").strip()
    if script_path:
        argv = [sys.executable, script_path]
        if arguments:
            argv.extend(_split_legacy_command(arguments))
    elif command:
        argv = _split_legacy_command(command)
        if arguments:
            argv.extend(_split_legacy_command(arguments))
        _require_executable(argv, bach_root)
    else:
        raise LegacyJobUnsupported("legacy job has neither script_path nor command")

    name = str(row.get("name") or f"BACH job {source_id}")
    provenance = {
        "schema": "bach.scheduler_jobs.v1",
        "source_job_id": source_id,
        "name": name,
        "description": str(row.get("description") or ""),
        "job_type": job_type,
        "schedule": schedule_text,
        "retry_on_fail": bool(row.get("retry_on_fail") or False),
        "max_retries": int(row.get("max_retries") or 0),
    }
    payload: dict[str, Any] = {
        "argv": argv,
        "env": {
            "BACH_SCHEDULER_JOB_ID": source_id,
            "BACH_SCHEDULER_JOB_NAME": name,
            "BACH_SCHEDULER_TRIGGERED_BY": "ellmos-scheduler",
        },
        "_bach": provenance,
    }
    if bach_root is not None:
        payload["cwd"] = str(Path(bach_root).resolve())
    timeout = int(row.get("timeout_seconds") or 300)
    if timeout <= 0:
        timeout = 300
    return MigratedJob(
        job_id=f"bach:{source_id}",
        schedule=schedule,
        executor="subprocess",
        payload=payload,
        enabled=bool(row.get("is_active", True)),
        timeout_seconds=timeout,
        next_due_at=legacy_next_due(
            job_type,
            schedule_text,
            now=now,
            last_run=row.get("last_run"),
            timezone_name=timezone_name,
        ),
    )


def read_legacy_jobs(source_db: str | Path) -> list[dict[str, Any]]:
    """Read BACH jobs through SQLite's mode=ro URI; never create or mutate source."""
    source = Path(source_db).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    uri = f"{source.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'scheduler_jobs'"
        ).fetchone()
        if table is None:
            raise ValueError("source database has no scheduler_jobs table")
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM scheduler_jobs ORDER BY id"
            ).fetchall()
        ]
    finally:
        conn.close()


def _read_existing_target_ids(target_db: Path) -> set[str]:
    if not target_db.is_file():
        return set()
    conn = sqlite3.connect(f"{target_db.resolve().as_uri()}?mode=ro", uri=True)
    try:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
        ).fetchone()
        if table is None:
            return set()
        return {str(row[0]) for row in conn.execute("SELECT id FROM jobs").fetchall()}
    finally:
        conn.close()


def import_legacy_jobs(
    source_db: str | Path,
    store: SchedulerStore | None,
    *,
    now: datetime | None = None,
    timezone_name: str = "UTC",
    bach_root: str | Path | None = None,
    dry_run: bool = False,
) -> MigrationReport:
    """Preview or import supported BACH jobs; duplicates are never overwritten."""
    if not dry_run and store is None:
        raise ValueError("store is required unless dry_run=True")
    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    source = Path(source_db).expanduser().resolve()
    if store is not None:
        target = store.path.expanduser().resolve()
        same_path = os.path.normcase(str(source)) == os.path.normcase(str(target))
        if source.exists() and target.exists():
            same_path = same_path or os.path.samefile(source, target)
        if same_path:
            raise ValueError("source and target databases must be different files")
    rows = read_legacy_jobs(source)
    existing: set[str] = set()
    if store is not None:
        if dry_run:
            existing = _read_existing_target_ids(store.path)
        else:
            store.init()
            existing = {str(job["id"]) for job in store.list_jobs()}

    items: list[MigrationItem] = []
    imported = 0
    ready = 0
    for row in rows:
        source_id = str(row.get("id", ""))
        target_id = f"bach:{source_id}"
        try:
            mapped = map_legacy_job(
                row,
                now=stamp,
                timezone_name=timezone_name,
                bach_root=bach_root,
            )
        except (LegacyJobUnsupported, ValueError) as exc:
            items.append(MigrationItem(source_id, target_id, "skipped", str(exc)))
            continue
        if mapped.job_id in existing:
            items.append(
                MigrationItem(
                    source_id,
                    mapped.job_id,
                    "skipped",
                    "target job already exists",
                )
            )
            continue
        if dry_run:
            ready += 1
            items.append(MigrationItem(source_id, mapped.job_id, "ready"))
            continue
        assert store is not None
        store.add_job(
            mapped.job_id,
            mapped.schedule,
            mapped.executor,
            mapped.payload,
            now=stamp,
            enabled=mapped.enabled,
            next_due_at=mapped.next_due_at,
            timeout_seconds=mapped.timeout_seconds,
        )
        existing.add(mapped.job_id)
        imported += 1
        items.append(MigrationItem(source_id, mapped.job_id, "imported"))

    return MigrationReport(
        source_db=str(source),
        target_db=None if store is None else str(store.path),
        dry_run=dry_run,
        total=len(rows),
        imported=imported,
        ready=ready,
        skipped=sum(item.action == "skipped" for item in items),
        items=tuple(items),
    )


class BachSchedulerAdapter:
    """Narrow consumer API used by BACH after its provider seam selects this module."""

    def __init__(
        self,
        state_db: str | Path,
        *,
        registry: ExecutorRegistry | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.store = SchedulerStore(state_db)
        self.store.init()
        self.service = SchedulerService(
            self.store,
            worker_id=worker_id,
            registry=registry or DEFAULT_REGISTRY,
        )

    def status(self) -> dict[str, Any]:
        result = self.store.status()
        return {"provider": "ellmos-scheduler", **result}

    def jobs(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        stamp = (now or datetime.now(UTC)).astimezone(UTC)
        latest_runs = self.store.latest_runs_by_job()
        result: list[dict[str, Any]] = []
        for row in self.store.list_jobs():
            payload = json.loads(row["payload_json"])
            provenance = payload.get("_bach", {})
            if not isinstance(provenance, Mapping):
                provenance = {}
            enabled = bool(row["enabled"])
            due = parse_iso(row["next_due_at"]) <= stamp
            latest = latest_runs.get(str(row["id"]))
            last_status = None if latest is None else latest["status"]
            if not enabled:
                status = "disabled"
            elif last_status in {"failed", "timed_out", "abandoned"}:
                status = "error"
            else:
                status = "due" if due else "scheduled"
            result.append(
                {
                    "id": provenance.get("source_job_id", row["id"]),
                    "scheduler_id": row["id"],
                    "name": provenance.get("name", row["id"]),
                    "description": provenance.get("description", ""),
                    "job_type": provenance.get(
                        "job_type",
                        json.loads(row["schedule_json"]).get("kind"),
                    ),
                    "schedule": provenance.get("schedule", row["schedule_json"]),
                    "is_active": enabled,
                    "status": status,
                    "next_run": row["next_due_at"],
                    "last_run": None
                    if latest is None
                    else latest["finished_at"] or latest["started_at"],
                    "last_result": last_status,
                }
            )
        return result

    def pause(self, reason: str = "", *, job_id: str | None = None) -> None:
        scope = f"job:{self._scheduler_job_id(job_id)}" if job_id else "global"
        self.store.set_pause(scope, True, reason)

    def resume(self, *, job_id: str | None = None) -> None:
        scope = f"job:{self._scheduler_job_id(job_id)}" if job_id else "global"
        self.store.set_pause(scope, False)

    def _scheduler_job_id(self, job_id: str) -> str:
        value = str(job_id)
        scheduler_ids = {str(row["id"]) for row in self.store.list_jobs()}
        if value in scheduler_ids:
            return value
        migrated = f"bach:{value}"
        return migrated if migrated in scheduler_ids else value

    def tick(self, *, now: datetime | None = None, limit: int = 20) -> list[dict]:
        return self.service.tick(now=now, limit=limit)

    def import_legacy(
        self,
        source_db: str | Path,
        **options: Any,
    ) -> MigrationReport:
        return import_legacy_jobs(source_db, self.store, **options)


def create_bach_adapter(
    state_db: str | Path,
    **options: Any,
) -> BachSchedulerAdapter:
    return BachSchedulerAdapter(state_db, **options)
