from __future__ import annotations

import os
import re
import subprocess
from codecs import lookup
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    exit_code: int | None = None
    output: str = ""
    error: str = ""


Executor = Callable[[dict[str, Any], int], ExecutionResult]
_EXECUTOR_NAME = re.compile(r"^[a-z][a-z0-9_.-]*$")
_STREAM_OUTPUT_ENCODINGS = frozenset(
    {
        "ascii",
        "cp437",
        "cp850",
        "cp1252",
        "iso8859-1",
        "utf-8",
        "utf-8-sig",
        "utf-16",
        "utf-16-be",
        "utf-16-le",
    }
)


def _output_encoding(payload: dict[str, Any]) -> str | None:
    value = payload.get("output_encoding", "utf-8")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        codec = lookup(value)
    except LookupError:
        return None
    if codec.name not in _STREAM_OUTPUT_ENCODINGS:
        return None
    return codec.name


def _decode_stream(value: bytes | str | None, encoding: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode(encoding, errors="strict")


def command_executor(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    """Execute an argv list and fail closed if audit output cannot be decoded."""
    argv = payload.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(v, str) for v in argv)
    ):
        return ExecutionResult(
            "failed", error="subprocess executor requires a non-empty argv list"
        )
    raw_env = payload.get("env", {})
    if not isinstance(raw_env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in raw_env.items()
    ):
        return ExecutionResult("failed", error="env must be a string-to-string object")
    cwd = payload.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        return ExecutionResult("failed", error="cwd must be a string")
    output_encoding = _output_encoding(payload)
    if output_encoding is None:
        return ExecutionResult(
            "failed", error="output_encoding must name a supported text encoding"
        )
    python_encoding_items = [
        (key, value)
        for key, value in raw_env.items()
        if key.casefold() == "pythonioencoding"
    ]
    if len(python_encoding_items) > 1:
        return ExecutionResult(
            "failed",
            error="env must not contain multiple PYTHONIOENCODING variants",
        )
    configured_python_encoding = (
        python_encoding_items[0][1] if python_encoding_items else None
    )
    if configured_python_encoding is not None:
        configured_parts = configured_python_encoding.split(":", 1)
        configured_python_encoding = configured_parts[0]
        configured_error_handler = (
            configured_parts[1].strip().lower() if len(configured_parts) == 2 else "strict"
        )
        if configured_error_handler != "strict":
            return ExecutionResult(
                "failed",
                error="PYTHONIOENCODING error handler must be strict",
            )
        if (
            _output_encoding({"output_encoding": configured_python_encoding})
            != output_encoding
        ):
            return ExecutionResult(
                "failed",
                error="PYTHONIOENCODING conflicts with output_encoding",
            )
    env = os.environ.copy()
    env.update(raw_env)
    for key in tuple(env):
        if key.casefold() == "pythonioencoding":
            del env[key]
    env["PYTHONIOENCODING"] = f"{output_encoding}:strict"
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        try:
            output = _decode_stream(exc.stdout, output_encoding)
            error = _decode_stream(exc.stderr, output_encoding)
        except UnicodeDecodeError:
            return ExecutionResult(
                "timed_out",
                error=(
                    "subprocess timed out and emitted output that is not valid "
                    f"{output_encoding}; set output_encoding explicitly"
                ),
            )
        return ExecutionResult(
            "timed_out",
            output=output,
            error=error,
        )
    except (OSError, ValueError) as exc:
        return ExecutionResult("failed", error=str(exc))
    try:
        output = _decode_stream(completed.stdout, output_encoding)
        error = _decode_stream(completed.stderr, output_encoding)
    except UnicodeDecodeError:
        return ExecutionResult(
            "failed",
            exit_code=completed.returncode,
            error=(
                "subprocess output is not valid "
                f"{output_encoding}; set output_encoding explicitly"
            ),
        )
    status = "succeeded" if completed.returncode == 0 else "failed"
    return ExecutionResult(status, completed.returncode, output, error)


def noop_executor(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    del timeout_seconds
    if payload.get("fail"):
        return ExecutionResult("failed", exit_code=1, error="requested noop failure")
    return ExecutionResult(
        "succeeded", exit_code=0, output=str(payload.get("message", "noop"))
    )


class ExecutorRegistry:
    """An explicit, isolatable registry for scheduler executor adapters."""

    def __init__(
        self,
        executors: Mapping[str, Executor] | None = None,
        *,
        include_standard: bool = True,
    ) -> None:
        self._executors: dict[str, Executor] = {}
        if include_standard:
            for name, executor in STANDARD_EXECUTORS.items():
                self.register(name, executor)
        if executors:
            for name, executor in executors.items():
                self.register(name, executor)

    @staticmethod
    def _validate(name: str, executor: Executor) -> None:
        if not isinstance(name, str) or not _EXECUTOR_NAME.fullmatch(name):
            raise ValueError(
                "executor name must start with a lowercase letter and contain "
                "only lowercase letters, digits, '.', '_' or '-'"
            )
        if not callable(executor):
            raise TypeError("executor must be callable")

    def register(self, name: str, executor: Executor, *, replace: bool = False) -> None:
        self._validate(name, executor)
        if name in self._executors and not replace:
            raise ValueError(f"executor already registered: {name}")
        self._executors[name] = executor

    def unregister(self, name: str) -> Executor:
        try:
            return self._executors.pop(name)
        except KeyError:
            raise KeyError(f"unknown executor: {name}") from None

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._executors))

    def snapshot(self) -> Mapping[str, Executor]:
        return MappingProxyType(dict(self._executors))

    def execute(
        self,
        name: str,
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> ExecutionResult:
        executor = self._executors.get(name)
        if executor is None:
            return ExecutionResult("failed", error=f"unknown executor: {name}")
        if not isinstance(payload, dict):
            return ExecutionResult("failed", error="executor payload must be an object")
        if timeout_seconds <= 0:
            return ExecutionResult("failed", error="timeout_seconds must be positive")
        try:
            result = executor(payload, timeout_seconds)
        except Exception as exc:  # Adapters must not strand a run in "running".
            return ExecutionResult(
                "failed",
                error=f"executor {name!r} raised {type(exc).__name__}: {exc}",
            )
        if not isinstance(result, ExecutionResult):
            return ExecutionResult(
                "failed",
                error=f"executor {name!r} returned an invalid result",
            )
        if result.status not in {"succeeded", "failed", "timed_out"}:
            return ExecutionResult(
                "failed",
                error=f"executor {name!r} returned invalid status: {result.status!r}",
            )
        return result


# Imported late so adapters can use ExecutionResult and command_executor without a
# circular dependency at module-import time.
from .adapters import coma_executor, marblerun_executor  # noqa: E402


STANDARD_EXECUTORS: Mapping[str, Executor] = MappingProxyType(
    {
        "command": command_executor,
        "coma": coma_executor,
        "marblerun": marblerun_executor,
        "noop": noop_executor,
        "subprocess": command_executor,
    }
)
DEFAULT_REGISTRY = ExecutorRegistry()


def register_executor(name: str, executor: Executor, *, replace: bool = False) -> None:
    """Register an adapter in the process-wide compatibility registry."""
    DEFAULT_REGISTRY.register(name, executor, replace=replace)


def unregister_executor(name: str) -> Executor:
    return DEFAULT_REGISTRY.unregister(name)


def executor_names() -> tuple[str, ...]:
    return DEFAULT_REGISTRY.names()


def execute(
    name: str, payload: dict[str, Any], timeout_seconds: int
) -> ExecutionResult:
    return DEFAULT_REGISTRY.execute(name, payload, timeout_seconds)
