"""Storage contract tests: migration, write, FTS, rollback, idempotence, restart.

PR-A2 gate per roadmap 02: migration/write/FTS/rollback tests.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID

import pytest

from verity.errors import VerityError
from verity.ids import make_chunk_id, make_evidence_id
from verity.models import (
    Chunk,
    ChunkKind,
    DocumentKind,
    DocumentStatus,
    DocumentMetadata,
    IngestRequest,
    Locator,
    ParsedBlock,
    ParsedDocument,
    Requirement,
    SearchRequest,
    SpecEntity,
)
from verity.storage import IngestionIdentity, SqliteKnowledgeStore

VERSION_ID = UUID("129dcd06-1ba1-4f0c-bf7e-c678f905b624")
SOURCE_ID = UUID("24da624f-7fd0-41ea-a49b-8449cbb179d9")
DOCUMENT_ID = UUID("ebc2352e-ff9c-4167-b11a-1e30d550411d")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path: Path):
    s = SqliteKnowledgeStore(tmp_path / "verity.sqlite3", tmp_path)
    s.open()
    yield s
    s.close()


def _metadata() -> DocumentMetadata:
    return DocumentMetadata(
        metadata_version="1.0.0", title="Payments", source_key="payments-api",
        project="payment-service", spec_version="1.0", language="en",
        page_count=None, parser_name="markdown", parser_version="1.0.0", warnings=[],
    )


def _parsed(text: str = "Refund requests MUST be accepted only within 30 days.") -> ParsedDocument:
    return ParsedDocument(
        metadata=_metadata(),
        blocks=[ParsedBlock(
            ordinal=0, text=text, block_type="paragraph", page=None,
            start_line=1, end_line=1, start_offset=None, end_offset=None,
            heading_path=["Requirements"],
        )],
        media_type="text/markdown",
        kind=DocumentKind.SPEC,
        spec_requirements=[],
        spec_entities=[],
    )


def _locator() -> Locator:
    return Locator(
        source_id=str(SOURCE_ID), document_id=str(DOCUMENT_ID),
        version_id=str(VERSION_ID), source_path="specs/payments.md", page=None,
        start_line=1, end_line=1, start_offset=None, end_offset=None,
        heading_path=["Requirements"],
    )


def _chunk(version_id: UUID, text: str, ordinal: int = 0) -> Chunk:
    draft_kwargs = dict(
        kind=ChunkKind.REQUIREMENT, text=text, block_start=0, block_end=0,
        start_offset=None, end_offset=None, requirement_id=None,
    )
    from verity.models import ChunkDraft

    draft = ChunkDraft(**draft_kwargs)
    locator = _locator()
    object.__setattr__(locator, "version_id", str(version_id))
    return Chunk(
        schema_version="1.0.0", chunk_id=make_chunk_id(version_id, draft),
        kind=ChunkKind.REQUIREMENT, text=text, locator=locator,
        block_start=0, block_end=0, ordinal=ordinal, requirement_id=None,
    )


def _ingest(store: SqliteKnowledgeStore, bytes_: bytes, source_id=None, source_key=None):
    request = IngestRequest(source_path="specs/payments.md",
                            mode="auto", source_id=source_id)
    import hashlib

    sha = hashlib.sha256(bytes_).hexdigest()
    identity = run(store.prepare_ingestion(request, sha, source_key))
    text = bytes_.decode("utf-8")
    chunk = _chunk(identity.version_id, text)
    if identity.existing_version_id is not None:
        # Contract 16: coordinator returns the current IngestResult without
        # reindexing when the active content is identical.
        from verity.models import IngestResult

        doc = run(store.get_document(identity.document_id))
        return identity, IngestResult(document=doc, created_new_version=False), chunk
    parsed = _parsed(text)
    result = run(store.activate_ingestion(
        identity, request, parsed, (chunk,), (), (), bytes_,
    ))
    return identity, result, chunk


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def test_migration_sets_user_version(store: SqliteKnowledgeStore) -> None:
    assert store.conn.execute("PRAGMA user_version").fetchone()[0] == 1
    tables = {r[0] for r in store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sources", "documents", "document_versions", "blocks", "chunks",
            "requirements", "spec_entities", "requirement_acceptance",
            "embeddings", "evidence_refs", "coverage_runs",
            "fts_chunks"} <= tables


def test_reopen_is_idempotent(store: SqliteKnowledgeStore, tmp_path: Path) -> None:
    store.close()
    again = SqliteKnowledgeStore(tmp_path / "verity.sqlite3", tmp_path)
    again.open()  # no error, user_version already 1
    assert again.conn.execute("PRAGMA user_version").fetchone()[0] == 1
    again.close()


def test_newer_user_version_unsupported(tmp_path: Path) -> None:
    import sqlite3

    conn = sqlite3.connect(tmp_path / "newer.sqlite3")
    conn.execute("PRAGMA user_version = 7")
    conn.close()
    s = SqliteKnowledgeStore(tmp_path / "newer.sqlite3", tmp_path)
    with pytest.raises(VerityError) as exc:
        s.open()
    assert exc.value.code == "VERSION_UNSUPPORTED"


# ---------------------------------------------------------------------------
# Write + read round trip
# ---------------------------------------------------------------------------


def test_ingest_and_read_back(store: SqliteKnowledgeStore) -> None:
    text = "Refund requests MUST be accepted only within 30 days."
    identity, result, chunk = _ingest(store, text.encode())
    assert result.created_new_version is True
    assert result.document.status is DocumentStatus.READY
    assert result.document.version_id == str(identity.version_id)
    # Original bytes stored at data/originals/<sha256>.
    originals = list((store._originals).iterdir())
    assert len(originals) == 1 and originals[0].name == result.document.content_sha256

    doc = run(store.get_document(identity.document_id))
    assert doc is not None and doc.document_id == str(identity.document_id)
    fetched = run(store.get_chunk(chunk.chunk_id))
    assert fetched is not None and fetched.text == text
    origin = run(store.get_evidence_origin(
        make_evidence_id(identity.version_id, chunk.chunk_id)))
    assert origin is not None
    got_chunk, got_doc, provenance = origin
    assert got_chunk.chunk_id == chunk.chunk_id
    assert got_doc.name == "payments.md"
    assert provenance.parser_name == "markdown"


def test_prepare_no_mutation(store: SqliteKnowledgeStore) -> None:
    request = IngestRequest(source_path="specs/payments.md")
    identity = run(store.prepare_ingestion(request, "a" * 64, None))
    assert isinstance(identity, IngestionIdentity)
    assert identity.existing_version_id is None
    count = store.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    assert count == 0  # prepare must not mutate


def test_reingest_same_content_is_idempotent(store: SqliteKnowledgeStore) -> None:
    text = "Identical content on reingest."
    _, first, _ = _ingest(store, text.encode())
    identity, second, _ = _ingest(
        store, text.encode(), source_id=first.document.source_id)
    assert second.created_new_version is False
    assert identity.existing_version_id == identity.version_id
    versions = store.conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0]
    assert versions == 1


def test_changed_content_creates_new_version(store: SqliteKnowledgeStore) -> None:
    text_v1 = "Version one text."
    _, first, chunk_v1 = _ingest(store, text_v1.encode())
    identity, second, chunk_v2 = _ingest(
        store, b"Version two text.", source_id=first.document.source_id)
    assert second.created_new_version is True
    assert second.document.version_id != str(first.document.version_id)
    # Old version stays resolvable for historical citations (contract 13).
    old = run(store.get_evidence_origin(
        make_evidence_id(UUID(first.document.version_id), chunk_v1.chunk_id)))
    assert old is not None
    assert old[0].text == text_v1


def test_unknown_source_reingest_fails(store: SqliteKnowledgeStore) -> None:
    request = IngestRequest(source_path="x.md", source_id=str(SOURCE_ID))
    with pytest.raises(VerityError) as exc:
        run(store.prepare_ingestion(request, "b" * 64, None))
    assert exc.value.code == "SOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# FTS
# ---------------------------------------------------------------------------


def test_lexical_search_and_escaping(store: SqliteKnowledgeStore) -> None:
    _, _, chunk = _ingest(store, b"Refund window policy for payments.")
    req = SearchRequest(query="refund window", document_ids=None,
                        document_kinds=None, chunk_kinds=None, limit=8)
    results = run(store.lexical_candidates(req, 50))
    assert len(results) >= 1
    assert results[0].chunk.chunk_id == chunk.chunk_id
    assert results[0].rank == 1
    # FTS special characters must not raise.
    evil = SearchRequest(query='refund " OR (', document_ids=None,
                         document_kinds=None, chunk_kinds=None, limit=8)
    run(store.lexical_candidates(evil, 50))  # no exception


def test_fts_delete_trigger(store: SqliteKnowledgeStore) -> None:
    _, _, chunk = _ingest(store, b"Deletable content for fts test.")
    assert store.conn.execute(
        "SELECT COUNT(*) FROM fts_chunks WHERE fts_chunks MATCH 'deletable'"
    ).fetchone()[0] == 1
    with store.conn:
        store.conn.execute(
            "DELETE FROM evidence_refs WHERE chunk_id = ?", (chunk.chunk_id,))
        store.conn.execute("DELETE FROM chunks WHERE chunk_id = ?", (chunk.chunk_id,))
    assert store.conn.execute(
        "SELECT COUNT(*) FROM fts_chunks WHERE fts_chunks MATCH 'deletable'"
    ).fetchone()[0] == 0


def test_fts_rebuild(store: SqliteKnowledgeStore) -> None:
    _, _, _ = _ingest(store, b"Rebuildable content.")
    store.rebuild_fts()  # must not error; index rebuilt from chunks
    assert store.conn.execute(
        "SELECT COUNT(*) FROM fts_chunks WHERE fts_chunks MATCH 'rebuildable'"
    ).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def test_activation_failure_rolls_back(store: SqliteKnowledgeStore) -> None:
    _, first, _ = _ingest(store, b"Stable v1 content.")
    request = IngestRequest(source_path="specs/payments.md",
                            source_id=first.document.source_id)
    identity = run(store.prepare_ingestion(request, "c" * 64, None))
    # Craft a failure: duplicate chunk_id within the same activation batch.
    chunk = _chunk(identity.version_id, "Will fail.")
    bad = (chunk, chunk)
    with pytest.raises(VerityError) as exc:
        run(store.activate_ingestion(
            identity, request, _parsed("Will fail."), bad, (), (), b"x"))
    assert exc.value.code == "INTERNAL_ERROR"
    # Prior active version untouched and still usable.
    doc = run(store.get_document(UUID(first.document.document_id)))
    assert doc.version_id == first.document.version_id
    # Failed version row must not exist (transaction rolled back).
    rows = store.conn.execute(
        "SELECT COUNT(*) FROM document_versions WHERE version_id = ?",
        (str(identity.version_id),),
    ).fetchone()[0]
    assert rows == 0