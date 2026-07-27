from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .service import SchedulerService
from .store import SchedulerStore


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="ellmos-scheduler")
    result.add_argument(
        "--db",
        type=Path,
        default=Path.home() / ".ellmos" / "scheduler.db",
        help="SQLite state path",
    )
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("init")

    add = sub.add_parser("add")
    add.add_argument("--id", required=True)
    add.add_argument("--schedule", required=True, help="JSON schedule object")
    add.add_argument("--executor", required=True)
    add.add_argument("--payload", required=True, help="JSON payload object")
    add.add_argument("--lease-seconds", type=int, default=900)
    add.add_argument("--timeout-seconds", type=int, default=600)

    jobs = sub.add_parser("jobs")
    jobs.add_argument("--json", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    runs = sub.add_parser("runs")
    runs.add_argument("--limit", type=int, default=20)
    runs.add_argument("--json", action="store_true")

    for name in ("enable", "disable"):
        item = sub.add_parser(name)
        item.add_argument("job_id")

    for name in ("pause", "resume"):
        item = sub.add_parser(name)
        item.add_argument("--job")
        item.add_argument("--reason", default="")

    tick = sub.add_parser("tick")
    tick.add_argument("--json", action="store_true")
    serve = sub.add_parser("serve")
    serve.add_argument("--poll-seconds", type=float, default=5.0)
    return result


def _print(value: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    elif isinstance(value, list):
        for item in value:
            print(item)
    else:
        print(value)


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    store = SchedulerStore(args.db)
    store.init()
    if args.command == "init":
        print(args.db)
    elif args.command == "add":
        store.add_job(
            args.id,
            json.loads(args.schedule),
            args.executor,
            json.loads(args.payload),
            lease_seconds=args.lease_seconds,
            timeout_seconds=args.timeout_seconds,
        )
        print(args.id)
    elif args.command == "jobs":
        _print(store.list_jobs(), args.json)
    elif args.command == "status":
        _print(store.status(), args.json)
    elif args.command == "runs":
        _print(store.recent_runs(args.limit), args.json)
    elif args.command in {"enable", "disable"}:
        store.set_enabled(args.job_id, args.command == "enable")
        print(args.job_id)
    elif args.command in {"pause", "resume"}:
        scope = f"job:{args.job}" if args.job else "global"
        store.set_pause(scope, args.command == "pause", args.reason)
        print(scope)
    elif args.command == "tick":
        _print(SchedulerService(store).tick(), args.json)
    elif args.command == "serve":
        SchedulerService(store).serve(args.poll_seconds)
    return 0
