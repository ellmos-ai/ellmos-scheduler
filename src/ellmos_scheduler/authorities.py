from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.parse import parse_qsl, unquote, urlsplit


_NAME = re.compile(r"^[a-z][a-z0-9_.:-]*$")
_SECRET_KEY = re.compile(
    r"(?:^|[_-])(secret|password|passwd|token|api[_-]?key|private[_-]?key|"
    r"access[_-]?key|credential|authorization|bearer)(?:$|[_-])",
    re.IGNORECASE,
)
_RAW_CONTENT_KEYS = {
    "body",
    "bytes",
    "content",
    "data",
    "prompt",
    "raw",
    "raw_body",
    "raw_bytes",
    "raw_content",
    "text",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.-]*$")
_SECRET_VALUE = re.compile(
    r"(?:authorization\s*:|bearer\s+[A-Za-z0-9._~+/=-]+|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=])",
    re.IGNORECASE,
)
_MAX_AUTHORITY_BYTES = 5 * 1024 * 1024


class AuthorityConfigurationError(ValueError):
    """Authority metadata is unsafe or does not satisfy the public contract."""


@dataclass(frozen=True)
class AuthorityResolution:
    status: str
    origin: str
    sha256: str | None = None
    readback_sha256: str | None = None
    byte_length: int | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class AuthoritySetResult:
    receipts: tuple[dict[str, Any], ...]
    set_sha256: str
    required_ok: bool
    error: str


AuthorityResolver = Callable[[Mapping[str, Any]], AuthorityResolution]
AuthoritySourceValidator = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_no_secrets(value: Any, *, path: str = "source") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise AuthorityConfigurationError(f"{path} keys must be strings")
            if _SECRET_KEY.search(key):
                raise AuthorityConfigurationError(
                    f"{path}.{key} is secret-bearing; use a provider-local "
                    "credential reference outside scheduler authority metadata"
                )
            if key.lower().replace("-", "_") in _RAW_CONTENT_KEYS:
                raise AuthorityConfigurationError(
                    f"{path}.{key} contains raw content; configure only a "
                    "read-only authority reference"
                )
            _validate_no_secrets(nested, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_no_secrets(nested, path=f"{path}[{index}]")
        return
    if isinstance(value, str) and "://" in value:
        parsed = urlsplit(value)
        if parsed.username is not None or parsed.password is not None:
            raise AuthorityConfigurationError(
                f"{path} URI userinfo is not allowed in authority metadata"
            )
        for key, item in parse_qsl(parsed.query, keep_blank_values=True):
            if _SECRET_KEY.search(key):
                raise AuthorityConfigurationError(
                    f"{path} URI contains secret-bearing query metadata"
                )
            if _SECRET_VALUE.search(item):
                raise AuthorityConfigurationError(
                    f"{path} URI contains credential-like query data"
                )
        if _SECRET_VALUE.search(unquote(parsed.path)):
            raise AuthorityConfigurationError(
                f"{path} URI path contains credential-like data"
            )
        return
    if isinstance(value, str) and _SECRET_VALUE.search(value):
        raise AuthorityConfigurationError(
            f"{path} contains credential-like data; store only a reference"
        )
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise AuthorityConfigurationError(
            f"{path} contains an unsupported metadata value"
        )


def validate_authority_specs(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AuthorityConfigurationError("authorities must be a JSON array")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        label = f"authorities[{index}]"
        if not isinstance(raw, Mapping):
            raise AuthorityConfigurationError(f"{label} must be an object")
        allowed = {"id", "type", "resolver", "required", "source"}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise AuthorityConfigurationError(
                f"{label} contains unsupported fields: {', '.join(unknown)}"
            )
        authority_id = raw.get("id")
        authority_type = raw.get("type")
        resolver = raw.get("resolver")
        for key, item in (
            ("id", authority_id),
            ("type", authority_type),
            ("resolver", resolver),
        ):
            if not isinstance(item, str) or not _NAME.fullmatch(item):
                raise AuthorityConfigurationError(
                    f"{label}.{key} must be a stable lowercase identifier"
                )
        assert isinstance(authority_id, str)
        if authority_id in seen:
            raise AuthorityConfigurationError(
                f"duplicate authority id: {authority_id}"
            )
        seen.add(authority_id)
        required = raw.get("required", True)
        if not isinstance(required, bool):
            raise AuthorityConfigurationError(f"{label}.required must be a boolean")
        source = raw.get("source")
        if not isinstance(source, Mapping):
            raise AuthorityConfigurationError(f"{label}.source must be an object")
        _validate_no_secrets(source)
        result.append(
            {
                "id": authority_id,
                "type": authority_type,
                "resolver": resolver,
                "required": required,
                "source": dict(source),
            }
        )
    return result


def validate_file_authority_source(
    source: Mapping[str, Any],
) -> Mapping[str, Any]:
    allowed = {"path", "max_bytes"}
    unknown = sorted(set(source) - allowed)
    if unknown:
        raise AuthorityConfigurationError(
            f"file authority source contains unsupported fields: {', '.join(unknown)}"
        )
    raw_path = source.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise AuthorityConfigurationError(
            "file authority source requires a non-empty path"
        )
    max_bytes = source.get("max_bytes", _MAX_AUTHORITY_BYTES)
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise AuthorityConfigurationError("file max_bytes must be a positive integer")
    return {"path": raw_path, "max_bytes": max_bytes}


def file_authority_resolver(source: Mapping[str, Any]) -> AuthorityResolution:
    source = validate_file_authority_source(source)
    raw_path = str(source["path"])
    max_bytes = int(source["max_bytes"])
    path = Path(raw_path).expanduser().resolve()
    origin = path.as_uri()
    try:
        first_stat = path.stat()
    except FileNotFoundError:
        return AuthorityResolution("unresolved", origin, error_code="not_found")
    except OSError:
        return AuthorityResolution("unresolved", origin, error_code="stat_failed")
    if not path.is_file():
        return AuthorityResolution("unresolved", origin, error_code="not_a_file")
    if first_stat.st_size > max_bytes:
        return AuthorityResolution("unresolved", origin, error_code="size_limit")
    try:
        with path.open("rb") as handle:
            first = handle.read(max_bytes + 1)
        with path.open("rb") as handle:
            second = handle.read(max_bytes + 1)
    except OSError:
        return AuthorityResolution("unresolved", origin, error_code="read_failed")
    if len(first) > max_bytes or len(second) > max_bytes:
        return AuthorityResolution("unresolved", origin, error_code="size_limit")
    first_hash = hashlib.sha256(first).hexdigest()
    second_hash = hashlib.sha256(second).hexdigest()
    if first_hash != second_hash:
        return AuthorityResolution(
            "conflict",
            origin,
            sha256=first_hash,
            readback_sha256=second_hash,
            byte_length=len(first),
            error_code="changed_during_readback",
        )
    return AuthorityResolution(
        "resolved",
        origin,
        sha256=first_hash,
        readback_sha256=second_hash,
        byte_length=len(first),
    )


class AuthorityResolverRegistry:
    """Explicit, provider-neutral registry for read-only authority resolvers."""

    def __init__(
        self,
        resolvers: Mapping[
            str, tuple[AuthorityResolver, AuthoritySourceValidator]
        ]
        | None = None,
        *,
        include_standard: bool = True,
    ) -> None:
        self._resolvers: dict[
            str, tuple[AuthorityResolver, AuthoritySourceValidator]
        ] = {}
        if include_standard:
            self.register(
                "file",
                file_authority_resolver,
                source_validator=validate_file_authority_source,
            )
        if resolvers:
            for name, definition in resolvers.items():
                if not isinstance(definition, tuple) or len(definition) != 2:
                    raise TypeError(
                        "custom authority resolvers require a "
                        "(resolver, source_validator) tuple"
                    )
                resolver, source_validator = definition
                self.register(
                    name,
                    resolver,
                    source_validator=source_validator,
                )

    def register(
        self,
        name: str,
        resolver: AuthorityResolver,
        *,
        source_validator: AuthoritySourceValidator,
        replace: bool = False,
    ) -> None:
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("authority resolver name must be a lowercase identifier")
        if not callable(resolver):
            raise TypeError("authority resolver must be callable")
        if not callable(source_validator):
            raise TypeError("authority source_validator must be callable")
        if name in self._resolvers and not replace:
            raise ValueError(f"authority resolver already registered: {name}")
        self._resolvers[name] = (resolver, source_validator)

    def unregister(self, name: str) -> AuthorityResolver:
        try:
            return self._resolvers.pop(name)[0]
        except KeyError:
            raise KeyError(f"unknown authority resolver: {name}") from None

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._resolvers))

    def snapshot(self) -> Mapping[str, AuthorityResolver]:
        return MappingProxyType(
            {name: definition[0] for name, definition in self._resolvers.items()}
        )

    def validate_specs(self, specs: Any) -> list[dict[str, Any]]:
        validated = validate_authority_specs(specs)
        for spec in validated:
            resolver_name = str(spec["resolver"])
            definition = self._resolvers.get(resolver_name)
            if definition is None:
                raise AuthorityConfigurationError(
                    f"unknown authority resolver: {resolver_name}"
                )
            _, source_validator = definition
            normalized = source_validator(spec["source"])
            if not isinstance(normalized, Mapping):
                raise AuthorityConfigurationError(
                    f"authority resolver {resolver_name!r} returned invalid source metadata"
                )
            _validate_no_secrets(normalized)
            spec["source"] = dict(normalized)
        return validated

    def resolve(
        self, specs: Any, *, run_id: str
    ) -> AuthoritySetResult:
        validated = self.validate_specs(specs)
        receipts: list[dict[str, Any]] = []
        required_failures: list[str] = []
        for spec in validated:
            resolver_name = str(spec["resolver"])
            resolver, _ = self._resolvers[resolver_name]
            try:
                resolution = resolver(spec["source"])
            except AuthorityConfigurationError:
                raise
            except Exception:
                resolution = AuthorityResolution(
                    "unresolved",
                    f"resolver:{resolver_name}",
                    error_code="resolver_failed",
                )
            if resolution.status not in {"resolved", "unresolved", "conflict"}:
                raise AuthorityConfigurationError(
                    f"authority resolver {resolver_name!r} returned invalid status"
                )
            if not isinstance(resolution.origin, str) or not resolution.origin:
                raise AuthorityConfigurationError(
                    f"authority resolver {resolver_name!r} returned invalid origin"
                )
            parsed_origin = urlsplit(resolution.origin)
            if (
                any(ord(character) < 32 for character in resolution.origin)
                or not parsed_origin.scheme
                or parsed_origin.username is not None
                or parsed_origin.password is not None
                or parsed_origin.query
                or parsed_origin.fragment
            ):
                raise AuthorityConfigurationError(
                    f"authority resolver {resolver_name!r} returned unsafe origin"
                )
            if resolution.status == "resolved":
                if (
                    not isinstance(resolution.sha256, str)
                    or not _SHA256.fullmatch(resolution.sha256)
                    or not isinstance(resolution.readback_sha256, str)
                    or not _SHA256.fullmatch(resolution.readback_sha256)
                    or resolution.sha256 != resolution.readback_sha256
                ):
                    raise AuthorityConfigurationError(
                        f"authority resolver {resolver_name!r} did not provide a "
                        "matching SHA-256 readback"
                    )
                if (
                    not isinstance(resolution.byte_length, int)
                    or isinstance(resolution.byte_length, bool)
                    or resolution.byte_length < 0
                ):
                    raise AuthorityConfigurationError(
                        f"authority resolver {resolver_name!r} returned invalid byte length"
                    )
                if resolution.error_code is not None:
                    raise AuthorityConfigurationError(
                        f"authority resolver {resolver_name!r} returned an error "
                        "for resolved authority"
                    )
            else:
                if (
                    not isinstance(resolution.error_code, str)
                    or not _ERROR_CODE.fullmatch(resolution.error_code)
                ):
                    raise AuthorityConfigurationError(
                        f"authority resolver {resolver_name!r} returned invalid error code"
                    )
                for digest in (resolution.sha256, resolution.readback_sha256):
                    if digest is not None and (
                        not isinstance(digest, str) or not _SHA256.fullmatch(digest)
                    ):
                        raise AuthorityConfigurationError(
                            f"authority resolver {resolver_name!r} returned invalid SHA-256"
                        )
                if resolution.byte_length is not None and (
                    not isinstance(resolution.byte_length, int)
                    or isinstance(resolution.byte_length, bool)
                    or resolution.byte_length < 0
                ):
                    raise AuthorityConfigurationError(
                        f"authority resolver {resolver_name!r} returned invalid byte length"
                    )
            receipt_core = {
                "authority_id": spec["id"],
                "authority_type": spec["type"],
                "resolver": resolver_name,
                "requirement": "required" if spec["required"] else "optional",
                "status": resolution.status,
                "origin": resolution.origin,
                "sha256": resolution.sha256,
                "readback_sha256": resolution.readback_sha256,
                "byte_length": resolution.byte_length,
                "error_code": resolution.error_code,
            }
            receipt_material = {
                "run_id": run_id,
                **receipt_core,
            }
            receipt = {
                "receipt_id": hashlib.sha256(
                    _canonical_json(receipt_material).encode("utf-8")
                ).hexdigest(),
                **receipt_core,
            }
            receipts.append(receipt)
            if spec["required"] and resolution.status != "resolved":
                required_failures.append(
                    f"{spec['id']}:{resolution.error_code or resolution.status}"
                )
        receipts.sort(key=lambda item: str(item["authority_id"]))
        set_hash = hashlib.sha256(
            _canonical_json(
                [
                    {key: value for key, value in receipt.items() if key != "receipt_id"}
                    for receipt in receipts
                ]
            ).encode("utf-8")
        ).hexdigest()
        return AuthoritySetResult(
            receipts=tuple(receipts),
            set_sha256=set_hash,
            required_ok=not required_failures,
            error="; ".join(required_failures),
        )


DEFAULT_AUTHORITY_REGISTRY = AuthorityResolverRegistry()
