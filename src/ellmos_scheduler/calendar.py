"""Calendar view of native one-shot agent definitions; no separate event store."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .definitions import AgentTriggers, DefinitionConflict
from .schedules import once_at


class AgentCalendar:
    """Both calendar and agent editors address the same definition ID/version.

    Personal appointments remain outside this projection. No call starts a worker.
    Configuration writes retain the scheduler's CAS, tombstone and run semantics.
    """

    def __init__(self, store: Any):
        self.triggers = AgentTriggers(store)

    @staticmethod
    def project(definition: dict) -> dict:
        if definition['schedule'].get('kind') != 'once':
            raise ValueError('definition is not an agent appointment')
        return {
            'id': definition['id'],
            'definition_id': definition['id'],
            'version': definition['version'],
            'agent_id': definition['agent_id'],
            'at': once_at(definition['schedule']).isoformat(),
            'enabled': definition['enabled'],
            'deleted': definition['deleted'],
            'source': 'agent_trigger_definition',
        }

    def list(self, *, agent_id: str | None = None) -> list[dict]:
        return [self.project(d) for d in self.triggers.list(agent_id=agent_id)
                if d['schedule'].get('kind') == 'once']

    def get(self, identifier: str) -> dict:
        return self.project(self.triggers.get(identifier))

    def create(self, identifier: str, *, at: str, agent_id: str, executor: str,
               enabled: bool = False, payload: dict | None = None,
               authorities: list | None = None, now: datetime | None = None) -> dict:
        return self.project(self.triggers.create(
            identifier, agent_id=agent_id, schedule={'kind': 'once', 'at': at},
            executor=executor, enabled=enabled, payload=payload,
            authorities=authorities, now=now))

    def update(self, identifier: str, *, expected_version: int, at: str | None = None,
               enabled: bool | None = None, now: datetime | None = None) -> dict:
        current = self.triggers.get(identifier)
        self.project(current)
        if current['version'] != expected_version:
            raise DefinitionConflict('stale calendar appointment')
        changes = {}
        if at is not None:
            changes['schedule'] = {'kind': 'once', 'at': at}
        if enabled is not None:
            changes['enabled'] = enabled
        return self.project(self.triggers.update(
            identifier, expected_version=expected_version, changes=changes, now=now))

    def delete(self, identifier: str, *, expected_version: int,
               now: datetime | None = None) -> dict:
        current = self.triggers.get(identifier)
        self.project(current)
        if current['version'] != expected_version:
            raise DefinitionConflict('stale calendar appointment')
        return self.project(self.triggers.delete(
            identifier, expected_version=expected_version, now=now))
