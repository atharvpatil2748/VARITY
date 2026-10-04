"""SQLite persistence — the only SQL owner in VERITY (contract 13, v1).

``PRAGMA user_version = 1``; ``foreign_keys=ON``; WAL for local concurrent
reads. One writable connection serializes mutations; methods are async per
contract 16 and safe for concurrent readers.
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from ..errors import VerityError
from ..ids import make_block_id, make_evidence_id, new_uuid4
from ..models import (
    AcceptanceCriterion,
    Chunk,
    ChunkKind,
    Document,
    DocumentKind,
    DocumentMetadata,
    DocumentStatus,
    IngestRequest,
    IngestResult,
    ListPage,
    Locator,
    ParsedDocument,
    Provenance,
    Requirement,
    SearchRequest,
    Source,
    SpecEntity,
    CoverageResult,
    canonical_json,
)
from .base import IngestionIdentity, RankedChunk

SCHEMA_VERSION = "1.0.0"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
CHUNKER_VERSION = "1.0.0"

_FTS_SPECIAL = re.compile(r'["^~*:\-()\[\]{}]')

#: Sentinel: distinguish "no prepared observation" from an observed None.
_UNSET = object()


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fts_escape(query: str) -> str:
    """Escape each term for FTS5 MATCH; quoted phrases prevent syntax errors."""
    parts = []
    for term in query.split():
        cleaned = _FTS_SPECIAL.sub(" ", term).strip()
        if cleaned:
            parts.append(f'"{cleaned}"')
    return " ".join(parts)


class SqliteKnowledgeStore:
    """Concrete ``KnowledgeStore`` over one SQLite database (contract 16).

    ``db_path`` is the canonical database file; ``data_dir`` holds
    ``originals/<sha256>`` source bytes written atomically before DB
    activation (contract 13).
    """

    def __init__(self, db_path: str | Path, data_dir: str | Path) -> None:
        self._db_path = Path(db_path)
        self._data_dir = Path(data_dir)
        self._originals = self._data_dir / "originals"
        self._lock = asyncio.Lock()
        self._conn: sqlite3.Connection | None = None
        #: Active-version observations from prepare_ingestion, keyed by
        #: version_id, for stale-activation detection (contract 16).
        self._prepared_active: dict[str, str | None] = {}

    # -- connection lifecycle -------------------------------------------------

    def open(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._originals.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        self._conn = conn
        self._migrate()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise VerityError("INTERNAL_ERROR", "store is not open")
        return self._conn

    def _migrate(self) -> None:
        current = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if current > 1:
            raise VerityError(
                "VERSION_UNSUPPORTED",
                "database was created by a newer schema",
                {"expected_version": 1, "actual_version": current},
            )
        if current == 1:
            return
        migration = (MIGRATIONS_DIR / "0001_initial.sql").read_text(encoding="utf-8")
        with self.conn:
            self.conn.executescript(migration)
        if self.conn.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise VerityError("INTERNAL_ERROR", "migration did not set user_version=1")

    # -- row mappers ----------------------------------------------------------

    def _row_to_source(self, row: sqlite3.Row) -> Source:
        return Source(
            schema_version=row["schema_version"],
            source_id=row["source_id"],
            source_key=row["source_key"],
            source_path=row["source_path"],
            registered_at=row["registered_at"],
        )

    def _row_to_metadata(self, metadata_json: str) -> DocumentMetadata:
        return DocumentMetadata.from_dict(json.loads(metadata_json))

    def _row_to_document(self, row: sqlite3.Row) -> Document:
        version = self.conn.execute(
            "SELECT * FROM document_versions WHERE version_id = ?",
            (row["active_version_id"],),
        ).fetchone()
        if version is None:
            raise VerityError("INTERNAL_ERROR", "active version row missing")
        return Document(
            schema_version=row["schema_version"],
            document_id=row["document_id"],
            source_id=row["source_id"],
            version_id=version["version_id"],
            name=row["name"],
            media_type=row["media_type"],
            kind=DocumentKind(row["kind"]),
            status=DocumentStatus(row["status"]),
            content_sha256=version["content_sha256"],
            metadata=self._row_to_metadata(version["metadata_json"]),
            indexed_at=row["indexed_at"],
        )

    def _row_to_chunk(self, row: sqlite3.Row) -> Chunk:
        return Chunk(
            schema_version=row["schema_version"],
            chunk_id=row["chunk_id"],
            kind=ChunkKind(row["kind"]),
            text=row["text"],
            locator=Locator.from_dict(json.loads(row["locator_json"])),
            block_start=row["block_start"],
            block_end=row["block_end"],
            ordinal=row["ordinal"],
            requirement_id=row["requirement_id"],
        )

    def _provenance_for(
        self, version_row: sqlite3.Row, metadata: DocumentMetadata
    ) -> Provenance:
        return Provenance(
            schema_version=SCHEMA_VERSION,
            content_sha256=version_row["content_sha256"],
            parser_name=metadata.parser_name,
            parser_version=metadata.parser_version,
            chunker_version=version_row["chunker_version"],
            embedding_model=version_row["embedding_model"],
            indexed_at=version_row["indexed_at"] or version_row["created_at"],
        )


    # -- ingestion (contract 16) ----------------------------------------------

    async def prepare_ingestion(
        self, request: IngestRequest, content_sha256: str, source_key: str | None
    ) -> IngestionIdentity:
        """Allocate identity without mutation (contract 16).

        Known source + identical active content -> ``existing_version_id ==
        version_id``; new/changed content -> ``existing_version_id is None``.
        """
        async with self._lock:
            return self._prepare_ingestion(request, content_sha256, source_key)

    def _prepare_ingestion(
        self, request: IngestRequest, content_sha256: str, source_key: str | None
    ) -> IngestionIdentity:
        if request.source_id is not None:
            source_row = self.conn.execute(
                "SELECT * FROM sources WHERE source_id = ?", (request.source_id,)
            ).fetchone()
            if source_row is None:
                raise VerityError(
                    "SOURCE_NOT_FOUND",
                    "reingest source is not registered",
                    {"source_id": request.source_id},
                )
            source_id = UUID(source_row["source_id"])
            document_row = self.conn.execute(
                "SELECT document_id FROM documents WHERE source_id = ?",
                (request.source_id,),
            ).fetchone()
            if document_row is None:
                raise VerityError(
                    "DOCUMENT_NOT_FOUND",
                    "registered source has no document",
                    {"source_id": request.source_id},
                )
            document_id = UUID(document_row["document_id"])
        else:
            source_id = new_uuid4()
            document_id = new_uuid4()

        existing = self.conn.execute(
            "SELECT v.version_id FROM document_versions v "
            "JOIN documents d ON d.document_id = v.document_id "
            "WHERE d.document_id = ? AND v.content_sha256 = ? "
            "AND d.active_version_id = v.version_id",
            (str(document_id), content_sha256),
        ).fetchone()
        if existing is not None:
            version_id = UUID(existing["version_id"])
            return IngestionIdentity(source_id, document_id, version_id, version_id)
        version_id = new_uuid4()
        # Observe the current active version for stale-activation detection:
        # activate_ingestion must not overwrite a version activated after this
        # preparation (contract 16).
        doc_row = self.conn.execute(
            "SELECT active_version_id FROM documents WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()
        self._prepared_active[str(version_id)] = (
            doc_row["active_version_id"] if doc_row else None
        )
        return IngestionIdentity(source_id, document_id, version_id, None)


    async def activate_ingestion(
        self,
        identity: IngestionIdentity,
        request: IngestRequest,
        parsed: ParsedDocument,
        chunks: tuple[Chunk, ...],
        requirements: tuple[Requirement, ...],
        spec_entities: tuple[SpecEntity, ...],
        original_bytes: bytes,
    ) -> IngestResult:
        """Write source/document/version/blocks/chunks/spec rows atomically.

        Original bytes are stored at ``data/originals/<sha256>`` atomically
        before DB activation. Any failure rolls back DB activation and leaves
        the old active version usable (contract 13).
        """
        import hashlib
        import os

        content_sha256 = hashlib.sha256(original_bytes).hexdigest()
        original_relpath = f"originals/{content_sha256}"
        final_path = self._originals / content_sha256
        if not final_path.exists():
            tmp_path = self._originals / f".{content_sha256}.tmp"
            tmp_path.write_bytes(original_bytes)
            os.replace(tmp_path, final_path)

        async with self._lock:
            return self._activate_ingestion(
                identity, request, parsed, chunks, requirements, spec_entities,
                content_sha256, original_relpath,
            )

    def _insert_requirements(
        self,
        requirements: tuple[Requirement, ...],
        spec_entities: tuple[SpecEntity, ...],
        version_id: str,
    ) -> None:
        conn = self.conn
        for entity in spec_entities:
            conn.execute(
                "INSERT INTO spec_entities (version_id, local_id, kind, title, text,"
                " reference_ids_json, chunk_id, locator_json, schema_version)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (version_id, entity.local_id, entity.kind.value, entity.title,
                 entity.text, canonical_json(entity.reference_ids), entity.chunk_id,
                 canonical_json(entity.locator.to_dict()), SCHEMA_VERSION),
            )
        for requirement in requirements:
            conn.execute(
                "INSERT INTO requirements (version_id, requirement_id, source_id,"
                " document_id, local_id, title, text, constraints_json,"
                " edge_cases_json, api_refs_json, reference_ids_json, chunk_id,"
                " locator_json, schema_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (version_id, requirement.requirement_id, requirement.source_id,
                 requirement.document_id, requirement.local_id, requirement.title,
                 requirement.text, canonical_json(requirement.constraints),
                 canonical_json(requirement.edge_cases),
                 canonical_json(requirement.api_refs),
                 canonical_json(requirement.reference_ids), requirement.chunk_id,
                 canonical_json(requirement.locator.to_dict()), SCHEMA_VERSION),
            )
            for ordinal, criterion in enumerate(requirement.acceptance_criteria):
                conn.execute(
                    "INSERT INTO requirement_acceptance (version_id, requirement_id,"
                    " ac_local_id, ordinal) VALUES (?,?,?,?)",
                    (version_id, requirement.requirement_id, criterion.local_id,
                     ordinal),
                )


    def _activate_ingestion(
        self,
        identity: IngestionIdentity,
        request: IngestRequest,
        parsed: ParsedDocument,
        chunks: tuple[Chunk, ...],
        requirements: tuple[Requirement, ...],
        spec_entities: tuple[SpecEntity, ...],
        content_sha256: str,
        original_relpath: str,
    ) -> IngestResult:
        now = _utcnow()
        source_id = str(identity.source_id)
        document_id = str(identity.document_id)
        version_id = str(identity.version_id)
        name = request.source_path.rsplit("/", 1)[-1]
        conn = self.conn
        try:
            with conn:
                conn.execute(
                    "INSERT OR IGNORE INTO sources (source_id, source_key,"
                    " source_path, registered_at, schema_version) VALUES (?,?,?,?,?)",
                    (source_id, None, request.source_path, now, SCHEMA_VERSION),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO documents (document_id, source_id, name,"
                    " media_type, kind, status, active_version_id, indexed_at,"
                    " schema_version) VALUES (?,?,?,?,?,'pending',NULL,NULL,?)",
                    (document_id, source_id, name, parsed.media_type,
                     parsed.kind.value, SCHEMA_VERSION),
                )
                # Stale-activation guard (contract 16): capture the currently
                # active version and refuse to overwrite a newer one.
                current = conn.execute(
                    "SELECT active_version_id FROM documents WHERE document_id = ?",
                    (document_id,),
                ).fetchone()["active_version_id"]
                expected = self._prepared_active.pop(version_id, _UNSET)
                if expected is not _UNSET and expected != current:
                    raise VerityError(
                        "INTERNAL_ERROR",
                        "conflicting activation; retry preparation",
                        {"reason": "active version changed since preparation"},
                    )
                conn.execute(
                    "INSERT INTO document_versions (version_id, document_id,"
                    " content_sha256, metadata_json, original_relpath, created_at,"
                    " indexed_at, chunker_version, embedding_model, status,"
                    " schema_version) VALUES (?,?,?,?,?,?,?,?,NULL,'ready',?)",
                    (version_id, document_id, content_sha256,
                     canonical_json(parsed.metadata.to_dict()), original_relpath,
                     now, now, CHUNKER_VERSION, SCHEMA_VERSION),
                )
                # Blocks: IDs assigned here (central materializer role).
                for block in parsed.blocks:
                    conn.execute(
                        "INSERT INTO blocks (block_id, version_id, ordinal, text,"
                        " block_type, page, heading_path_json, start_line, end_line,"
                        " start_offset, end_offset, schema_version)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (make_block_id(identity.version_id, block.ordinal, block.text),
                         version_id, block.ordinal, block.text, block.block_type,
                         block.page, canonical_json(block.heading_path),
                         block.start_line, block.end_line, block.start_offset,
                         block.end_offset, SCHEMA_VERSION),
                    )
                for chunk in chunks:
                    heading_text = " / ".join(chunk.locator.heading_path)
                    conn.execute(
                        "INSERT INTO chunks (chunk_id, version_id, kind, text,"
                        " heading_text, locator_json, block_start, block_end,"
                        " ordinal, requirement_id, schema_version)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (chunk.chunk_id, version_id, chunk.kind.value, chunk.text,
                         heading_text, canonical_json(chunk.locator.to_dict()),
                         chunk.block_start, chunk.block_end, chunk.ordinal,
                         chunk.requirement_id, SCHEMA_VERSION),
                    )
                    conn.execute(
                        "INSERT INTO evidence_refs (evidence_id, version_id, chunk_id)"
                        " VALUES (?,?,?)",
                        (make_evidence_id(identity.version_id, chunk.chunk_id),
                         version_id, chunk.chunk_id),
                    )
                self._insert_requirements(requirements, spec_entities, version_id)
                # Activate only after all canonical rows commit (contract 13).
                # CAS on the captured active version: never overwrite a newer
                # active version (contract 16).
                cursor = conn.execute(
                    "UPDATE documents SET active_version_id = ?, indexed_at = ?,"
                    " status = 'ready' WHERE document_id = ?"
                    " AND active_version_id IS ?",
                    (version_id, now, document_id, current),
                )
                if cursor.rowcount != 1:
                    raise VerityError(
                        "INTERNAL_ERROR",
                        "conflicting activation; retry preparation",
                        {"reason": "active version changed during activation"},
                    )
        except sqlite3.IntegrityError as exc:
            raise VerityError(
                "INTERNAL_ERROR",
                "ingestion activation failed; prior active version unchanged",
                {"reason": str(exc)},
            ) from exc

        final_doc = self.conn.execute(
            "SELECT * FROM documents WHERE document_id = ?", (document_id,)
        ).fetchone()
        return IngestResult(
            document=self._row_to_document(final_doc),
            created_new_version=identity.existing_version_id is None,
        )


    # -- read methods (contract 16) -------------------------------------------

    async def get_document(self, document_id: UUID) -> Document | None:
        row = self.conn.execute(
            "SELECT * FROM documents WHERE document_id = ?", (str(document_id),)
        ).fetchone()
        return self._row_to_document(row) if row else None

    async def list_documents(
        self, limit: int, offset: int, kind: DocumentKind | None
    ) -> ListPage:
        if kind is None:
            rows = self.conn.execute(
                "SELECT * FROM documents ORDER BY name LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        else:
            rows = self.conn.execute(
                "SELECT * FROM documents WHERE kind = ? ORDER BY name LIMIT ? OFFSET ?",
                (kind.value, limit, offset),
            ).fetchall()
            total = self.conn.execute(
                "SELECT COUNT(*) FROM documents WHERE kind = ?", (kind.value,)
            ).fetchone()[0]
        return ListPage(
            items=[self._row_to_document(r) for r in rows],
            total=total, limit=limit, offset=offset,
        )

    async def list_sources(self, limit: int, offset: int) -> ListPage:
        rows = self.conn.execute(
            "SELECT * FROM sources ORDER BY registered_at LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        return ListPage(
            items=[self._row_to_source(r) for r in rows],
            total=total, limit=limit, offset=offset,
        )

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        row = self.conn.execute(
            "SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        return self._row_to_chunk(row) if row else None

    async def get_requirement(self, requirement_id: str) -> Requirement | None:
        row = self.conn.execute(
            "SELECT r.* FROM requirements r "
            "JOIN documents d ON d.document_id = r.document_id "
            "AND d.active_version_id = r.version_id "
            "WHERE r.requirement_id = ?",
            (requirement_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_requirement(row)

    def _row_to_requirement(self, row: sqlite3.Row) -> Requirement:
        criteria_rows = self.conn.execute(
            "SELECT s.* FROM requirement_acceptance a "
            "JOIN spec_entities s ON s.version_id = a.version_id "
            "AND s.local_id = a.ac_local_id "
            "WHERE a.version_id = ? AND a.requirement_id = ? ORDER BY a.ordinal",
            (row["version_id"], row["requirement_id"]),
        ).fetchall()
        criteria = [
            AcceptanceCriterion(
                local_id=s["local_id"], title=s["title"], text=s["text"],
                locator=Locator.from_dict(json.loads(s["locator_json"])),
            )
            for s in criteria_rows
        ]
        locator = Locator.from_dict(json.loads(row["locator_json"]))
        return Requirement(
            schema_version=row["schema_version"],
            requirement_id=row["requirement_id"],
            local_id=row["local_id"],
            source_id=row["source_id"],
            document_id=row["document_id"],
            version_id=row["version_id"],
            title=row["title"],
            text=row["text"],
            chunk_id=row["chunk_id"],
            evidence_id=make_evidence_id(UUID(row["version_id"]), row["chunk_id"]),
            locator=locator,
            constraints=json.loads(row["constraints_json"]),
            edge_cases=json.loads(row["edge_cases_json"]),
            acceptance_criteria=criteria,
            api_refs=json.loads(row["api_refs_json"]),
            reference_ids=json.loads(row["reference_ids_json"]),
        )


    async def get_evidence_origin(
        self, evidence_id: str
    ) -> tuple[Chunk, Document, Provenance] | None:
        row = self.conn.execute(
            "SELECT c.*, v.document_id, v.content_sha256, v.metadata_json,"
            " v.created_at, v.indexed_at, v.chunker_version, v.embedding_model,"
            " d.name, d.media_type, d.kind AS d_kind, d.status,"
            " d.indexed_at AS d_indexed_at, d.schema_version AS d_schema,"
            " d.source_id FROM evidence_refs e "
            "JOIN chunks c ON c.chunk_id = e.chunk_id "
            "JOIN document_versions v ON v.version_id = e.version_id "
            "JOIN documents d ON d.document_id = v.document_id "
            "WHERE e.evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        if row is None:
            return None
        chunk = self._row_to_chunk(row)
        metadata = DocumentMetadata.from_dict(json.loads(row["metadata_json"]))
        document = Document(
            schema_version=row["d_schema"],
            document_id=row["document_id"],
            source_id=row["source_id"],
            version_id=row["version_id"],
            name=row["name"],
            media_type=row["media_type"],
            kind=DocumentKind(row["d_kind"]),
            status=DocumentStatus(row["status"]),
            content_sha256=row["content_sha256"],
            metadata=metadata,
            indexed_at=row["d_indexed_at"],
        )
        provenance = self._provenance_for(row, metadata)
        return chunk, document, provenance

    # -- retrieval candidates (contract 06 inputs; ranking is Piyush's) --------

    def _search_filters(self, request: SearchRequest) -> tuple[str, list[Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if request.document_ids is not None:
            marks = ",".join("?" for _ in request.document_ids)
            clauses.append(f"v.document_id IN ({marks})")
            params.extend(request.document_ids)
        if request.document_kinds is not None:
            marks = ",".join("?" for _ in request.document_kinds)
            clauses.append(f"d.kind IN ({marks})")
            params.extend(k.value for k in request.document_kinds)
        if request.chunk_kinds is not None:
            marks = ",".join("?" for _ in request.chunk_kinds)
            clauses.append(f"c.kind IN ({marks})")
            params.extend(k.value for k in request.chunk_kinds)
        return " AND ".join(clauses), params

    async def lexical_candidates(
        self, request: SearchRequest, limit: int
    ) -> tuple[RankedChunk, ...]:
        match = _fts_escape(request.query)
        if not match:
            return ()
        filters, params = self._search_filters(request)
        rows = self.conn.execute(
            "SELECT c.*, bm25(fts_chunks) AS score FROM fts_chunks "
            "JOIN chunks c ON c.rowid = fts_chunks.rowid "
            "JOIN document_versions v ON v.version_id = c.version_id "
            "JOIN documents d ON d.document_id = v.document_id "
            "AND d.active_version_id = v.version_id "
            f"WHERE fts_chunks MATCH ? AND {filters} "
            "ORDER BY score LIMIT ?",
            [match, *params, limit],
        ).fetchall()
        out = []
        for rank, row in enumerate(rows, start=1):
            out.append(RankedChunk(
                chunk=self._row_to_chunk(row), rank=rank,
                raw_score=float(row["score"]),
            ))
        return tuple(out)

    async def vector_candidates(
        self,
        query_vector: tuple[float, ...],
        request: SearchRequest,
        model_id: str,
        limit: int,
    ) -> tuple[RankedChunk, ...]:
        import struct

        filters, params = self._search_filters(request)
        rows = self.conn.execute(
            "SELECT c.*, e.vector_f32le FROM embeddings e "
            "JOIN chunks c ON c.chunk_id = e.chunk_id "
            "JOIN document_versions v ON v.version_id = c.version_id "
            "JOIN documents d ON d.document_id = v.document_id "
            "AND d.active_version_id = v.version_id "
            f"WHERE e.model_id = ? AND {filters}",
            [model_id, *params],
        ).fetchall()
        qnorm = sum(x * x for x in query_vector) ** 0.5 or 1.0
        scored = []
        for row in rows:
            vector = struct.unpack(f"{len(row['vector_f32le']) // 4}f",
                                   row["vector_f32le"])
            if len(vector) != len(query_vector):
                continue
            dot = sum(a * b for a, b in zip(query_vector, vector))
            scored.append((dot / qnorm, row))
        scored.sort(key=lambda item: (-item[0], item[1]["chunk_id"]))
        return tuple(
            RankedChunk(chunk=self._row_to_chunk(row), rank=rank,
                        raw_score=float(score))
            for rank, (score, row) in enumerate(scored[:limit], start=1)
        )


    # -- embedding writes (private store path; contract 13) --------------------

    def save_embedding(
        self, chunk_id: str, model_id: str, vector: tuple[float, ...], text: str
    ) -> None:
        """Persist one normalized embedding (little-endian float32 BLOB).

        Not part of the frozen ``KnowledgeStore`` protocol — used by the
        ingestion pipeline after canonical activation (contract 16 has no
        embedding write call; noted in PR-A2 as a boundary gap). The vector
        is normalized here (contract 13 stores normalized vectors) and bound
        to the exact embedded text via ``text_sha256``.
        """
        import hashlib
        import struct

        if not vector:
            raise VerityError("INVALID_REQUEST", "embedding vector must be nonempty")
        norm = sum(x * x for x in vector) ** 0.5
        if norm == 0:
            raise VerityError("INVALID_REQUEST", "embedding vector must be nonzero")
        normalized = tuple(x / norm for x in vector)
        text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        blob = struct.pack(f"{len(normalized)}f", *normalized)
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO embeddings (chunk_id, model_id, dimension,"
                " vector_f32le, text_sha256, created_at) VALUES (?,?,?,?,?,?)",
                (chunk_id, model_id, len(normalized), blob, text_sha256, _utcnow()),
            )

    # -- coverage persistence (Vanashree computes; Atharv persists) -----------

    async def save_coverage(self, result: CoverageResult) -> None:
        """Persist an immutable coverage run (contract 03/16).

        ``coverage_id`` is an immutable run identity: re-saving the same ID
        raises, it never overwrites.
        """
        async with self._lock:
            try:
                with self.conn:
                    self.conn.execute(
                        "INSERT INTO coverage_runs (coverage_id, workspace_id,"
                        " workspace_revision, inspected_at, report_json,"
                        " schema_version) VALUES (?,?,?,?,?,?)",
                        (str(result.coverage_id), result.workspace_id,
                         result.workspace_revision, result.inspected_at,
                         canonical_json(result.to_dict()), SCHEMA_VERSION),
                    )
            except sqlite3.IntegrityError as exc:
                raise VerityError(
                    "INTERNAL_ERROR",
                    "coverage run already exists; reports are immutable",
                    {"coverage_id": str(result.coverage_id)},
                ) from exc

    async def get_coverage(self, coverage_id: UUID) -> CoverageResult | None:
        row = self.conn.execute(
            "SELECT report_json FROM coverage_runs WHERE coverage_id = ?",
            (str(coverage_id),),
        ).fetchone()
        if row is None:
            return None
        return CoverageResult.from_dict(json.loads(row["report_json"]))

    # -- FTS maintenance (contract 13: rebuild and delete are tested) ---------

    def rebuild_fts(self) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO fts_chunks(fts_chunks) VALUES('rebuild')")