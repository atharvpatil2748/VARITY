"""Storage boundary types (contracts 13/16; owner Atharv).

Internal persistence records — not wire types. Only ``verity.storage`` may
issue SQL; every other module reaches data through ``KnowledgeStore``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from ..models import (
    Chunk,
    CoverageRequest,
    CoverageResult,
    Document,
    DocumentKind,
    IngestRequest,
    IngestResult,
    ListPage,
    ParsedDocument,
    Provenance,
    Requirement,
    SearchRequest,
    Source,
    SpecEntity,
)


@dataclass(frozen=True)
class IngestionIdentity:
    """Identity allocated by ``prepare_ingestion`` without mutation.

    For a known source and identical active content,
    ``existing_version_id == version_id`` and the coordinator returns the
    current ``IngestResult`` without reindexing. For new/changed content
    ``existing_version_id`` is None and ``activate_ingestion`` writes
    everything atomically.
    """

    source_id: UUID
    document_id: UUID
    version_id: UUID
    existing_version_id: UUID | None


@dataclass(frozen=True)
class RankedChunk:
    """Internal public-to-retrieval store record (contract 16, 1.0.0)."""

    chunk: Chunk
    rank: int  # >= 1
    raw_score: float


@runtime_checkable
class KnowledgeStore(Protocol):
    """Canonical persistence boundary (contract 16). No method returns SQL."""

    async def prepare_ingestion(
        self, request: IngestRequest, content_sha256: str, source_key: str | None
    ) -> IngestionIdentity: ...

    async def activate_ingestion(
        self,
        identity: IngestionIdentity,
        request: IngestRequest,
        parsed: ParsedDocument,
        chunks: tuple[Chunk, ...],
        requirements: tuple[Requirement, ...],
        spec_entities: tuple[SpecEntity, ...],
        original_bytes: bytes,
    ) -> IngestResult: ...

    async def get_document(self, document_id: UUID) -> Document | None: ...

    async def list_documents(
        self, limit: int, offset: int, kind: DocumentKind | None
    ) -> ListPage: ...

    async def list_sources(self, limit: int, offset: int) -> ListPage: ...

    async def get_requirement(self, requirement_id: str) -> Requirement | None: ...

    async def get_chunk(self, chunk_id: str) -> Chunk | None: ...

    async def get_evidence_origin(
        self, evidence_id: str
    ) -> tuple[Chunk, Document, Provenance] | None: ...

    async def lexical_candidates(
        self, request: SearchRequest, limit: int
    ) -> tuple[RankedChunk, ...]: ...

    async def vector_candidates(
        self,
        query_vector: tuple[float, ...],
        request: SearchRequest,
        model_id: str,
        limit: int,
    ) -> tuple[RankedChunk, ...]: ...

    async def save_coverage(self, result: CoverageResult) -> None: ...

    async def get_coverage(self, coverage_id: UUID) -> CoverageResult | None: ...