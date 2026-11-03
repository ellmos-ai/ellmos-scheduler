from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timedelta, timezone
from pathlib import PureWindowsPath
from urllib.parse import unquote, urlsplit

import pytest

from ellmos_scheduler.cli import main
from ellmos_scheduler.service import SchedulerService
from ellmos_scheduler.store import SchedulerStore, _readonly_uri


@pytest.fixture
def state(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.add_job("fixture", {"kind": "interval", "seconds": 60}, "noop", {}, now=now)
    result = SchedulerService(store, "inspection-fixture").tick(now=now + timedelta(seconds=60))
    return store, result[0]["run_id"]


@pytest.mark.parametrize("command", ["status", "jobs", "runs", "authority-receipt"])
def test_inspection_missing_database_does_not_create_state(tmp_path, capsys, command):
    database = tmp_path / "absent" / "scheduler.db"
    arguments = ["--db", str(database), command]
    if command == "authority-receipt":
        arguments.append("missing-run")
    assert main([*arguments, "--json"]) == 2
    assert not database.parent.exists()
    output = capsys.readouterr()
    assert output.out == ""
    assert "Cannot inspect scheduler database" in output.err


@pytest.mark.parametrize("command", ["status", "jobs", "runs", "authority-receipt"])
def test_inspection_never_initializes_or_migrates_existing_state(state, monkeypatch, capsys, command):
    store, run_id = state
    before = store.path.read_bytes()

    def forbidden(*args):
        raise AssertionError("inspection must not initialize or migrate state")

    monkeypatch.setattr(SchedulerStore, "init", forbidden)
    arguments = ["--db", str(store.path), command]
    if command == "authority-receipt":
        arguments.append(run_id)
    assert main([*arguments, "--json"]) == 0
    assert capsys.readouterr().err == ""
    assert store.path.read_bytes() == before


def test_inspection_does_not_migrate_an_uninitialized_schema(tmp_path, capsys):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE existing (value TEXT)")
        conn.execute("INSERT INTO existing VALUES ('retained')")
    before = database.read_bytes()
    assert main(["--db", str(database), "status", "--json"]) == 2
    assert database.read_bytes() == before
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("existing",)]
    assert "Cannot inspect scheduler database" in capsys.readouterr().err


def test_inspection_reports_corrupt_database_without_replacing_it(tmp_path, capsys):
    database = tmp_path / "corrupt.db"
    database.write_bytes(b"synthetic invalid database")
    assert main(["--db", str(database), "status", "--json"]) == 2
    assert database.read_bytes() == b"synthetic invalid database"
    assert capsys.readouterr().out == ""


def test_missing_run_receipt_is_an_explicit_error(state, capsys):
    store, _ = state
    assert main(["--db", str(store.path), "authority-receipt", "absent", "--json"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "Cannot inspect scheduler database" in output.err


def test_read_connection_rejects_writes_even_if_query_only_is_disabled(state):
    store, _ = state
    with store.read_connection() as conn:
        conn.execute("PRAGMA query_only=OFF")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO meta (key,value) VALUES ('forbidden','write')")
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM meta WHERE key='forbidden'").fetchone()[0] == 0


def test_inspection_sees_committed_live_wal_state(state):
    store, _ = state
    with store.connect() as writer:
        writer.execute("UPDATE meta SET value='live-wal-marker' WHERE key='last_tick_at'")
        writer.commit()
        assert store.path.with_name("scheduler.db-wal").is_file()
        assert store.status()["last_tick_at"] == "live-wal-marker"


def test_read_connection_keeps_one_snapshot_during_concurrent_commit(state):
    store, _ = state
    with store.connect() as writer, store.read_connection() as reader:
        assert reader.execute("SELECT COUNT(*) FROM meta WHERE key='later'").fetchone()[0] == 0
        writer.execute("INSERT INTO meta (key,value) VALUES ('later','committed')")
        writer.commit()
        assert reader.execute("SELECT COUNT(*) FROM meta WHERE key='later'").fetchone()[0] == 0
    with store.read_connection() as reader:
        assert reader.execute("SELECT value FROM meta WHERE key='later'").fetchone()[0] == "committed"


@pytest.mark.parametrize("filename", ["state #1.db", "state %23.db", "state ü space.db"])
def test_read_connection_preserves_literal_filenames(tmp_path, filename):
    store = SchedulerStore(tmp_path / filename)
    store.init()
    assert store.status()["jobs"]["total"] == 0


def test_unc_filename_is_not_a_sqlite_uri_authority():
    path = PureWindowsPath("//server/share/state #1 %23 ü.db")
    uri = urlsplit(_readonly_uri(path))
    assert uri.netloc == ""
    assert unquote(uri.path) == path.as_posix()
    assert uri.query == "mode=ro"


@pytest.mark.skipif(os.name != "posix", reason="POSIX double-root alias probes SQLite URI decoding without an SMB server")
def test_sqlite_decodes_unc_style_path_without_dropping_literal_characters(tmp_path):
    database = tmp_path / "state #1 %23 ü.db"
    SchedulerStore(database).init()
    uri = _readonly_uri(PureWindowsPath("/" + database.as_posix()))
    with sqlite3.connect(uri, uri=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TABLE forbidden (value TEXT)")
