"""Immutable execution metadata issued from a native admitted run, not its payload."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionContext:
    """Host-side context, not an authority grant or a user-serializable credential.

    SchedulerStore creates this under admission's write transaction. Plugins are
    trusted Python code; the security boundary is against configuration/payload
    impersonation, not against arbitrary code running inside the host process.
    """

    job_id: str
    scheduled_for: str
    run_id: str
    attempt: int
    claimed_by: str
    lease_expires_at: str
    started_at: str

    @property
    def occurrence_id(self) -> str:
        """One logical occurrence across abandoned retries, unlike attempt run_id."""
        material = json.dumps([self.job_id, self.scheduled_for], separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        return hashlib.sha256(material).hexdigest()
