from __future__ import annotations

import hashlib
import json
import socket
import time
from collections.abc import Sequence
from datetime import datetime

from .authorities import (
    DEFAULT_AUTHORITY_REGISTRY,
    AuthorityConfigurationError,
    AuthorityResolverRegistry,
)
from .executors import DEFAULT_REGISTRY, ExecutorRegistry
from .store import SchedulerStore


class SchedulerService:
    def __init__(
        self,
        store: SchedulerStore,
        worker_id: str | None = None,
        registry: ExecutorRegistry | None = None,
        authority_registry: AuthorityResolverRegistry | None = None,
        require_authorities: bool = False,
    ):
        if not isinstance(require_authorities, bool):
            raise TypeError("require_authorities must be a boolean")
        self.store = store
        self.worker_id = worker_id or f"{socket.gethostname()}:{id(self)}"
        self.registry = registry or DEFAULT_REGISTRY
        self.authority_registry = (
            authority_registry
            or store.authority_registry
            or DEFAULT_AUTHORITY_REGISTRY
        )
        self.require_authorities = require_authorities

    def tick(
        self,
        *,
        now: datetime | None = None,
        limit: int = 20,
        job_ids: Sequence[str] | None = None,
    ) -> list[dict]:
        claimed = self.store.claim_due(
            self.worker_id,
            now=now,
            limit=limit,
            job_ids=job_ids,
        )
        results: list[dict] = []
        for job in claimed:
            run_id = job["run_id"]
            authority_error = ""
            try:
                authority_specs = json.loads(job.get("authorities_json") or "[]")
                if self.require_authorities and not authority_specs:
                    authority_error = "authority_configuration_required"
                    empty_hash = hashlib.sha256(b"[]").hexdigest()
                    self.store.record_authority_receipt(
                        run_id,
                        [],
                        empty_hash,
                        error=authority_error,
                    )
                    self.store.fail_claimed_run(
                        run_id,
                        error=authority_error,
                        now=now,
                    )
                    results.append(
                        {
                            "run_id": run_id,
                            "job_id": job["id"],
                            "status": "failed",
                            "exit_code": None,
                            "phase": "authority-resolution",
                        }
                    )
                    continue
                authority_set = self.authority_registry.resolve(
                    authority_specs,
                    run_id=run_id,
                )
            except (json.JSONDecodeError, AuthorityConfigurationError):
                authority_error = "invalid_authority_configuration"
                empty_hash = hashlib.sha256(b"[]").hexdigest()
                self.store.record_authority_receipt(
                    run_id,
                    [],
                    empty_hash,
                    error=authority_error,
                )
                self.store.fail_claimed_run(
                    run_id,
                    error=authority_error,
                    now=now,
                )
                results.append(
                    {
                        "run_id": run_id,
                        "job_id": job["id"],
                        "status": "failed",
                        "exit_code": None,
                        "phase": "authority-resolution",
                    }
                )
                continue
            receipt_error = (
                ""
                if authority_set.required_ok
                else f"required_authority_unresolved:{authority_set.error}"
            )
            self.store.record_authority_receipt(
                run_id,
                authority_set.receipts,
                authority_set.set_sha256,
                error=receipt_error,
            )
            if not authority_set.required_ok:
                authority_error = receipt_error
                self.store.fail_claimed_run(
                    run_id,
                    error=authority_error,
                    now=now,
                )
                results.append(
                    {
                        "run_id": run_id,
                        "job_id": job["id"],
                        "status": "failed",
                        "exit_code": None,
                        "phase": "authority-resolution",
                    }
                )
                continue
            self.store.start_run(run_id, now=now)
            result = self.registry.execute(
                job["executor"],
                json.loads(job["payload_json"]),
                int(job["timeout_seconds"]),
            )
            self.store.finish_run(
                run_id,
                result.status,
                exit_code=result.exit_code,
                output=result.output,
                error=result.error,
                now=now,
            )
            results.append(
                {
                    "run_id": run_id,
                    "job_id": job["id"],
                    "status": result.status,
                    "exit_code": result.exit_code,
                }
            )
        return results

    def serve(self, poll_seconds: float = 5.0) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        while True:
            self.tick()
            time.sleep(poll_seconds)
