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
from .context import ExecutionContext
from .dispatch import AcceptedTaskResult, DispatchConflict, DispatchReceipts, RecoveryEvidence
from .executors import (
    DEFAULT_REGISTRY,
    ExecutionResult,
    ExecutorRegistry,
    executor_names,
    register_executor,
    register_contextual_executor,
    unregister_executor,
)
from .definitions import AgentTriggers, DefinitionConflict
from .events import EventTriggers
from .service import SchedulerService
from .store import SchedulerStore
from .trigger_projection import TriggerProjectionError, execute_trigger_request

__all__ = [
    "DEFAULT_AUTHORITY_REGISTRY",
    "DEFAULT_REGISTRY",
    "AcceptedTaskResult",
    "AgentTriggers",
    "AuthorityConfigurationError",
    "AuthorityResolution",
    "AuthorityResolverRegistry",
    "AuthoritySetResult",
    "BachSchedulerAdapter",
    "DefinitionConflict",
    "DispatchConflict",
    "DispatchReceipts",
    "EventTriggers",
    "ExecutionContext",
    "ExecutionResult",
    "ExecutorRegistry",
    "RecoveryEvidence",
    "SchedulerService",
    "SchedulerStore",
    "TriggerProjectionError",
    "create_bach_adapter",
    "execute_trigger_request",
    "executor_names",
    "import_legacy_jobs",
    "register_contextual_executor",
    "register_executor",
    "unregister_executor",
    "validate_authority_specs",
]

__version__ = "0.3.6"
