from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from ellmos_scheduler import AgentTriggers, DefinitionConflict, SchedulerStore
from ellmos_scheduler.calendar import AgentCalendar

AT = datetime(2026, 12, 1, 12, tzinfo=timezone.utc)


def test_calendar_and_agent_views_share_identity_versions_and_tombstone(tmp_path):
    store = SchedulerStore(tmp_path / 'state.db')
    store.init()
    calendar, agents = AgentCalendar(store), AgentTriggers(store)
    event = calendar.create('appointment', at=AT.isoformat(), agent_id='a', executor='noop', now=AT)
    assert event['id'] == event['definition_id'] == 'appointment'
    assert agents.get('appointment')['enabled'] is False
    agents.update('appointment', expected_version=1, changes={'enabled': True}, now=AT)
    assert calendar.get('appointment')['version'] == 2
    with pytest.raises(DefinitionConflict):
        calendar.update('appointment', expected_version=1, at=AT.isoformat(), now=AT)
    later = AT + timedelta(days=1)
    calendar.update('appointment', expected_version=2, at=later.isoformat(), now=AT)
    assert agents.get('appointment')['schedule']['at'] == later.isoformat()
    assert store.claim_due('worker', now=AT) == []
    calendar.delete('appointment', expected_version=3, now=AT)
    assert agents.get('appointment')['deleted'] is True
    assert calendar.list() == []
    assert store.claim_due('worker', now=later) == []


def test_recurring_definition_cannot_be_changed_or_deleted_through_calendar(tmp_path):
    store = SchedulerStore(tmp_path / 'state.db')
    store.init()
    agents, calendar = AgentTriggers(store), AgentCalendar(store)
    agents.create('routine', agent_id='a', schedule={'kind': 'interval', 'seconds': 60}, executor='noop', now=AT)
    assert calendar.list() == []
    with pytest.raises(ValueError):
        calendar.update('routine', expected_version=1, at=AT.isoformat(), now=AT)
    with pytest.raises(ValueError):
        calendar.delete('routine', expected_version=1, now=AT)
    assert agents.get('routine')['version'] == 1


def test_calendar_read_does_not_create_missing_database(tmp_path):
    path = tmp_path / 'missing' / 'state.db'
    calendar = AgentCalendar(SchedulerStore(path))
    with pytest.raises(sqlite3.OperationalError):
        calendar.list()
    assert not path.exists()


def test_calendar_rejects_naive_appointment_without_creating_definition(tmp_path):
    store = SchedulerStore(tmp_path / 'state.db')
    store.init()
    calendar = AgentCalendar(store)
    with pytest.raises(ValueError):
        calendar.create('bad', at='2026-12-01T12:00:00', agent_id='a', executor='noop')
    assert calendar.list() == []
