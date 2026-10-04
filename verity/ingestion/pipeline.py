"""Ingestion coordinator (contract 05/16, P5; owner Piyush).

``IngestionPipeline.ingest(request, data)`` implements the frozen flow:

1. Validate the request **before** parsing (contract 05): path must be a
   relative path without traversal, media type must be supported
   (``UNSUPPORTED_FORMAT``), data must be at most ``MAX_BYTES`` (25 MiB, the
   contract 11 upload bound -> ``LIMIT_EXCEEDED``), and text formats must be
   valid UTF-8 (``PARSER_ERROR``).
2. Parse with the mode-aware router (``auto``/``spec``/``general``); parser
   errors (``PARSER_ERROR``/``SPEC_VALIDATION_ERROR``/``VERSION_UNSUPPORTED``)
   and chunker errors (``CHUNKING_ERROR``) propagate as typed ``VerityError``.
3. ``KnowledgeStore.prepare_ingestion`` allocates identity without mutation.
   For identical active content (``existing_version_id == version_id``) the
   current ``IngestResult`` is returned without reindexing (idempotent
   reingest).
4. Otherwise chunk -> central materializer (canonical ``verity.ids``) ->
   ``activate_ingestion`` commits everything atomically; a store failure
   rolls back and leaves the prior active version untouched.

The pipeline talks to any contract-16 ``KnowledgeStore``; tests use
``FakeKnowledgeStore`` until PR-A2 merges the SQLite store. Records cross the
store boundary as typed ``verity.models`` objects.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from verity import ids as verity_ids
from verity.errors import VerityError
from verity.models import (
    Chunk,
    Document,
    IngestMode,
    IngestRequest,
    IngestResult,
    ParsedDocument,
    Requirement,
    SpecEntity,
)

from .chunking import CentralMaterializer, GeneralChunker
from .parsers import ParserRouter, media_type_for, resolve_kind

#: Contract 11 ``POST /documents`` upload bound; the coordinator enforces it.
MAX_BYTES = 25 * 1024 * 1024

_TRAVERSAL_RE = re.compile(r"(^|/)\.\.(/|$)")


class IngestionPipeline:
    """Contract-16 ``IngestionCoordinator`` over a ``KnowledgeStore``."""

    def __init__(self, store: Any, max_bytes: int = MAX_BYTES,
                 router: ParserRouter | None = None,
                 chunker: GeneralChunker | None = None,
                 materializer: CentralMaterializer | None = None) -> None:
        self._store = store
        self._max_bytes = max_bytes
        self._router = router or ParserRouter()
        self._chunker = chunker or GeneralChunker()
        self._materializer = materializer or CentralMaterializer(verity_ids)

    async def ingest(self, request: IngestRequest, data: bytes) -> IngestResult:
        parsed = self._validate_and_parse(request, data)
        content_sha256 = hashlib.sha256(data).hexdigest()
        identity = await self._store.prepare_ingestion(
            request, content_sha256, parsed["metadata"]["source_key"]
        )
        if identity.existing_version_id is not None:
            # Contract 16: identical active content -> return the current
            # result without reindexing.
            current = await self._store.get_document(identity.document_id)
            if current is None:
                raise VerityError(
                    "INTERNAL_ERROR",
                    "existing version has no active document",
                    {"document_id": str(identity.document_id)},
                )
            return IngestResult(document=current, created_new_version=False)

        drafts = self._chunker.chunk(parsed, identity.version_id)
        rows = self._materializer.materialize(
            parsed, drafts,
            identity.source_id, identity.document_id, identity.version_id,
            request.source_path,
        )
        return await self._store.activate_ingestion(
            identity, request,
            ParsedDocument.from_dict(parsed),
            tuple(Chunk.from_dict(row) for row in rows["chunks"]),
            tuple(Requirement.from_dict(row) for row in rows["requirements"]),
            tuple(SpecEntity.from_dict(row) for row in rows["spec_entities"]),
            data,
        )

    # -- step 1: validate before parsing (contract 05) ---------------------
    def _validate_and_parse(self, request: IngestRequest, data: bytes) -> dict:
        request.validate()  # bounds, UUIDv4 source_id, absolute path
        source_path = request.source_path
        if _TRAVERSAL_RE.search(source_path) or source_path.startswith("\\"):
            raise VerityError(
                "INVALID_REQUEST",
                "source_path must not contain path traversal",
                {"field": "source_path"},
            )
        if len(data) > self._max_bytes:
            raise VerityError(
                "LIMIT_EXCEEDED",
                f"document exceeds the {self._max_bytes} byte ingest bound",
                {"field": "data", "size": len(data), "limit": self._max_bytes},
            )
        filename = source_path.rsplit("/", 1)[-1]
        media_type = media_type_for(filename)
        if resolve_kind(media_type, filename) is None:
            raise VerityError(
                "UNSUPPORTED_FORMAT",
                f"unsupported document type: {filename!r}",
                {"file": source_path},
            )
        mode = request.mode.value if isinstance(request.mode, IngestMode) else str(request.mode)
        if not data.startswith(b"%PDF-"):
            try:
                data.decode("utf-8")  # strict; text formats must be UTF-8
            except UnicodeDecodeError as exc:
                raise VerityError(
                    "PARSER_ERROR", "document is not valid UTF-8",
                    {"file": source_path, "line": None},
                ) from exc
        return self._router.parse_for_mode(data, source_path, media_type, mode)