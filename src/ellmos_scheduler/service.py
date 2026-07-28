from __future__ import annotations

import json
import socket
import time
from datetime import datetime

from .executors import DEFAULT_REGISTRY, ExecutorRegistry
from .store import SchedulerStore


class SchedulerService:
    def __init__(
        self,
        store: SchedulerStore,
        worker_id: str | None = None,
        registry: ExecutorRegistry | None = None,
    ):
        self.store = store
        self.worker_id = worker_id or f"{socket.gethostname()}:{id(self)}"
        self.registry = registry or DEFAULT_REGISTRY

    def tick(self, *, now: datetime | None = None, limit: int = 20) -> list[dict]:
        claimed = self.store.claim_due(self.worker_id, now=now, limit=limit)
        results: list[dict] = []
        for job in claimed:
            run_id = job["run_id"]
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
