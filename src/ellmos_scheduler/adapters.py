from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from typing import Any

from .executors import ExecutionResult, command_executor


_CHAIN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _object(
    value: Any, label: str
) -> tuple[dict[str, Any] | None, ExecutionResult | None]:
    if value is None:
        return {}, None
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        return None, ExecutionResult("failed", error=f"{label} must be an object")
    return dict(value), None


def coma_executor(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    """Run a provider prompt through COMA's public adapter/Spawner seam."""
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return ExecutionResult(
            "failed", error="COMA executor requires a non-empty prompt"
        )
    provider = payload.get("provider", payload.get("adapter", "claude"))
    if not isinstance(provider, str) or not provider:
        return ExecutionResult(
            "failed", error="COMA provider must be a non-empty string"
        )
    adapter_options, error = _object(payload.get("adapter_options"), "adapter_options")
    if error:
        return error
    run_options, error = _object(payload.get("run_options"), "run_options")
    if error:
        return error
    assert adapter_options is not None and run_options is not None
    cwd = payload.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        return ExecutionResult("failed", error="cwd must be a string")
    allow_unverified = payload.get("allow_unverified", False)
    if not isinstance(allow_unverified, bool):
        return ExecutionResult("failed", error="allow_unverified must be a boolean")
    adapter_options["timeout"] = timeout_seconds
    if cwd is not None:
        adapter_options["cwd"] = cwd
    run_options["timeout"] = timeout_seconds
    if "log_file" in payload:
        run_options["log_file"] = payload["log_file"]
    try:
        from coma import Spawner, get_adapter
    except ImportError as exc:
        return ExecutionResult("failed", error=f"COMA is not installed: {exc}")
    try:
        adapter = get_adapter(provider, **adapter_options)
        spawner = Spawner(
            adapter,
            allow_unverified=allow_unverified,
        )
        raw = spawner.run(prompt, **run_options)
    except Exception as exc:
        return ExecutionResult("failed", error=f"COMA execution failed: {exc}")
    if not isinstance(raw, Mapping):
        return ExecutionResult("failed", error="COMA returned an invalid result")
    success = raw.get("success")
    timed_out_value = raw.get("timed_out", False)
    if not isinstance(success, bool) or not isinstance(timed_out_value, bool):
        return ExecutionResult(
            "failed",
            error="COMA result success/timed_out fields must be booleans",
        )
    returncode = raw.get("returncode")
    exit_code = returncode if isinstance(returncode, int) else None
    timed_out = timed_out_value or exit_code == -1
    if timed_out:
        status = "timed_out"
    else:
        status = "succeeded" if success else "failed"
    return ExecutionResult(
        status,
        exit_code=exit_code,
        output=str(raw.get("output") or ""),
        error=str(raw.get("stderr") or ""),
    )


def marblerun_executor(
    payload: dict[str, Any], timeout_seconds: int
) -> ExecutionResult:
    """Start a MarbleRun chain through its stable, argv-only CLI contract."""
    chain = payload.get("chain")
    if not isinstance(chain, str) or not chain.strip():
        return ExecutionResult(
            "failed",
            error="MarbleRun executor requires a non-empty chain name",
        )
    if not _CHAIN_NAME.fullmatch(chain):
        return ExecutionResult(
            "failed",
            error="MarbleRun chain name contains unsupported characters",
        )
    background = payload.get("background", False)
    if not isinstance(background, bool):
        return ExecutionResult("failed", error="background must be a boolean")
    command_payload: dict[str, Any] = {
        "argv": [sys.executable, "-m", "llmauto", "chain", "start", chain],
    }
    if background:
        command_payload["argv"].append("--bg")
    for key in ("cwd", "env"):
        if key in payload:
            command_payload[key] = payload[key]
    return command_executor(command_payload, timeout_seconds)
