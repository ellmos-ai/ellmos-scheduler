from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ellmos_scheduler import adapters
from ellmos_scheduler.cli import _print, main
from ellmos_scheduler.executors import (
    ExecutionResult,
    ExecutorRegistry,
    command_executor,
    executor_names,
)
from ellmos_scheduler.service import SchedulerService
from ellmos_scheduler.store import SchedulerStore


UTC = timezone.utc


def test_standard_executor_names_are_registered():
    assert executor_names() == ("coma", "command", "marblerun", "noop", "subprocess")


def test_executor_listing_does_not_create_scheduler_database(tmp_path, capsys):
    target = tmp_path / "state.db"
    assert main(["--db", str(target), "executors", "--json"]) == 0
    assert not target.exists()
    assert json.loads(capsys.readouterr().out) == [
        "coma",
        "command",
        "marblerun",
        "noop",
        "subprocess",
    ]


def test_registry_is_isolated_and_rejects_implicit_overwrite():
    first = ExecutorRegistry(include_standard=False)
    second = ExecutorRegistry(include_standard=False)
    executor = lambda payload, timeout: ExecutionResult("succeeded")  # noqa: E731
    replacement = lambda payload, timeout: ExecutionResult("failed")  # noqa: E731

    first.register("custom", executor)
    assert first.names() == ("custom",)
    assert second.names() == ()
    with pytest.raises(ValueError, match="already registered"):
        first.register("custom", replacement)
    first.register("custom", replacement, replace=True)
    assert first.execute("custom", {}, 1).status == "failed"
    with pytest.raises(ValueError, match="already registered"):
        ExecutorRegistry({"noop": replacement})


def test_registry_contains_adapter_exception_and_invalid_result():
    registry = ExecutorRegistry(include_standard=False)

    def broken(payload, timeout):
        raise RuntimeError("boom")

    registry.register("broken", broken)
    registry.register("invalid", lambda payload, timeout: {"success": True})
    assert "RuntimeError: boom" in registry.execute("broken", {}, 1).error
    assert "invalid result" in registry.execute("invalid", {}, 1).error


def test_scheduler_service_uses_injected_registry(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    base = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    store.add_job(
        "custom-job",
        {"kind": "interval", "seconds": 60},
        "custom",
        {"value": 42},
        now=base,
    )
    seen = []
    registry = ExecutorRegistry(include_standard=False)
    registry.register(
        "custom",
        lambda payload, timeout: (
            seen.append((payload, timeout))
            or ExecutionResult("succeeded", exit_code=0, output="custom")
        ),
    )

    result = SchedulerService(store, "worker", registry).tick(
        now=datetime(2026, 7, 28, 10, 1, tzinfo=UTC)
    )

    assert result[0]["status"] == "succeeded"
    assert seen == [({"value": 42}, 600)]
    assert store.recent_runs()[0]["output"] == "custom"


def test_subprocess_executor_alias_runs_argv():
    registry = ExecutorRegistry()
    result = registry.execute(
        "subprocess",
        {"argv": [sys.executable, "-c", "print('adapter-ok')"]},
        10,
    )
    assert result.status == "succeeded"
    assert result.output.strip() == "adapter-ok"


def test_command_executor_sets_explicit_utf8_python_contract():
    result = command_executor(
        {
            "argv": [
                sys.executable,
                "-c",
                (
                    "import os, sys; "
                    "print(os.environ['PYTHONIOENCODING']); "
                    "print(sys.stdout.encoding); "
                    "print('ä')"
                ),
            ]
        },
        10,
    )
    assert result.status == "succeeded"
    assert "\ufffd" not in result.output
    assert result.output.splitlines() == ["utf-8:strict", "utf-8", "ä"]


def test_command_executor_fails_closed_on_output_encoding_mismatch():
    result = command_executor(
        {
            "argv": [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(bytes([0xe4]))",
            ]
        },
        10,
    )
    assert result.status == "failed"
    assert result.exit_code == 0
    assert result.output == ""
    assert "not valid utf-8" in result.error


def test_command_executor_supports_explicit_legacy_output_encoding():
    result = command_executor(
        {
            "argv": [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(bytes([0xe4]))",
            ],
            "output_encoding": "cp1252",
        },
        10,
    )
    assert result == ExecutionResult("succeeded", 0, "ä", "")


def test_command_executor_supports_explicit_utf16_output_encoding():
    result = command_executor(
        {
            "argv": [sys.executable, "-c", "print('gültig')"],
            "output_encoding": "utf-16",
        },
        10,
    )
    assert result.status == "succeeded"
    assert result.output.strip() == "gültig"


def test_command_executor_decodes_valid_timeout_partial_output():
    result = command_executor(
        {
            "argv": [
                sys.executable,
                "-c",
                (
                    "import sys, time; "
                    "sys.stdout.write('part'); "
                    "sys.stdout.flush(); "
                    "time.sleep(3)"
                ),
            ]
        },
        1,
    )
    assert result.status == "timed_out"
    assert result.output == "part"
    assert result.error == ""


def test_command_executor_fails_closed_on_invalid_timeout_partial_output():
    result = command_executor(
        {
            "argv": [
                sys.executable,
                "-c",
                (
                    "import sys, time; "
                    "sys.stdout.buffer.write(bytes([0xff])); "
                    "sys.stdout.flush(); "
                    "time.sleep(3)"
                ),
            ]
        },
        1,
    )
    assert result.status == "timed_out"
    assert result.output == ""
    assert "not valid utf-8" in result.error


def test_command_executor_rejects_conflicting_python_output_encoding():
    result = command_executor(
        {
            "argv": [sys.executable, "-c", "print('never runs')"],
            "env": {"PYTHONIOENCODING": "cp1252"},
        },
        10,
    )
    assert result.status == "failed"
    assert result.error == "PYTHONIOENCODING conflicts with output_encoding"


@pytest.mark.parametrize("encoding", ("not-a-real-codec", "base64_codec", "idna"))
def test_command_executor_rejects_non_text_output_encoding(encoding):
    result = command_executor(
        {
            "argv": [sys.executable, "-c", "print('never runs')"],
            "output_encoding": encoding,
        },
        10,
    )
    assert result.status == "failed"
    assert result.error == "output_encoding must name a supported text encoding"


@pytest.mark.parametrize("error_handler", ("ignore", "replace", "backslashreplace"))
def test_command_executor_rejects_lossy_python_error_handler(error_handler):
    result = command_executor(
        {
            "argv": [sys.executable, "-c", "print('never runs')"],
            "env": {"PYTHONIOENCODING": f"utf-8:{error_handler}"},
        },
        10,
    )
    assert result.status == "failed"
    assert result.error == "PYTHONIOENCODING error handler must be strict"


def test_command_executor_rejects_mixed_case_python_encoding_duplicates():
    result = command_executor(
        {
            "argv": [sys.executable, "-c", "print('never runs')"],
            "env": {
                "PYTHONIOENCODING": "utf-8:strict",
                "pythonioencoding": "cp1252:ignore",
            },
        },
        10,
    )
    assert result.status == "failed"
    assert result.error == "env must not contain multiple PYTHONIOENCODING variants"


def test_command_executor_normalizes_lowercase_python_encoding_key():
    result = command_executor(
        {
            "argv": [
                sys.executable,
                "-c",
                "import os; print(os.environ['PYTHONIOENCODING']); print('gültig')",
            ],
            "env": {"pythonioencoding": "utf-8:strict"},
        },
        10,
    )
    assert result.status == "succeeded"
    assert result.output.splitlines() == ["utf-8:strict", "gültig"]


def test_json_output_is_ascii_safe_and_round_trips(capsys):
    value = {"output": "gültig \ufffd"}
    _print(value, True)
    rendered = capsys.readouterr().out
    assert rendered.isascii()
    assert json.loads(rendered) == value


def test_json_output_is_ascii_safe_in_real_cp1252_child():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252:strict"
    source_root = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (source_root, env.get("PYTHONPATH")) if value
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from ellmos_scheduler.cli import _print; "
                "_print({'output': 'gültig'}, True)"
            ),
        ],
        env=env,
        capture_output=True,
        text=False,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stderr == b""
    assert completed.stdout.isascii()
    assert json.loads(completed.stdout.decode("ascii")) == {"output": "gültig"}


def test_coma_executor_uses_public_adapter_seam(monkeypatch):
    calls = {}

    class FakeSpawner:
        def __init__(self, adapter, *, allow_unverified=False):
            calls["spawner"] = (adapter, allow_unverified)

        def run(self, prompt, **options):
            calls["run"] = (prompt, options)
            return {
                "success": True,
                "returncode": 0,
                "output": "done",
                "stderr": "",
                "timed_out": False,
            }

    def fake_get_adapter(name, **options):
        calls["adapter"] = (name, options)
        return object()

    module = types.ModuleType("coma")
    module.Spawner = FakeSpawner
    module.get_adapter = fake_get_adapter
    monkeypatch.setitem(sys.modules, "coma", module)

    result = adapters.coma_executor(
        {
            "provider": "codex",
            "prompt": "Do work",
            "cwd": "C:\\work",
            "adapter_options": {"model": "gpt-test"},
            "run_options": {"effort": "high"},
        },
        123,
    )

    assert result == ExecutionResult("succeeded", 0, "done", "")
    assert calls["adapter"] == (
        "codex",
        {"model": "gpt-test", "timeout": 123, "cwd": "C:\\work"},
    )
    assert calls["run"] == ("Do work", {"effort": "high", "timeout": 123})


def test_coma_timeout_is_normalized(monkeypatch):
    class FakeSpawner:
        def __init__(self, adapter, *, allow_unverified=False):
            pass

        def run(self, prompt, **options):
            return {
                "success": False,
                "returncode": -1,
                "stderr": "TIMEOUT",
                "timed_out": True,
            }

    module = types.ModuleType("coma")
    module.Spawner = FakeSpawner
    module.get_adapter = lambda name, **options: object()
    monkeypatch.setitem(sys.modules, "coma", module)
    assert adapters.coma_executor({"prompt": "wait"}, 5).status == "timed_out"


def test_coma_allow_unverified_requires_json_boolean():
    result = adapters.coma_executor(
        {"prompt": "wait", "allow_unverified": "false"},
        5,
    )
    assert result.status == "failed"
    assert result.error == "allow_unverified must be a boolean"


def test_coma_result_booleans_are_not_coerced(monkeypatch):
    class FakeSpawner:
        def __init__(self, adapter, *, allow_unverified=False):
            pass

        def run(self, prompt, **options):
            return {
                "success": "false",
                "returncode": 1,
                "timed_out": False,
            }

    module = types.ModuleType("coma")
    module.Spawner = FakeSpawner
    module.get_adapter = lambda name, **options: object()
    monkeypatch.setitem(sys.modules, "coma", module)
    result = adapters.coma_executor({"prompt": "wait"}, 5)
    assert result.status == "failed"
    assert "must be booleans" in result.error


def test_marble_run_adapter_builds_safe_cli_argv(monkeypatch):
    captured = {}

    def fake_subprocess(payload, timeout):
        captured.update(payload)
        captured["timeout"] = timeout
        return ExecutionResult("succeeded", 0)

    monkeypatch.setattr(adapters, "command_executor", fake_subprocess)
    result = adapters.marblerun_executor(
        {
            "chain": "review-chain",
            "background": True,
            "cwd": "C:\\marblerun",
            "env": {"MODE": "test"},
        },
        45,
    )

    assert result.status == "succeeded"
    assert captured["argv"] == [
        sys.executable,
        "-m",
        "llmauto",
        "chain",
        "start",
        "review-chain",
        "--bg",
    ]
    assert captured["cwd"] == "C:\\marblerun"
    assert captured["env"] == {"MODE": "test"}
    assert captured["timeout"] == 45


def test_marble_run_background_requires_json_boolean():
    result = adapters.marblerun_executor(
        {"chain": "review-chain", "background": "false"},
        45,
    )
    assert result.status == "failed"
    assert result.error == "background must be a boolean"


def test_marble_run_chain_name_rejects_options_and_path_traversal():
    for chain in ("--help", "..\\outside", "../outside", "name\nother"):
        result = adapters.marblerun_executor({"chain": chain}, 45)
        assert result.status == "failed"
        assert "unsupported characters" in result.error


def test_executor_payload_round_trips_through_store(tmp_path):
    store = SchedulerStore(tmp_path / "scheduler.db")
    store.init()
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    payload = {"provider": "codex", "prompt": "hello"}
    store.add_job(
        "coma-job",
        {"kind": "interval", "seconds": 60},
        "coma",
        payload,
        now=now,
    )
    assert json.loads(store.list_jobs()[0]["payload_json"]) == payload
