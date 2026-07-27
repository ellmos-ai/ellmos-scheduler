from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    exit_code: int | None = None
    output: str = ""
    error: str = ""


Executor = Callable[[dict[str, Any], int], ExecutionResult]
_EXECUTORS: dict[str, Executor] = {}


def register_executor(name: str, executor: Executor) -> None:
    if not name or name in {"command", "noop"}:
        raise ValueError("reserved or empty executor name")
    _EXECUTORS[name] = executor


def command_executor(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    argv = payload.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
        return ExecutionResult("failed", error="command executor requires a non-empty argv list")
    raw_env = payload.get("env", {})
    if not isinstance(raw_env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in raw_env.items()
    ):
        return ExecutionResult("failed", error="env must be a string-to-string object")
    env = os.environ.copy()
    env.update(raw_env)
    try:
        completed = subprocess.run(
            argv,
            cwd=payload.get("cwd"),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecutionResult(
            "timed_out",
            output=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            error=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
        )
    except OSError as exc:
        return ExecutionResult("failed", error=str(exc))
    status = "succeeded" if completed.returncode == 0 else "failed"
    return ExecutionResult(status, completed.returncode, completed.stdout, completed.stderr)


def noop_executor(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    del timeout_seconds
    if payload.get("fail"):
        return ExecutionResult("failed", exit_code=1, error="requested noop failure")
    return ExecutionResult("succeeded", exit_code=0, output=str(payload.get("message", "noop")))


def execute(name: str, payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    if name == "command":
        return command_executor(payload, timeout_seconds)
    if name == "noop":
        return noop_executor(payload, timeout_seconds)
    executor = _EXECUTORS.get(name)
    if executor is None:
        return ExecutionResult("failed", error=f"unknown executor: {name}")
    return executor(payload, timeout_seconds)
