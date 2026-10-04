"""Public cross-module interfaces owned by Piyush (contract 16, v1.0.0).

These are the exact frozen Python signatures from
``Docs/contracts/16_VERITY_PUBLIC_INTERFACES.md``. They are interface
signatures, not class internals; concrete parsers/chunkers live in this
package and satisfy these protocols structurally.

Canonical types (``ParsedDocument``, ``ChunkDraft``, ``IngestRequest``,
``IngestResult``, ``SearchRequest``, ``RetrievalRun``, ``Chunk``) are the
single models from ``verity.models`` (contract 03). While PR-A1 is not yet
merged the ingestion modules emit canonical JSON instances (dicts that
validate against ``Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json`` $defs);
annotations below name the canonical types and switch to real imports once
the foundation lands on the integration branch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from uuid import UUID

    from verity.models import (
        Chunk,
        ChunkDraft,
        IngestRequest,
        IngestResult,
        ParsedDocument,
        RetrievalRun,
        SearchRequest,
    )


@runtime_checkable
class Parser(Protocol):
    """Bytes -> normalized parsed document (contract 05/16)."""

    def parse(self, data: bytes, filename: str, media_type: str) -> "ParsedDocument":
        ...


@runtime_checkable
class Chunker(Protocol):
    """Parsed document -> ordered chunk drafts (contract 05/16).

    Chunkers never assign IDs: the central materializer assigns the
    ``Locator``, ``ordinal``, ``chunk_id`` and ``schema_version``.
    """

    def chunk(
        self, parsed: "ParsedDocument", version_id: "UUID"
    ) -> "tuple[ChunkDraft, ...]":
        ...


@runtime_checkable
class IngestionCoordinator(Protocol):
    """End-to-end ingest boundary (contract 05/16). Implemented in P5."""

    async def ingest(
        self, request: "IngestRequest", data: bytes
    ) -> "IngestResult":
        ...


@runtime_checkable
class Materializer(Protocol):
    """Central materializer record boundary used by the pipeline (contract 05).

    Not a public cross-module signature in 16; it documents the conversion
    from drafts to canonical ``Chunk``/``Requirement``/``SpecEntity`` records
    after the store hands out source/document/version IDs.
    """

    def materialize(
        self,
        parsed: "ParsedDocument",
        drafts: "tuple[ChunkDraft, ...]",
        source_id: "UUID",
        document_id: "UUID",
        version_id: "UUID",
        source_path: str,
    ) -> "dict[str, tuple]":
        ...