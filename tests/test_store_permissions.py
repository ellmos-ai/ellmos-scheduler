"""New POSIX state must be private even under a common permissive umask."""
from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import contextmanager

import pytest

from ellmos_scheduler.store import SchedulerStore

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits; no Windows ACL claim")


@contextmanager
def public_umask():
    previous = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.mark.parametrize("depth", [1, 3])
def test_new_state_and_every_new_parent_are_private(tmp_path, depth):
    directory = tmp_path
    parents = []
    for number in range(depth):
        directory = directory / f"state-{number}"
        parents.append(directory)
    database = directory / "scheduler.db"
    with public_umask():
        SchedulerStore(database).init()
    assert [stat.S_IMODE(path.stat().st_mode) for path in parents] == [0o700] * depth
    assert stat.S_IMODE(database.stat().st_mode) == 0o600


def test_live_wal_and_shared_memory_are_private(tmp_path):
    database = tmp_path / "scheduler.db"
    with public_umask():
        store = SchedulerStore(database)
        store.init()
        with store.connect() as conn:
            conn.execute("INSERT INTO meta (key,value) VALUES ('private','synthetic-output')")
            for path in (database, database.with_name("scheduler.db-wal"), database.with_name("scheduler.db-shm")):
                assert path.is_file(), path
                assert stat.S_IMODE(path.stat().st_mode) == 0o600, path


def test_existing_shared_parent_permissions_are_preserved(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    database = shared / "scheduler.db"
    with public_umask():
        SchedulerStore(database).init()
        SchedulerStore(database).init()
    assert stat.S_IMODE(shared.stat().st_mode) == 0o755
    assert stat.S_IMODE(database.stat().st_mode) == 0o600


def test_reopening_preserves_existing_data(tmp_path):
    database = tmp_path / "scheduler.db"
    with public_umask():
        store = SchedulerStore(database)
        store.init()
        with store.connect() as conn:
            conn.execute("INSERT INTO meta (key,value) VALUES ('retained','value')")
        store.init()
        with store.connect() as conn:
            assert conn.execute("SELECT value FROM meta WHERE key='retained'").fetchone()[0] == "value"


def test_database_is_private_before_sqlite_can_write_payloads(tmp_path, monkeypatch):
    database = tmp_path / "scheduler.db"
    original = sqlite3.connect
    observed = []

    def connect(path):
        observed.append(stat.S_IMODE(database.stat().st_mode))
        return original(path)

    monkeypatch.setattr(sqlite3, "connect", connect)
    with public_umask():
        SchedulerStore(database).init()
    assert observed == [0o600]


def test_memory_database_does_not_create_a_literal_state_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with SchedulerStore(":memory:").connect() as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    assert not (tmp_path / ":memory:").exists()
