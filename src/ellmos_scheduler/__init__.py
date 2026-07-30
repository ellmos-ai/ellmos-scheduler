"""Standalone scheduler for modular ellmos stacks."""

from .authorities import (
    DEFAULT_AUTHORITY_REGISTRY,
    AuthorityConfigurationError,
    AuthorityResolution,
    AuthorityResolverRegistry,
    AuthoritySetResult,
    validate_authority_specs,
)
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
    "AuthorityConfigurationError",
    "AuthorityResolution",
    "AuthorityResolverRegistry",
    "AuthoritySetResult",
    "DEFAULT_AUTHORITY_REGISTRY",
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
    "validate_authority_specs",
]

__version__ = "0.2.1"
