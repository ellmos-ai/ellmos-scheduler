# SPDX-License-Identifier: MIT
"""Prepared-only provider proposals: pure validation and logical CAS, never authority.

The host's existing control owner supplies locking, fresh reads, atomic persistence
and independent readback. This module owns no files, stores or activation path.
"""

from __future__ import annotations

import re

PROVIDER_SELECTION_SCHEMA = "ellmos.scheduler-provider-selection.v1"
MAX_PROVIDER_SELECTION_VERSION = 2**53 - 1
_FIELDS = frozenset({"schema", "version", "generation", "phase", "selected_provider", "proposal"})
_PROPOSAL_FIELDS = frozenset(
    {"provider", "store_binding_sha256", "legacy_manifest_sha256", "module_commit", "executor_registry_sha256"}
)
_HEX = re.compile(r"[0-9a-f]+\Z")


class ProviderSelectionError(ValueError):
    """Bounded error: input values and provenance are never echoed."""

    def __init__(self, reason_code):
        super().__init__(reason_code)
        self.reason_code = reason_code


class ProviderSelectionConflict(ProviderSelectionError):
    """The expected proposal version or generation is no longer current."""


def _invalid(reason):
    raise ProviderSelectionError(reason)


def _object(value, fields):
    if (
        type(value) is not dict
        or len(value) != len(fields)
        or any(type(key) is not str for key in value)
        or set(value) != fields
    ):
        _invalid("invalid_provider_selection_fields")


def _literal(value, expected):
    return type(value) is str and len(value) == len(expected) and value == expected


def _hex(value, length):
    if type(value) is not str or len(value) != length or _HEX.fullmatch(value) is None:
        _invalid("invalid_provider_selection_digest")
    return value


def _version(value, *, initial=False):
    if type(value) is not int or not (0 if initial else 1) <= value <= MAX_PROVIDER_SELECTION_VERSION:
        _invalid("invalid_provider_selection_version")
    return value


def _proposal(value):
    _object(value, _PROPOSAL_FIELDS)
    if not _literal(value["provider"], "ellmos-scheduler"):
        _invalid("invalid_proposed_provider")
    return {
        "provider": "ellmos-scheduler",
        "store_binding_sha256": _hex(value["store_binding_sha256"], 64),
        "legacy_manifest_sha256": _hex(value["legacy_manifest_sha256"], 64),
        "module_commit": _hex(value["module_commit"], 40),
        "executor_registry_sha256": _hex(value["executor_registry_sha256"], 64),
    }


def validate_provider_selection(value):
    """Validate an existing prepared snapshot and return an independent plain copy.

    Absence is NOT an existing snapshot. Unknown phases/providers, extra fields,
    malformed digests and non-plain values fail closed; none become defaults.
    Fixed fields/string lengths and a JSON-safe version bound limit snapshot size.
    """
    _object(value, _FIELDS)
    if (
        not _literal(value["schema"], PROVIDER_SELECTION_SCHEMA)
        or not _literal(value["phase"], "prepared")
        or not _literal(value["selected_provider"], "legacy")
    ):
        _invalid("invalid_provider_selection_state")
    return {
        "schema": PROVIDER_SELECTION_SCHEMA,
        "version": _version(value["version"]),
        "generation": _hex(value["generation"], 32),
        "phase": "prepared",
        "selected_provider": "legacy",
        "proposal": _proposal(value["proposal"]),
    }


def prepare_provider_selection(current, *, expected_version, expected_generation, new_generation, proposal):
    """Construct one prepared successor under logical version AND generation CAS.

    Only current=None represents host-confirmed initial absence, with expected
    version 0 and generation None. Existing malformed state must never be replaced
    by None. A new generation identifies this proposal mutation, not a worker run
    or an admission grant. Hosts supply it; this function generates no identity.
    Hashes bind proposed provenance only, never validate external readiness.
    """
    expected_version = _version(expected_version, initial=True)
    if expected_version == 0:
        if expected_generation is not None:
            _invalid("invalid_expected_provider_generation")
    else:
        _hex(expected_generation, 32)
    generation = _hex(new_generation, 32)
    proposed = _proposal(proposal)
    if current is None:
        if expected_version != 0 or expected_generation is not None:
            raise ProviderSelectionConflict("provider_selection_conflict")
        version = 0
    else:
        snapshot = validate_provider_selection(current)
        if snapshot["version"] != expected_version or snapshot["generation"] != expected_generation:
            raise ProviderSelectionConflict("provider_selection_conflict")
        if generation == snapshot["generation"]:
            _invalid("provider_generation_reused")
        version = snapshot["version"]
    if version == MAX_PROVIDER_SELECTION_VERSION:
        _invalid("provider_selection_version_exhausted")
    return {
        "schema": PROVIDER_SELECTION_SCHEMA,
        "version": version + 1,
        "generation": generation,
        "phase": "prepared",
        "selected_provider": "legacy",
        "proposal": proposed,
    }
