"""Ingestion pipeline (P5) tests against FakeKnowledgeStore (roadmap 09).

Gate items: same-hash skip, atomic activation delegation, error rollback,
validation-before-parsing (LIMIT_EXCEEDED/INVALID_REQUEST/UNSUPPORTED_FORMAT),
typed error propagation and canonical ID materialization. Real SQLite store
integration tests follow in PR-P2 after PR-A2 merges (roadmap 03 P5 row).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from fakes.fake_store import FakeKnowledgeStore

from verity import ids as verity_ids
from verity.errors import VerityError
from verity.ingestion import IngestionPipeline
from verity.models import DocumentKind, DocumentStatus, IngestMode, IngestRequest

FIXTURES = TESTS_DIR / "fixtures" / "contracts_v1"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store() -> FakeKnowledgeStore:
    return FakeKnowledgeStore()


@pytest.fixture()
def pipeline(store: FakeKnowledgeStore) -> IngestionPipeline:
    return IngestionPipeline(store)


def request(path: str = "specs/payments.md", mode="auto", source_id=None) -> IngestRequest:
    return IngestRequest(source_path=path, mode=mode, source_id=source_id)


def test_ingest_spec_end_to_end(pipeline: IngestionPipeline, store: FakeKnowledgeStore) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    result = run(pipeline.ingest(request(), data))
    assert result.created_new_version is True
    doc = result.document
    assert doc.name == "payments.md"
    assert doc.kind is DocumentKind.SPEC
    assert doc.status is DocumentStatus.READY
    assert doc.content_sha256 == hashlib.sha256(data).hexdigest()
    assert len(store.chunks) == 9
    assert len(store.requirements) == 3
    req = store.requirements[verity_ids.make_requirement_id(doc.source_id, "REQ-001")]
    assert req.local_id == "REQ-001"
    assert [c.local_id for c in req.acceptance_criteria] == ["AC-001"]
    assert req.evidence_id.startswith("ev_")
    assert all(re.fullmatch(r"chk_[0-9a-f]{64}", c.chunk_id) for c in store.chunks.values())


def test_requirement_chunk_carries_canonical_requirement_id(
        pipeline: IngestionPipeline, store: FakeKnowledgeStore) -> None:
    result = run(pipeline.ingest(request(), (FIXTURES / "payments.md").read_bytes()))
    expected = verity_ids.make_requirement_id(result.document.source_id, "REQ-001")
    requirement_chunks = [c for c in store.chunks.values() if c.kind.value == "requirement"]
    refund = next(c for c in requirement_chunks if c.text.startswith("Refund window"))
    assert refund.requirement_id == expected


def test_same_hash_reingest_skips_reindexing(
        pipeline: IngestionPipeline, store: FakeKnowledgeStore) -> None:
    data = (FIXTURES / "architecture.md").read_bytes()
    first = run(pipeline.ingest(request("docs/architecture.md"), data))
    second = run(pipeline.ingest(
        request("docs/architecture.md", source_id=first.document.source_id), data))
    assert second.created_new_version is False
    assert second.document.version_id == first.document.version_id
    assert store.activation_calls == 1  # no reindexing


def test_changed_content_creates_new_version(
        pipeline: IngestionPipeline, store: FakeKnowledgeStore) -> None:
    first = run(pipeline.ingest(request("docs/architecture.md"),
                                (FIXTURES / "architecture.md").read_bytes()))
    second = run(pipeline.ingest(
        request("docs/architecture.md", source_id=first.document.source_id),
        (FIXTURES / "security.txt").read_bytes()))
    assert second.created_new_version is True
    assert second.document.version_id != first.document.version_id


def test_limit_exceeded(store: FakeKnowledgeStore) -> None:
    small = IngestionPipeline(store, max_bytes=10)
    with pytest.raises(VerityError) as exc:
        run(small.ingest(request("docs/a.md"), b"x" * 11))
    assert exc.value.code == "LIMIT_EXCEEDED"


def test_traversal_path_rejected(pipeline: IngestionPipeline) -> None:
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request("docs/../secrets.md"), b"# hi\n"))
    assert exc.value.code == "INVALID_REQUEST"


def test_absolute_path_rejected(pipeline: IngestionPipeline) -> None:
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request("C:/notes/a.md"), b"# hi\n"))
    assert exc.value.code == "INVALID_REQUEST"


def test_unsupported_format(pipeline: IngestionPipeline) -> None:
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request("docs/book.docx"), b"data"))
    assert exc.value.code == "UNSUPPORTED_FORMAT"


def test_invalid_utf8_is_parser_error(pipeline: IngestionPipeline) -> None:
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request("docs/a.txt"), b"\xff\xfe"))
    assert exc.value.code == "PARSER_ERROR"


def test_spec_validation_error_propagates_with_line(pipeline: IngestionPipeline) -> None:
    data = (FIXTURES / "invalid_reference.md").read_bytes()
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request("specs/invalid_reference.md"), data))
    assert exc.value.code == "SPEC_VALIDATION_ERROR"
    assert exc.value.details["line"] == 16


def test_version_unsupported_propagates(pipeline: IngestionPipeline) -> None:
    data = (b'---\nverity_spec: "2.0.0"\nsource_key: a-b\nproject: p\n'
            b'title: T\nspec_version: "1.0"\n---\n\n# Requirements\n'
            b'## REQ-001: A\nText.\n')
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request("specs/t.md"), data))
    assert exc.value.code == "VERSION_UNSUPPORTED"


def test_mode_general_forces_general(
        pipeline: IngestionPipeline, store: FakeKnowledgeStore) -> None:
    result = run(pipeline.ingest(request("specs/payments.md", mode=IngestMode.GENERAL),
                                 (FIXTURES / "payments.md").read_bytes()))
    assert result.document.kind is DocumentKind.GENERAL
    assert store.requirements == {}


def test_mode_spec_requires_markdown(pipeline: IngestionPipeline) -> None:
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request("docs/payments.pdf", mode=IngestMode.SPEC),
                            (FIXTURES / "payments.pdf").read_bytes()))
    assert exc.value.code == "SPEC_VALIDATION_ERROR"


def test_unknown_source_reingest_fails(pipeline: IngestionPipeline) -> None:
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request(source_id="24da624f-7fd0-41ea-a49b-8449cbb179d9"),
                            (FIXTURES / "payments.md").read_bytes()))
    assert exc.value.code == "SOURCE_NOT_FOUND"


def test_store_failure_propagates_and_leaves_state(store: FakeKnowledgeStore) -> None:
    class FailingStore(FakeKnowledgeStore):
        async def activate_ingestion(self, *args, **kwargs):
            self.activation_calls += 1
            raise VerityError("INTERNAL_ERROR", "activation failed; rolled back")

    failing = FailingStore()
    pipeline = IngestionPipeline(failing)
    with pytest.raises(VerityError) as exc:
        run(pipeline.ingest(request("docs/architecture.md"),
                            (FIXTURES / "architecture.md").read_bytes()))
    assert exc.value.code == "INTERNAL_ERROR"
    assert failing.documents == {}  # nothing committed