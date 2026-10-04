"""VERITY canonical error codes and typed core exception.

Contract: Docs/contracts/17_VERITY_ERROR_CONTRACT.md (v1.0.0, owner Atharv).
All public failures become the canonical ``Error`` object from contract 03:
``{schema_version:"1.0.0", code, message, details:null|object, request_id:UUIDv4, retryable}``.
Core raises ``VerityError``; adapters add ``request_id``, serialize and never
expose tracebacks, credentials, absolute paths or model internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

SCHEMA_VERSION = "1.0.0"

#: Every public failure code in v1 (contract 17). No other code may be created.
ERROR_CODES: frozenset[str] = frozenset({
    "INVALID_REQUEST",
    "CONFIG_INVALID",
    "VERSION_UNSUPPORTED",
    "UNSUPPORTED_FORMAT",
    "SPEC_VALIDATION_ERROR",
    "PARSER_ERROR",
    "CHUNKING_ERROR",
    "LIMIT_EXCEEDED",
    "SOURCE_NOT_FOUND",
    "DOCUMENT_NOT_FOUND",
    "REQUIREMENT_NOT_FOUND",
    "EVIDENCE_NOT_FOUND",
    "EVIDENCE_GONE",
    "COVERAGE_NOT_FOUND",
    "WORKSPACE_NOT_FOUND",
    "WORKSPACE_DENIED",
    "MODEL_UNAVAILABLE",
    "RETRIEVAL_UNAVAILABLE",
    "COVERAGE_UNAVAILABLE",
    "SDK_UNAVAILABLE",
    "SESSION_NOT_FOUND",
    "TIMEOUT",
    "INTERNAL_ERROR",
})

#: Default retryable flag per code (contract 17).
_RETRYABLE_DEFAULT: dict[str, bool] = {
    "MODEL_UNAVAILABLE": True,
    "RETRIEVAL_UNAVAILABLE": True,
    "COVERAGE_UNAVAILABLE": True,
    "SDK_UNAVAILABLE": True,
    "TIMEOUT": True,
    "INTERNAL_ERROR": True,
}


@dataclass
class VerityError(Exception):
    """Typed core exception raised by verity modules.

    ``code`` is one of ``ERROR_CODES``; ``message`` is safe user-facing
    English text; ``details`` is a JSON-compatible object or None;
    ``retryable`` defaults to the contract-17 default for the code.
    The adapter adds ``request_id`` when serializing the public Error.
    """

    code: str
    message: str
    details: Mapping[str, Any] | None = None
    retryable: bool | None = None

    def __post_init__(self) -> None:
        if self.code not in ERROR_CODES:
            raise ValueError(f"unknown error code: {self.code!r}")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("message must be a nonempty string")
        if self.retryable is None:
            self.retryable = _RETRYABLE_DEFAULT.get(self.code, False)
        if self.details is not None and not isinstance(self.details, Mapping):
            raise ValueError("details must be a mapping or None")
        super().__init__(self.code, self.message)

    def to_dict(self, request_id: str) -> dict[str, Any]:
        """Serialize as the canonical public ``Error`` from contract 03.

        ``request_id`` is supplied by the transport adapter, never invented
        here. Raw tracebacks/secrets/absolute paths are never included.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "code": self.code,
            "message": self.message,
            "details": dict(self.details) if self.details is not None else None,
            "request_id": request_id,
            "retryable": self.retryable,
        }


def invalid_request(message: str, details: Mapping[str, Any] | None = None) -> VerityError:
    """Convenience constructor for the most common model validation failure."""
    return VerityError("INVALID_REQUEST", message, details)