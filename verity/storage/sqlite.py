"""SQLite canonical store, FTS5 index and embedding records.

Contract: Docs/contracts/13_VERITY_DATABASE_SCHEMA.md. Owner Atharv.

Tables: ``documents``, ``document_versions``, ``blocks``, ``requirements``,
``retrieval_units``, ``embeddings``, ``coverage_runs`` with foreign keys,
WAL mode and one transaction per document version. Only this module (and
the service through protocols) touches SQL; transports never do.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..config import VerityConfig
from ..errors import VerityError

SCHEMA_VERSION = 1


class KnowledgeStore(Protocol):
    """Persistence protocol used by ``VerityService`` (contract 16)."""

    def connect(self) -> None: ...
    def close(self) -> None: ...


def open_store(config: VerityConfig) -> KnowledgeStore:
    """Open (and migrate, if needed) the canonical SQLite store.

    Skeleton for Phase 11: apply ``storage/migrations`` in order inside a
    transaction, enable WAL and foreign keys, and reject newer schema
    versions with ``VERSION_UNSUPPORTED``.
    """
    database_path: Path = config.database_path
    if database_path.exists():
        # Placeholder validation until migrations land (Phase 11).
        pass
    raise VerityError(
        "RETRIEVAL_UNAVAILABLE",
        "sqlite store not yet implemented (Phase 11, contract 13)",
    )