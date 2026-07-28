from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

from ellmos_scheduler.bach import (
    BachSchedulerAdapter,
    import_legacy_jobs,
    legacy_next_due,
    map_legacy_job,
    parse_legacy_interval,
    read_legacy_jobs,
)
from ellmos_scheduler.cli import main
from ellmos_scheduler.store import SchedulerStore


UTC = timezone.utc


def _legacy_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE scheduler_jobs (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            job_type TEXT NOT NULL,
            schedule TEXT,
            command TEXT,
            script_path TEXT,
            arguments TEXT,
            is_active INTEGER,
            timeout_seconds INTEGER,
            retry_on_fail INTEGER,
            max_retries INTEGER,
            last_run TEXT,
            next_run TEXT
        );
        """
    )
    rows = [
        (
            7,
            "interval script",
            "safe script job",
            "interval",
            "30m",
            "",
            "system/task.py",
            "--mode check",
            1,
            90,
            1,
            2,
            "2026-07-28T11:45:00",
            None,
        ),
        (
            8,
            "cron command",
            "safe argv command",
            "cron",
            "*/15 * * * *",
            f'"{sys.executable}" -c "print(123)"',
            None,
            "",
            0,
            120,
            0,
            3,
            None,
            None,
        ),
        (
            9,
            "manual",
            "not automatically due",
            "manual",
            "",
            "echo manual",
            None,
            "",
            1,
            30,
            0,
            0,
            None,
            None,
        ),
        (
            10,
            "unsafe shell",
            "requires manual conversion",
            "interval",
            "1h",
            "echo one && echo two",
            None,
            "",
            1,
            30,
            0,
            0,
            None,
            None,
        ),
        (
            11,
            "missing executable",
            "cannot run without the legacy shell",
            "interval",
            "1h",
            "definitely-not-a-real-executable-ellmos hello",
            None,
            "",
            1,
            30,
            0,
            0,
            None,
            None,
        ),
    ]
    conn.executemany(
        """
        INSERT INTO scheduler_jobs(
            id, name, description, job_type, schedule, command, script_path,
            arguments, is_active, timeout_seconds, retry_on_fail, max_retries,
            last_run, next_run
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()
    return path


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bach_interval_parser_and_due_parity():
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    assert parse_legacy_interval("30m").total_seconds() == 1800
    # BACH uses last_run + interval while it remains in the future.
    assert legacy_next_due(
        "interval",
        "30m",
        now=now,
        last_run="2026-07-28T11:45:00+00:00",
    ) == datetime(2026, 7, 28, 12, 15, tzinfo=UTC)
    # If that time is already past, BACH resets to now + interval.
    assert legacy_next_due(
        "interval",
        "30m",
        now=now,
        last_run="2026-07-28T10:00:00+00:00",
    ) == datetime(2026, 7, 28, 12, 30, tzinfo=UTC)


def test_bach_interval_nonexistent_dst_due_runs_at_gap_end():
    result = legacy_next_due(
        "interval",
        "30m",
        now=datetime(2026, 3, 29, 0, 50, tzinfo=UTC),
        last_run="2026-03-29T01:45:00",
        timezone_name="Europe/Berlin",
    )
    assert result == datetime(2026, 3, 29, 1, 0, tzinfo=UTC)


def test_cron_day_fields_match_bach_croniter_or_semantics():
    # 13th OR Monday, not 13th AND Monday.
    result = legacy_next_due(
        "cron",
        "0 9 13 * 1",
        now=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
    )
    assert result == datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


def test_legacy_mapping_preserves_provenance_and_due():
    mapped = map_legacy_job(
        {
            "id": 7,
            "name": "job",
            "description": "desc",
            "job_type": "interval",
            "schedule": "30m",
            "script_path": "task.py",
            "arguments": "--check",
            "is_active": 1,
            "timeout_seconds": 90,
            "retry_on_fail": 1,
            "max_retries": 2,
            "last_run": "2026-07-28T11:45:00+00:00",
        },
        now=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        bach_root="C:\\bach",
    )
    assert mapped.job_id == "bach:7"
    assert mapped.executor == "subprocess"
    assert mapped.payload["argv"][:2] == [sys.executable, "task.py"]
    assert mapped.payload["_bach"]["source_job_id"] == "7"
    assert mapped.payload["_bach"]["retry_on_fail"] is True
    assert mapped.next_due_at == datetime(2026, 7, 28, 12, 15, tzinfo=UTC)


def test_legacy_command_shell_expansions_are_rejected():
    base = {
        "id": 12,
        "name": "unsafe expansion",
        "job_type": "interval",
        "schedule": "1h",
        "is_active": 1,
    }
    for command in (
        "python process.py *.txt",
        "python process.py $INPUT",
        "python process.py %INPUT%",
    ):
        try:
            map_legacy_job(
                {**base, "command": command},
                now=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
            )
        except ValueError as error:
            assert "manual argv conversion" in str(error)
        else:
            raise AssertionError(f"shell expansion was accepted: {command}")


def test_import_is_read_only_idempotent_and_reports_skips(tmp_path):
    source = _legacy_db(tmp_path / "bach.db")
    target = SchedulerStore(tmp_path / "ellmos.db")
    before = _sha256(source)
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)

    preview = import_legacy_jobs(
        source,
        target,
        now=now,
        bach_root=tmp_path,
        dry_run=True,
    )
    assert preview.ready == 2
    assert preview.imported == 0
    assert preview.skipped == 3
    assert not target.path.exists()

    report = import_legacy_jobs(
        source,
        target,
        now=now,
        bach_root=tmp_path,
    )
    assert report.imported == 2
    assert report.skipped == 3
    assert _sha256(source) == before
    jobs = target.list_jobs()
    assert [job["id"] for job in jobs] == ["bach:7", "bach:8"]
    assert jobs[0]["next_due_at"] == "2026-07-28T12:15:00Z"
    assert jobs[1]["enabled"] == 0
    provenance = json.loads(jobs[0]["payload_json"])["_bach"]
    assert provenance["name"] == "interval script"

    repeated = import_legacy_jobs(source, target, now=now, bach_root=tmp_path)
    assert repeated.imported == 0
    assert repeated.skipped == 5
    assert len(target.list_jobs()) == 2


def test_dry_run_does_not_modify_existing_target(tmp_path):
    source = _legacy_db(tmp_path / "bach.db")
    target = SchedulerStore(tmp_path / "ellmos.db")
    target.init()
    target.add_job(
        "bach:7",
        {"kind": "interval", "seconds": 60},
        "noop",
        {},
        now=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
    )
    before = _sha256(target.path)

    report = import_legacy_jobs(
        source,
        target,
        now=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        dry_run=True,
    )

    assert _sha256(target.path) == before
    assert any(
        item.target_job_id == "bach:7" and item.reason == "target job already exists"
        for item in report.items
    )


def test_read_legacy_jobs_rejects_missing_table_without_mutation(tmp_path):
    source = tmp_path / "other.db"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE other(value TEXT)")
    conn.commit()
    conn.close()
    before = _sha256(source)
    try:
        read_legacy_jobs(source)
    except ValueError as error:
        assert "scheduler_jobs" in str(error)
    else:
        raise AssertionError("missing scheduler_jobs table was accepted")
    assert _sha256(source) == before


def test_import_rejects_identical_source_and_target_without_mutation(tmp_path):
    source = _legacy_db(tmp_path / "bach.db")
    before_hash = _sha256(source)
    conn = sqlite3.connect(source)
    before_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    conn.close()

    try:
        import_legacy_jobs(source, SchedulerStore(source))
    except ValueError as error:
        assert "must be different files" in str(error)
    else:
        raise AssertionError("identical source and target were accepted")

    hardlink = tmp_path / "hardlinked-target.db"
    os.link(source, hardlink)
    try:
        import_legacy_jobs(source, SchedulerStore(hardlink))
    except ValueError as error:
        assert "must be different files" in str(error)
    else:
        raise AssertionError("hardlinked source and target were accepted")

    conn = sqlite3.connect(source)
    after_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    conn.close()
    assert after_tables == before_tables == {"scheduler_jobs"}
    assert _sha256(source) == before_hash


def test_bach_consumer_adapter_exposes_status_jobs_and_controls(tmp_path):
    source = _legacy_db(tmp_path / "bach.db")
    adapter = BachSchedulerAdapter(tmp_path / "state.db", worker_id="bach-test")
    adapter.import_legacy(
        source,
        now=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        bach_root=tmp_path,
    )

    assert adapter.status()["provider"] == "ellmos-scheduler"
    jobs = adapter.jobs(now=datetime(2026, 7, 28, 12, 10, tzinfo=UTC))
    assert jobs[0]["id"] == "7"
    assert jobs[0]["status"] == "scheduled"
    assert jobs[1]["status"] == "disabled"
    adapter.pause("maintenance")
    assert adapter.status()["control"] == {
        "paused": True,
        "reason": "maintenance",
    }
    adapter.resume()
    assert adapter.status()["control"]["paused"] is False


def test_imported_bach_script_runs_end_to_end_through_adapter(tmp_path):
    source = _legacy_db(tmp_path / "bach.db")
    script = tmp_path / "system" / "task.py"
    script.parent.mkdir()
    script.write_text(
        "import os\n"
        "print(os.environ['BACH_SCHEDULER_JOB_ID'])\n"
        "print(os.environ['BACH_SCHEDULER_TRIGGERED_BY'])\n",
        encoding="utf-8",
    )
    adapter = BachSchedulerAdapter(tmp_path / "state.db", worker_id="bach-e2e")
    adapter.import_legacy(
        source,
        now=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        bach_root=tmp_path,
    )

    adapter.pause(job_id="7")
    assert adapter.tick(now=datetime(2026, 7, 28, 12, 15, tzinfo=UTC)) == []
    adapter.resume(job_id="7")
    result = adapter.tick(now=datetime(2026, 7, 28, 12, 15, tzinfo=UTC))

    assert result == [
        {
            "run_id": result[0]["run_id"],
            "job_id": "bach:7",
            "status": "succeeded",
            "exit_code": 0,
        }
    ]
    run = adapter.store.recent_runs()[0]
    assert run["output"].splitlines() == ["7", "ellmos-scheduler"]


def test_bach_job_status_prioritizes_latest_run_error(tmp_path):
    adapter = BachSchedulerAdapter(tmp_path / "state.db", worker_id="bach-error")
    base = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    adapter.store.add_job(
        "failing",
        {"kind": "interval", "seconds": 60},
        "noop",
        {"fail": True},
        now=base,
    )

    result = adapter.tick(now=datetime(2026, 7, 28, 12, 1, tzinfo=UTC))
    jobs = adapter.jobs(now=datetime(2026, 7, 28, 12, 1, tzinfo=UTC))

    assert result[0]["status"] == "failed"
    assert jobs[0]["status"] == "error"
    assert jobs[0]["last_result"] == "failed"
    assert jobs[0]["last_run"] == "2026-07-28T12:01:00Z"


def test_import_bach_cli_dry_run_does_not_create_target(tmp_path, capsys):
    source = _legacy_db(tmp_path / "bach.db")
    target = tmp_path / "state.db"
    exit_code = main(
        [
            "--db",
            str(target),
            "import-bach",
            "--source-db",
            str(source),
            "--dry-run",
            "--json",
        ]
    )
    assert exit_code == 0
    assert not target.exists()
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] == 2
