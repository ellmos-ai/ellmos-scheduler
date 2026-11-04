"""Prepared proposal invariants, deliberately without a persistence implementation."""

from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from ellmos_scheduler import (
    MAX_PROVIDER_SELECTION_VERSION,
    ProviderSelectionConflict,
    ProviderSelectionError,
    prepare_provider_selection,
    validate_provider_selection,
)

A = "a" * 32
B = "b" * 32
C = "c" * 32


def proposal(**changes):
    return {
        "provider": "ellmos-scheduler",
        "store_binding_sha256": "1" * 64,
        "legacy_manifest_sha256": "2" * 64,
        "module_commit": "3" * 40,
        "executor_registry_sha256": "4" * 64,
        **changes,
    }


def initial():
    return prepare_provider_selection(
        None, expected_version=0, expected_generation=None, new_generation=A, proposal=proposal()
    )


def prepare(current, *, version=1, generation=A, new_generation=B, candidate=None):
    return prepare_provider_selection(
        current,
        expected_version=version,
        expected_generation=generation,
        new_generation=new_generation,
        proposal=proposal() if candidate is None else candidate,
    )


def test_initial_absence_creates_only_a_prepared_legacy_selected_proposal():
    result = initial()
    assert result == {
        "schema": "ellmos.scheduler-provider-selection.v1",
        "version": 1,
        "generation": A,
        "phase": "prepared",
        "selected_provider": "legacy",
        "proposal": proposal(),
    }
    assert validate_provider_selection(result) == result
    with pytest.raises(ProviderSelectionError):
        validate_provider_selection(None)
    assert not any(key in result for key in ("active", "ready", "verified", "activated_at"))


@pytest.mark.parametrize("version,generation", [(1, A), (4, B)])
def test_absence_cannot_satisfy_a_previously_observed_existing_epoch(version, generation):
    with pytest.raises(ProviderSelectionConflict):
        prepare(None, version=version, generation=generation)


@pytest.mark.parametrize("version,generation", [(0, None), (2, A), (1, B)])
def test_either_stale_version_or_generation_blocks_overwrite(version, generation):
    current = initial()
    original = deepcopy(current)
    with pytest.raises(ProviderSelectionConflict):
        prepare(current, version=version, generation=generation)
    assert current == original


def test_proposal_generation_changes_and_stale_aba_identity_cannot_match():
    first = initial()
    second = prepare(first)
    assert second["version"] == 2 and second["generation"] == B
    third = prepare(second, version=2, generation=B, new_generation=A)
    assert third["version"] == 3 and third["generation"] == A and third["selected_provider"] == "legacy"
    with pytest.raises(ProviderSelectionConflict):
        prepare(third, version=1, generation=A, new_generation=C)
    with pytest.raises(ProviderSelectionConflict):
        prepare(third, version=3, generation=B, new_generation=C)
    with pytest.raises(ProviderSelectionError, match="provider_generation_reused"):
        prepare(first, new_generation=A)


@pytest.mark.parametrize(
    "current",
    [{}, [], False, "", {"version": 0}, {"schema": "other"}, {"phase": "active", "selected_provider": "external"}],
)
def test_malformed_existing_state_is_never_treated_as_initial_absence(current):
    original = deepcopy(current)
    with pytest.raises(ProviderSelectionError):
        prepare(current, version=0, generation=None)
    assert current == original
    with pytest.raises(ProviderSelectionError):
        validate_provider_selection(current)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "unknown"),
        ("version", True),
        ("version", 0),
        ("version", -1),
        ("version", MAX_PROVIDER_SELECTION_VERSION + 1),
        ("version", 1.0),
        ("generation", "A" * 32),
        ("generation", "a" * 31),
        ("generation", "a" * 33),
        ("phase", "active"),
        ("selected_provider", "ellmos-scheduler"),
        ("proposal", []),
        ("extra", "synthetic-secret"),
    ],
)
def test_existing_snapshot_has_strict_fields_types_and_no_activation_states(field, value):
    current = initial()
    current[field] = value
    with pytest.raises(ProviderSelectionError):
        validate_provider_selection(current)


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider", "bach"),
        ("module_commit", "3" * 39),
        ("module_commit", "3" * 41),
        ("module_commit", "A" * 40),
        ("store_binding_sha256", "1" * 63),
        ("legacy_manifest_sha256", "2" * 65),
        ("executor_registry_sha256", "x" * 64),
        ("executor_registry_sha256", None),
        ("token", "synthetic-secret"),
        ("raw_manifest", {"private": "x" * 100000}),
    ],
)
def test_proposal_rejects_extras_unbounded_data_and_abbreviated_or_nonhex_provenance(field, value):
    with pytest.raises(ProviderSelectionError) as error:
        prepare(initial(), candidate=proposal(**{field: value}))
    assert "synthetic-secret" not in str(error.value)
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "version,generation,new_generation",
    [
        (True, A, B),
        (-1, A, B),
        (MAX_PROVIDER_SELECTION_VERSION + 1, A, B),
        (1.0, A, B),
        (0, A, B),
        (1, None, B),
        (1, "a" * 31, B),
        (1, A, "B" * 32),
        (1, A, False),
    ],
)
def test_cas_arguments_are_strict_bounded_values(version, generation, new_generation):
    with pytest.raises(ProviderSelectionError):
        prepare(initial(), version=version, generation=generation, new_generation=new_generation)


def test_exhausted_version_never_wraps_or_restarts_a_generation():
    current = initial()
    current["version"] = MAX_PROVIDER_SELECTION_VERSION
    assert validate_provider_selection(current)["version"] == MAX_PROVIDER_SELECTION_VERSION
    with pytest.raises(ProviderSelectionError, match="provider_selection_version_exhausted"):
        prepare(current, version=MAX_PROVIDER_SELECTION_VERSION)


def test_nonplain_objects_missing_fields_and_nonstring_keys_are_invalid():
    class Mapping(dict):
        pass

    current = initial()
    for malformed in (
        Mapping(current),
        {key: val for key, val in current.items() if key != "phase"},
        {**current, 1: "unexpected"},
    ):
        with pytest.raises(ProviderSelectionError):
            validate_provider_selection(malformed)
    with pytest.raises(ProviderSelectionError):
        prepare(current, candidate=Mapping(proposal()))


def test_inputs_and_returned_snapshots_have_no_shared_mutable_state():
    current = initial()
    candidate = proposal()
    before = deepcopy(current)
    first = prepare(current, candidate=candidate)
    second = prepare(current, candidate=candidate)
    copied = validate_provider_selection(first)
    first["proposal"]["module_commit"] = "f" * 40
    first["generation"] = C
    assert second["proposal"] == candidate and current == before
    assert copied["proposal"]["module_commit"] == "3" * 40 and copied["generation"] == B
    candidate["provider"] = "changed"
    assert second["proposal"]["provider"] == "ellmos-scheduler"


def test_isolated_contract_has_no_store_io_network_process_or_provider_imports():
    source = Path(__file__).resolve().parents[1] / "src/ellmos_scheduler/provider_selection.py"
    script = r"""
import importlib.util,sys
spec=importlib.util.spec_from_file_location('isolated_selection',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def reject(event,args):
    if event in {'open','sqlite3.connect','socket.__new__','subprocess.Popen','os.system'}:
        raise AssertionError('unexpected effect: '+event)
sys.addaudithook(reject)
p={'provider':'ellmos-scheduler','store_binding_sha256':'1'*64,
   'legacy_manifest_sha256':'2'*64,'module_commit':'3'*40,'executor_registry_sha256':'4'*64}
a=m.prepare_provider_selection(None,expected_version=0,expected_generation=None,new_generation='a'*32,proposal=p)
b=m.prepare_provider_selection(a,expected_version=1,expected_generation='a'*32,new_generation='b'*32,proposal=p)
assert m.validate_provider_selection(b)==b
assert not any(n.startswith(('ellmos_scheduler','hub','fastapi','httpx','requests')) for n in sys.modules)
print('pure_contract_ok')
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(source)], capture_output=True, text=True, check=True
    )
    assert completed.stdout.strip() == "pure_contract_ok"
