"""In-memory ``FakeKnowledgeStore`` (roadmap 09 shared mocks; Piyush-private).

Implements only the ``KnowledgeStore`` calls the ingestion pipeline (P5)
uses: ``prepare_ingestion``, ``activate_ingestion``, ``get_document`` plus
simple ``get_chunk``/``get_requirement`` reads. No SQL, no DB connection.

Behaviors mirrored from contract 16:

* ``prepare_ingestion`` performs no mutation; known source + identical active
  content -> ``existing_version_id == version_id``; unknown reingest source ->
  ``SOURCE_NOT_FOUND``.
* ``activate_ingestion`` is all-or-nothing: rows are staged, duplicate
  ``chunk_id`` in one batch raises ``INTERNAL_ERROR`` and prior state stays
  intact (mirrors the real store's tested rollback semantics).

The identity record is duck-typed (``source_id``/``document_id``/
``version_id``/``existing_version_id``) so the pipeline works with the real
``verity.storage.base.IngestionIdentity`` once PR-A2 merges without changes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from verity.errors import VerityError
from verity.ids import new_uuid4
from verity.models import (
    Chunk,
    Document,
    DocumentStatus,
    IngestResult,
    Requirement,
)


@dataclass(frozen=True)
class FakeIngestionIdentity:
    source_id: UUID
    document_id: UUID
    version_id: UUID
    existing_version_id: UUID | None


class FakeKnowledgeStore:
    """Minimal in-memory store used by P5 tests until PR-A2 merges."""

    def __init__(self) -> None:
        self.sources: dict[str, dict[str, Any]] = {}
        self.documents: dict[str, dict[str, Any]] = {}
        self.versions: dict[str, dict[str, Any]] = {}
        self.chunks: dict[str, Chunk] = {}
        self.requirements: dict[str, Requirement] = {}
        self.activation_calls = 0

    # -- contract 16 surface used by the pipeline --------------------------
    async def prepare_ingestion(self, request, content_sha256: str,
                                source_key: str | None) -> FakeIngestionIdentity:
        if request.source_id is not None:
            # Reingest of a registered source (contract 05).
            source_row = self.sources.get(str(request.source_id))
            if source_row is None:
                raise VerityError(
                    "SOURCE_NOT_FOUND", "reingest source is not registered",
                    {"source_id": str(request.source_id)},
                )
            source_id = request.source_id
            document_id = source_row["document_id"]
        else:
            # Contract 05: null source_id registers a NEW source.
            source_id, document_id = new_uuid4(), new_uuid4()

        active_version = self.documents.get(str(document_id), {}).get("active_version_id")
        if active_version is not None:
            version = self.versions[str(active_version)]
            if version["content_sha256"] == content_sha256:
                return FakeIngestionIdentity(source_id, document_id,
                                             version["version_id"], version["version_id"])
        return FakeIngestionIdentity(source_id, document_id, new_uuid4(), None)

    async def activate_ingestion(self, identity, request, parsed, chunks,
                                 requirements, spec_entities,
                                 original_bytes: bytes) -> IngestResult:
        self.activation_calls += 1
        # Stage-then-commit: duplicate chunk IDs in one batch must not commit.
        staged_chunk_ids = [c.chunk_id for c in chunks]
        if len(set(staged_chunk_ids)) != len(staged_chunk_ids):
            raise VerityError(
                "INTERNAL_ERROR",
                "ingestion activation failed; prior active version unchanged",
                {"reason": "duplicate chunk_id in batch"},
            )
        source_id = str(identity.source_id)
        document_id = str(identity.document_id)
        version_id = str(identity.version_id)
        name = request.source_path.rsplit("/", 1)[-1]
        self.sources.setdefault(source_id, {
            "source_id": identity.source_id, "source_path": request.source_path,
            "document_id": identity.document_id,
        })
        self.versions[version_id] = {
            "version_id": identity.version_id, "document_id": identity.document_id,
            "content_sha256": hashlib.sha256(original_bytes).hexdigest(),
        }
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk
        for requirement in requirements:
            self.requirements[requirement.requirement_id] = requirement
        document = Document(
            schema_version="1.0.0",
            document_id=document_id,
            source_id=source_id,
            version_id=version_id,
            name=name,
            media_type=parsed.media_type,
            kind=parsed.kind,
            status=DocumentStatus.READY,
            content_sha256=self.versions[version_id]["content_sha256"],
            metadata=parsed.metadata,
            indexed_at=None,
        )
        self.documents[document_id] = {
            "document": document, "active_version_id": identity.version_id,
        }
        return IngestResult(document=document, created_new_version=True)

    async def get_document(self, document_id: UUID) -> Document | None:
        row = self.documents.get(str(document_id))
        return row["document"] if row else None

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self.chunks.get(chunk_id)

    async def get_requirement(self, requirement_id: str) -> Requirement | None:
        return self.requirements.get(requirement_id)