from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .authorities import DEFAULT_AUTHORITY_REGISTRY
from .bach import import_legacy_jobs
from .executors import executor_names
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
    add.add_argument(
        "--authorities",
        default="[]",
        help="JSON authority-source array; required sources fail closed before execution",
    )
    add.add_argument("--lease-seconds", type=int, default=900)
    add.add_argument("--timeout-seconds", type=int, default=600)

    jobs = sub.add_parser("jobs")
    jobs.add_argument("--json", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    runs = sub.add_parser("runs")
    runs.add_argument("--limit", type=int, default=20)
    runs.add_argument("--json", action="store_true")
    executors = sub.add_parser("executors")
    executors.add_argument("--json", action="store_true")
    authority_resolvers = sub.add_parser("authority-resolvers")
    authority_resolvers.add_argument("--json", action="store_true")
    authority_receipt = sub.add_parser("authority-receipt")
    authority_receipt.add_argument("run_id")
    authority_receipt.add_argument("--json", action="store_true")
    set_authorities = sub.add_parser("set-authorities")
    set_authorities.add_argument("job_id")
    set_authorities.add_argument("--authorities", required=True)

    import_bach = sub.add_parser("import-bach")
    import_bach.add_argument("--source-db", type=Path, required=True)
    import_bach.add_argument("--bach-root", type=Path)
    import_bach.add_argument("--timezone", default="UTC")
    import_bach.add_argument("--dry-run", action="store_true")
    import_bach.add_argument("--json", action="store_true")

    for name in ("enable", "disable"):
        item = sub.add_parser(name)
        item.add_argument("job_id")

    for name in ("pause", "resume"):
        item = sub.add_parser(name)
        item.add_argument("--job")
        item.add_argument("--reason", default="")

    tick = sub.add_parser("tick")
    tick.add_argument("--json", action="store_true")
    tick.add_argument("--require-authorities", action="store_true")
    serve = sub.add_parser("serve")
    serve.add_argument("--poll-seconds", type=float, default=5.0)
    serve.add_argument("--require-authorities", action="store_true")
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
    if args.command == "executors":
        _print(list(executor_names()), args.json)
        return 0
    if args.command == "authority-resolvers":
        _print(list(DEFAULT_AUTHORITY_REGISTRY.names()), args.json)
        return 0
    store = SchedulerStore(args.db)
    if args.command == "import-bach":
        report = import_legacy_jobs(
            args.source_db,
            store,
            timezone_name=args.timezone,
            bach_root=args.bach_root,
            dry_run=args.dry_run,
        )
        _print(report.to_dict(), args.json)
        return 0
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
            authorities=json.loads(args.authorities),
        )
        print(args.id)
    elif args.command == "jobs":
        _print(store.list_jobs(), args.json)
    elif args.command == "status":
        _print(store.status(), args.json)
    elif args.command == "runs":
        _print(store.recent_runs(args.limit), args.json)
    elif args.command == "authority-receipt":
        _print(store.authority_receipt(args.run_id), args.json)
    elif args.command == "set-authorities":
        store.set_authorities(args.job_id, json.loads(args.authorities))
        print(args.job_id)
    elif args.command in {"enable", "disable"}:
        store.set_enabled(args.job_id, args.command == "enable")
        print(args.job_id)
    elif args.command in {"pause", "resume"}:
        scope = f"job:{args.job}" if args.job else "global"
        store.set_pause(scope, args.command == "pause", args.reason)
        print(scope)
    elif args.command == "tick":
        _print(
            SchedulerService(
                store,
                require_authorities=args.require_authorities,
            ).tick(),
            args.json,
        )
    elif args.command == "serve":
        SchedulerService(
            store,
            require_authorities=args.require_authorities,
        ).serve(args.poll_seconds)
    return 0
