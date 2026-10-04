"""Real-store P5 integration tests (PR-P2 gate: real write/idempotence/rollback).

Runs ``IngestionPipeline`` end-to-end through Atharv's SQLite
``SqliteKnowledgeStore`` (PR-A2): canonical rows written atomically with
originals at ``data/originals/<sha256>``, same-hash reingest idempotent,
changed content creating a new version whose historical evidence stays
resolvable (D3-approved version-bound ``Document``), and a failed activation
rolling back with the prior active version untouched.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path
from uuid import UUID

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from verity.errors import VerityError
from verity.ids import make_evidence_id, make_requirement_id
from verity.ingestion import IngestionPipeline
from verity.models import (
    DocumentKind,
    DocumentStatus,
    IngestRequest,
    SearchRequest,
)
from verity.storage import SqliteKnowledgeStore

FIXTURES = TESTS_DIR / "fixtures" / "contracts_v1"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path: Path):
    s = SqliteKnowledgeStore(tmp_path / "verity.sqlite3", tmp_path)
    s.open()
    yield s
    s.close()


@pytest.fixture()
def pipeline(store: SqliteKnowledgeStore) -> IngestionPipeline:
    return IngestionPipeline(store)


def request(path: str, source_id=None) -> IngestRequest:
    return IngestRequest(source_path=path, mode="auto", source_id=source_id)


def test_real_ingest_writes_rows_and_originals(
        pipeline: IngestionPipeline, store: SqliteKnowledgeStore,
        tmp_path: Path) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    result = run(pipeline.ingest(request("specs/payments.md"), data))
    assert result.created_new_version is True
    doc = result.document
    assert doc.kind is DocumentKind.SPEC
    assert doc.status is DocumentStatus.READY
    assert doc.content_sha256 == hashlib.sha256(data).hexdigest()

    # Original bytes stored exactly once at data/originals/<sha256>.
    originals = list((tmp_path / "originals").iterdir())
    assert [o.name for o in originals] == [doc.content_sha256]
    assert originals[0].read_bytes() == data

    # Chunk + evidence round trip through public reads.
    found = run(store.lexical_candidates(
        SearchRequest(query="refund window", document_ids=None,
                      document_kinds=None, chunk_kinds=None, limit=8), 50))
    assert found
    chunk_id = found[0].chunk.chunk_id
    chunk = run(store.get_chunk(chunk_id))
    assert chunk is not None and chunk.text.startswith("Refund window")
    origin = run(store.get_evidence_origin(
        make_evidence_id(doc.version_id, chunk_id)))
    assert origin is not None
    assert origin[1].version_id == doc.version_id

    # FTS index is live (lexical smoke).
    assert any(r.chunk.chunk_id == chunk_id for r in found)


def test_real_requirement_round_trip(
        pipeline: IngestionPipeline, store: SqliteKnowledgeStore) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    result = run(pipeline.ingest(request("specs/payments.md"), data))
    doc = result.document
    req_id = make_requirement_id(doc.source_id, "REQ-001")
    req = run(store.get_requirement(req_id))
    assert req is not None and req.local_id == "REQ-001"
    assert [c.local_id for c in req.acceptance_criteria] == ["AC-001"]
    chunk = run(store.get_chunk(req.chunk_id))
    assert chunk is not None and chunk.text.startswith("Refund window")


def test_real_same_hash_reingest_is_idempotent(
        pipeline: IngestionPipeline, store: SqliteKnowledgeStore) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    first = run(pipeline.ingest(request("specs/payments.md"), data))
    second = run(pipeline.ingest(
        request("specs/payments.md", source_id=first.document.source_id), data))
    assert second.created_new_version is False
    assert second.document.version_id == first.document.version_id
    rows = store.conn.execute(
        "SELECT COUNT(*) FROM document_versions WHERE document_id = ?",
        (first.document.document_id,),
    ).fetchone()[0]
    assert rows == 1


def test_real_changed_content_new_version_and_historical_origin(
        pipeline: IngestionPipeline, store: SqliteKnowledgeStore) -> None:
    data_v1 = (FIXTURES / "security.txt").read_bytes()
    first = run(pipeline.ingest(request("docs/security.txt"), data_v1))
    # Capture a v1 chunk through the lexical index.
    found = run(store.lexical_candidates(
        SearchRequest(query="idempotency", document_ids=None,
                      document_kinds=None, chunk_kinds=None, limit=8), 50))
    assert found
    first_chunk = found[0].chunk

    second = run(pipeline.ingest(
        request("docs/security.txt", source_id=first.document.source_id),
        data_v1 + b"\n\nRotate audit credentials every 30 days.\n"))
    assert second.created_new_version is True
    assert second.document.version_id != first.document.version_id
    rows = store.conn.execute(
        "SELECT COUNT(*) FROM document_versions WHERE document_id = ?",
        (first.document.document_id,),
    ).fetchone()[0]
    assert rows == 2

    # Active search only sees the new version (contract 06).
    active = run(store.lexical_candidates(
        SearchRequest(query="idempotency", document_ids=None,
                      document_kinds=None, chunk_kinds=None, limit=8), 50))
    assert first_chunk.chunk_id not in [r.chunk.chunk_id for r in active]

    # Historical evidence still resolves (D3-approved Option B: the returned
    # Document describes the evidence's version).
    origin = run(store.get_evidence_origin(
        make_evidence_id(first.document.version_id, first_chunk.chunk_id)))
    assert origin is not None
    chunk, doc, provenance = origin
    assert chunk.text == first_chunk.text
    assert doc.version_id == first.document.version_id
    assert provenance.content_sha256 == first.document.content_sha256


def test_real_failed_activation_rolls_back(
        pipeline: IngestionPipeline, store: SqliteKnowledgeStore) -> None:
    class DupChunkStore:
        """Delegates to the real store but corrupts the batch (one duplicate)."""

        def __init__(self, inner: SqliteKnowledgeStore) -> None:
            self._inner = inner

        async def prepare_ingestion(self, *args, **kwargs):
            return await self._inner.prepare_ingestion(*args, **kwargs)

        async def activate_ingestion(self, identity, request_, parsed, chunks,
                                     requirements, spec_entities, original_bytes):
            return await self._inner.activate_ingestion(
                identity, request_, parsed, (chunks[0], chunks[0]),
                requirements, spec_entities, original_bytes)

        async def get_document(self, *args, **kwargs):
            return await self._inner.get_document(*args, **kwargs)

    first = run(pipeline.ingest(
        request("specs/payments.md"), (FIXTURES / "payments.md").read_bytes()))
    bad = IngestionPipeline(DupChunkStore(store))
    with pytest.raises(VerityError) as exc:
        run(bad.ingest(request("specs/payments.md",
                               source_id=first.document.source_id),
                       (FIXTURES / "architecture.md").read_bytes()))
    assert exc.value.code == "INTERNAL_ERROR"
    # Prior active version untouched; failed version committed nothing.
    doc = run(store.get_document(UUID(first.document.document_id)))
    assert doc.version_id == first.document.version_id
    rows = store.conn.execute(
        "SELECT COUNT(*) FROM document_versions WHERE document_id = ?",
        (first.document.document_id,),
    ).fetchone()[0]
    assert rows == 1