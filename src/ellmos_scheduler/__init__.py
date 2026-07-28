"""Standalone scheduler for modular ellmos stacks."""

from .bach import BachSchedulerAdapter, create_bach_adapter, import_legacy_jobs
from .executors import (
    DEFAULT_REGISTRY,
    ExecutionResult,
    ExecutorRegistry,
    executor_names,
    register_executor,
    unregister_executor,
)
from .service import SchedulerService
from .store import SchedulerStore

__all__ = [
    "BachSchedulerAdapter",
    "DEFAULT_REGISTRY",
    "ExecutionResult",
    "ExecutorRegistry",
    "SchedulerService",
    "SchedulerStore",
    "executor_names",
    "create_bach_adapter",
    "import_legacy_jobs",
    "register_executor",
    "unregister_executor",
]

__version__ = "0.1.0"
