"""Pre-PR-A1 compatibility for typed errors (contract 17).

Prefers the canonical ``verity.errors.VerityError`` from Atharv's foundation
(PR-A1). Until that PR is merged onto ``integration/verity-v1`` this module
provides a temporary stand-in with the identical
``(code, message, details, retryable)`` constructor shape and the exact
contract-17 code strings, so P1-P4 fixtures and tests can exercise typed
errors without waiting (roadmap 03: "use fixture IDs/models until PR-A1").

The stand-in is deleted automatically once ``verity.errors`` imports; it is
never serialized on the wire and adapters map everything through contract 17
codes. It is not a second canonical model.
"""

from __future__ import annotations

from typing import Any, Mapping

try:  # pragma: no cover - exercised only after PR-A1 lands
    from verity.errors import VerityError  # noqa: F401
except ImportError:  # pragma: no cover - pre-merge fixture phase

    class VerityError(Exception):  # type: ignore[no-redef]
        """Temporary stand-in matching contract 16/17's VerityError shape."""

        def __init__(
            self,
            code: str,
            message: str,
            details: Mapping[str, Any] | None = None,
            retryable: bool | None = None,
        ) -> None:
            self.code = code
            self.message = message
            self.details = details
            self.retryable = retryable
            super().__init__(code, message)