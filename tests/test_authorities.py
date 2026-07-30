from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from ellmos_scheduler.authorities import (
    AuthorityConfigurationError,
    AuthorityResolution,
    AuthorityResolverRegistry,
    validate_authority_specs,
)
from ellmos_scheduler.cli import main
from ellmos_scheduler.executors import ExecutionResult, ExecutorRegistry
from ellmos_scheduler.service import SchedulerService
from ellmos_scheduler.store import SchedulerStore


UTC = timezone.utc


def _spec(path, *, required=True):
    return [
        {
            "id": "policy:runtime",
            "type": "policy",
            "resolver": "file",
            "required": required,
            "source": {"path": str(path)},
        }
    ]


def _empty_source(source):
    if source:
        raise AuthorityConfigurationError("source must be empty")
    return {}


def _catalog_source(source):
    if set(source) != {"entry"} or not isinstance(source["entry"], str):
        raise AuthorityConfigurationError("catalog source requires only entry")
    return {"entry": source["entry"]}


def _due_store(tmp_path, authorities, *, registry=None):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
    store.add_job(
        "authority-job",
        {"kind": "interval", "seconds": 60},
        "probe",
        {},
        now=base,
        authorities=authorities,
    )
    return store, base, registry


def test_required_file_is_read_back_and_receipted_without_raw_content(tmp_path):
    authority = tmp_path / "policy.md"
    raw = "current canonical policy\n"
    authority.write_text(raw, encoding="utf-8")
    seen = []
    executors = ExecutorRegistry(include_standard=False)
    executors.register(
        "probe",
        lambda payload, timeout: (
            seen.append(True) or ExecutionResult("succeeded", 0, "executed")
        ),
    )
    store, base, _ = _due_store(tmp_path, _spec(authority))

    result = SchedulerService(store, "worker", executors).tick(
        now=base.replace(minute=1)
    )

    assert result[0]["status"] == "succeeded"
    assert seen == [True]
    receipt = store.authority_receipt(result[0]["run_id"])
    item = receipt["authorities"][0]
    expected_hash = hashlib.sha256(authority.read_bytes()).hexdigest()
    assert item["authority_id"] == "policy:runtime"
    assert item["authority_type"] == "policy"
    assert item["requirement"] == "required"
    assert item["status"] == "resolved"
    assert item["sha256"] == item["readback_sha256"] == expected_hash
    assert item["origin"] == authority.resolve().as_uri()
    assert raw.strip() not in json.dumps(receipt)
    assert receipt["authority_set_sha256"]
    assert item["receipt_id"]
    assert store.recent_runs()[0]["started_at"] is not None


def test_required_unresolved_authority_fails_closed_before_executor(tmp_path):
    seen = []
    executors = ExecutorRegistry(include_standard=False)
    executors.register(
        "probe",
        lambda payload, timeout: (
            seen.append(True) or ExecutionResult("succeeded", 0)
        ),
    )
    store, base, _ = _due_store(tmp_path, _spec(tmp_path / "missing.md"))

    result = SchedulerService(store, "worker", executors).tick(
        now=base.replace(minute=1)
    )

    assert result[0]["status"] == "failed"
    assert result[0]["phase"] == "authority-resolution"
    assert seen == []
    receipt = store.authority_receipt(result[0]["run_id"])
    assert (
        receipt["authority_error"]
        == "required_authority_unresolved:policy:runtime:not_found"
    )
    assert receipt["authorities"][0]["error_code"] == "not_found"
    assert store.recent_runs()[0]["started_at"] is None


def test_optional_unresolved_authority_is_typed_and_does_not_block(tmp_path):
    executors = ExecutorRegistry(include_standard=False)
    executors.register("probe", lambda payload, timeout: ExecutionResult("succeeded", 0))
    store, base, _ = _due_store(
        tmp_path,
        _spec(tmp_path / "optional.md", required=False),
    )

    result = SchedulerService(store, "worker", executors).tick(
        now=base.replace(minute=1)
    )

    assert result[0]["status"] == "succeeded"
    item = store.authority_receipt(result[0]["run_id"])["authorities"][0]
    assert item["requirement"] == "optional"
    assert item["status"] == "unresolved"


def test_authority_set_hash_is_stable_but_receipt_id_is_per_run(tmp_path):
    authority = tmp_path / "workflow.md"
    authority.write_text("workflow v1\n", encoding="utf-8")
    registry = AuthorityResolverRegistry()
    first = registry.resolve(_spec(authority), run_id="run-1")
    second = registry.resolve(_spec(authority), run_id="run-2")
    assert first.set_sha256 == second.set_sha256
    assert first.receipts[0]["receipt_id"] != second.receipts[0]["receipt_id"]


def test_provider_neutral_custom_resolver_records_safe_origin():
    registry = AuthorityResolverRegistry(include_standard=False)
    registry.register(
        "catalog",
        lambda source: AuthorityResolution(
            "resolved",
            f"catalog://{source['entry']}",
            sha256="a" * 64,
            readback_sha256="a" * 64,
            byte_length=123,
        ),
        source_validator=_catalog_source,
    )
    result = registry.resolve(
        [
            {
                "id": "decision:approved",
                "type": "decision",
                "resolver": "catalog",
                "required": True,
                "source": {"entry": "approved-runtime-gate"},
            }
        ],
        run_id="run-1",
    )
    assert result.required_ok is True
    assert result.receipts[0]["origin"] == "catalog://approved-runtime-gate"


def test_custom_resolver_runs_while_claimed_and_service_uses_store_registry(tmp_path):
    observed_statuses = []
    registry = AuthorityResolverRegistry(include_standard=False)
    store = SchedulerStore(tmp_path / "scheduler.db", authority_registry=registry)

    def resolver(source):
        observed_statuses.append(store.recent_runs()[0]["status"])
        return AuthorityResolution(
            "resolved",
            "catalog://policy",
            sha256="a" * 64,
            readback_sha256="a" * 64,
            byte_length=1,
        )

    registry.register("catalog", resolver, source_validator=_empty_source)
    store.init()
    base = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
    store.add_job(
        "custom",
        {"kind": "interval", "seconds": 60},
        "noop",
        {},
        now=base,
        authorities=[
            {
                "id": "policy:custom",
                "type": "policy",
                "resolver": "catalog",
                "source": {},
            }
        ],
    )
    result = SchedulerService(store, "worker").tick(now=base.replace(minute=1))
    assert result[0]["status"] == "succeeded"
    assert observed_statuses == ["claimed"]


def test_resolver_exception_is_reduced_to_code_only_receipt(tmp_path):
    registry = AuthorityResolverRegistry(include_standard=False)

    def resolver(source):
        raise RuntimeError("Bearer TOPSECRET")

    registry.register("catalog", resolver, source_validator=_empty_source)
    store = SchedulerStore(tmp_path / "scheduler.db", authority_registry=registry)
    store.init()
    base = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
    store.add_job(
        "broken",
        {"kind": "interval", "seconds": 60},
        "noop",
        {},
        now=base,
        authorities=[
            {
                "id": "policy:broken",
                "type": "policy",
                "resolver": "catalog",
                "source": {},
            }
        ],
    )
    result = SchedulerService(store, "worker").tick(now=base.replace(minute=1))
    receipt = store.authority_receipt(result[0]["run_id"])
    serialized = json.dumps(receipt)
    assert result[0]["status"] == "failed"
    assert receipt["authorities"][0]["error_code"] == "resolver_failed"
    assert "TOPSECRET" not in serialized
    assert store.recent_runs()[0]["started_at"] is None


def test_custom_resolver_cannot_claim_resolved_without_hash_readback():
    registry = AuthorityResolverRegistry(include_standard=False)
    registry.register(
        "broken",
        lambda source: AuthorityResolution("resolved", "catalog://broken"),
        source_validator=_empty_source,
    )
    with pytest.raises(AuthorityConfigurationError, match="matching SHA-256"):
        registry.resolve(
            [
                {
                    "id": "policy:broken",
                    "type": "policy",
                    "resolver": "broken",
                    "source": {},
                }
            ],
            run_id="run-1",
        )


def test_custom_resolver_cannot_persist_credential_bearing_origin():
    registry = AuthorityResolverRegistry(include_standard=False)
    registry.register(
        "unsafe",
        lambda source: AuthorityResolution(
            "resolved",
            "https://authority.example/policy?token=raw",
            sha256="a" * 64,
            readback_sha256="a" * 64,
            byte_length=1,
        ),
        source_validator=_empty_source,
    )
    with pytest.raises(AuthorityConfigurationError, match="unsafe origin"):
        registry.resolve(
            [
                {
                    "id": "policy:unsafe",
                    "type": "policy",
                    "resolver": "unsafe",
                    "source": {},
                }
            ],
            run_id="run-1",
        )


def test_custom_resolver_error_code_cannot_contain_raw_exception_or_secret():
    registry = AuthorityResolverRegistry(include_standard=False)
    registry.register(
        "unsafe",
        lambda source: AuthorityResolution(
            "unresolved",
            "catalog://policy",
            error_code="Bearer TOPSECRET",
        ),
        source_validator=_empty_source,
    )
    with pytest.raises(AuthorityConfigurationError, match="invalid error code"):
        registry.resolve(
            [
                {
                    "id": "policy:unsafe",
                    "type": "policy",
                    "resolver": "unsafe",
                    "source": {},
                }
            ],
            run_id="run-1",
        )


@pytest.mark.parametrize(
    "source",
    [
        {"path": "policy.md", "token": "raw"},
        {"path": "policy.md", "api_key": "raw"},
        {"path": "policy.md", "nested": {"private-key": "raw"}},
    ],
)
def test_secret_bearing_authority_metadata_is_rejected(source):
    with pytest.raises(AuthorityConfigurationError, match="secret-bearing"):
        validate_authority_specs(
            [
                {
                    "id": "policy:test",
                    "type": "policy",
                    "resolver": "file",
                    "source": source,
                }
            ]
        )


def test_raw_authority_content_is_rejected_in_favor_of_a_reference():
    with pytest.raises(AuthorityConfigurationError, match="raw content"):
        validate_authority_specs(
            [
                {
                    "id": "policy:test",
                    "type": "policy",
                    "resolver": "file",
                    "source": {"path": "policy.md", "content": "do not persist me"},
                }
            ]
        )


def test_credential_like_uri_query_value_is_rejected_after_decoding():
    with pytest.raises(AuthorityConfigurationError, match="credential-like query"):
        validate_authority_specs(
            [
                {
                    "id": "policy:test",
                    "type": "policy",
                    "resolver": "file",
                    "source": {
                        "path": (
                            "https://authority.example/policy"
                            "?x=Bearer%20TOPSECRET"
                        )
                    },
                }
            ]
        )


def test_resolver_source_allowlist_blocks_secret_header_before_db_write(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    with pytest.raises(AuthorityConfigurationError, match="credential-like data"):
        store.add_job(
            "unsafe",
            {"kind": "interval", "seconds": 60},
            "noop",
            {},
            authorities=[
                {
                    "id": "policy:unsafe",
                    "type": "policy",
                    "resolver": "file",
                    "source": {
                        "path": str(tmp_path / "policy.md"),
                        "headers": ["Authorization: Bearer TOPSECRET"],
                    },
                }
            ],
        )
    assert store.list_jobs() == []


def test_init_migrates_legacy_database_and_existing_job_runs(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, schedule_json TEXT NOT NULL, executor TEXT NOT NULL,
            payload_json TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            generation INTEGER NOT NULL DEFAULT 1, next_due_at TEXT NOT NULL,
            lease_seconds INTEGER NOT NULL DEFAULT 900,
            timeout_seconds INTEGER NOT NULL DEFAULT 600,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
            scheduled_for TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 1,
            claimed_by TEXT NOT NULL, lease_expires_at TEXT NOT NULL,
            status TEXT NOT NULL, started_at TEXT, finished_at TEXT, exit_code INTEGER,
            output TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE controls (
            scope TEXT PRIMARY KEY, paused INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL DEFAULT '', steer_message TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO jobs VALUES (
            'legacy', '{"kind":"interval","seconds":60}', 'noop', '{}', 1, 1,
            '2026-07-30T10:01:00Z', 900, 600,
            '2026-07-30T10:00:00Z', '2026-07-30T10:00:00Z'
        );
        """
    )
    conn.commit()
    conn.close()

    store = SchedulerStore(path)
    store.init()
    job = store.list_jobs()[0]
    assert job["authorities_json"] == "[]"
    result = SchedulerService(store, "worker").tick(
        now=datetime(2026, 7, 30, 10, 1, tzinfo=UTC)
    )
    receipt = store.authority_receipt(result[0]["run_id"])
    assert result[0]["status"] == "succeeded"
    assert receipt["authorities"] == []
    assert receipt["authority_set_sha256"] == hashlib.sha256(b"[]").hexdigest()


def test_strict_runtime_mode_rejects_unmigrated_empty_authority_set(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
    store.add_job(
        "unmigrated",
        {"kind": "interval", "seconds": 60},
        "noop",
        {},
        now=base,
    )
    result = SchedulerService(
        store,
        "worker",
        require_authorities=True,
    ).tick(now=base.replace(minute=1))
    assert result[0]["status"] == "failed"
    assert result[0]["phase"] == "authority-resolution"
    receipt = store.authority_receipt(result[0]["run_id"])
    assert receipt["authority_error"] == "authority_configuration_required"


def test_cli_add_tick_and_authority_receipt_readback(tmp_path, capsys):
    db = tmp_path / "scheduler.db"
    authority = tmp_path / "rule.md"
    authority.write_text("rule\n", encoding="utf-8")
    assert (
        main(
            [
                "--db",
                str(db),
                "add",
                "--id",
                "cli-job",
                "--schedule",
                '{"kind":"interval","seconds":1}',
                "--executor",
                "noop",
                "--payload",
                "{}",
                "--authorities",
                json.dumps(_spec(authority)),
            ]
        )
        == 0
    )
    capsys.readouterr()
    store = SchedulerStore(db)
    job = store.list_jobs()[0]
    due = datetime.fromisoformat(job["next_due_at"].replace("Z", "+00:00"))
    result = SchedulerService(store, "cli-test").tick(now=due)
    run_id = result[0]["run_id"]

    assert main(["--db", str(db), "authority-receipt", run_id, "--json"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["run_id"] == run_id
    assert receipt["authorities"][0]["status"] == "resolved"


def test_set_authorities_updates_existing_job_generation(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    now = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)
    store.add_job(
        "job",
        {"kind": "interval", "seconds": 60},
        "noop",
        {},
        now=now,
    )
    store.set_authorities("job", _spec(tmp_path / "policy.md"), now=now)
    job = store.list_jobs()[0]
    assert job["generation"] == 2
    assert json.loads(job["authorities_json"])[0]["id"] == "policy:runtime"
