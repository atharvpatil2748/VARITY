"""P10 corpus contract/integration tests (roadmap 03: three-document query,
malformed/empty/version cases, lexical fallback).

Real end-to-end slice: shared fixture corpus -> ``IngestionPipeline`` ->
``SqliteKnowledgeStore`` -> ``DefaultRetrievalService.search`` ->
``DefaultEvidenceService`` (PR-A3). This is the PR-P4 "clean corpus"
evidence: cross-document identity, multi-document selector, version
supersession, PDF page provenance, offline lexical fallback and resolution
of every returned evidence ID.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from verity.errors import VerityError
from verity.evidence import DefaultEvidenceService
from verity.ids import make_evidence_id
from verity.ingestion import IngestionPipeline
from verity.models import Completeness, IngestRequest, RetrievalMode, SearchRequest
from verity.retrieval import DefaultRetrievalService
from verity.storage import SqliteKnowledgeStore

FIXTURES = TESTS_DIR / "fixtures" / "contracts_v1"

CORPUS = (
    ("specs/payments.md", "payments.md"),
    ("docs/architecture.md", "architecture.md"),
    ("docs/security.txt", "security.txt"),
    ("docs/payments.pdf", "payments.pdf"),
)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path: Path):
    s = SqliteKnowledgeStore(tmp_path / "verity.sqlite3", tmp_path)
    s.open()
    yield s
    s.close()


@pytest.fixture()
def corpus(store: SqliteKnowledgeStore) -> dict:
    pipeline = IngestionPipeline(store)
    documents = {}
    for source_path, fixture in CORPUS:
        result = run(pipeline.ingest(
            IngestRequest(source_path=source_path, mode="auto"),
            (FIXTURES / fixture).read_bytes(),
        ))
        documents[fixture] = result.document
    return documents


def request(**overrides) -> SearchRequest:
    base = dict(query="idempotency", document_ids=None,
                document_kinds=None, chunk_kinds=None, limit=8,
                per_document_limit=None)
    base.update(overrides)
    return SearchRequest(**base)


# ---------------------------------------------------------------------------
# Three-document query and source identity (contract 08)
# ---------------------------------------------------------------------------


def test_three_document_query_returns_cross_source_evidence(
        store: SqliteKnowledgeStore, corpus: dict[str, str]) -> None:
    service = DefaultRetrievalService(store)  # no BGE: lexical-only corpus
    result = run(service.search(request(query="idempotency")))
    assert result.items
    documents = {item.chunk.locator.document_id for item in result.items}
    assert len(documents) >= 3  # payments.md + architecture.md + security.txt
    assert documents <= {d.document_id for d in corpus.values()}
    for item in result.items:
        locator = item.chunk.locator
        assert locator.source_id and locator.source_path
        assert not locator.source_path.startswith("/")
        assert item.rrf_score is not None


def test_multi_document_selector_restricts_scope(
        store: SqliteKnowledgeStore, corpus: dict[str, str]) -> None:
    service = DefaultRetrievalService(store)
    allowed = [corpus["payments.md"].document_id,
               corpus["security.txt"].document_id]
    result = run(service.search(request(query="idempotency",
                                        document_ids=allowed)))
    assert result.items
    assert {item.chunk.locator.document_id for item in result.items} <= set(allowed)


def test_end_to_end_search_evidence_resolution(
        store: SqliteKnowledgeStore, corpus: dict[str, str]) -> None:
    service = DefaultRetrievalService(store)
    evidence_service = DefaultEvidenceService(store)
    req = request(query="idempotency")
    run_result = run(service.search(req))
    result = run(evidence_service.from_retrieval(req, run_result))
    assert result.total_returned == len(result.items)
    for item in result.items:
        lookup = run(evidence_service.get(item.evidence_id))
        assert lookup.evidence.quote == item.quote  # canonical quote
        assert item.citation.label  # canonical label present


# ---------------------------------------------------------------------------
# Version cases (D3 semantics)
# ---------------------------------------------------------------------------


def test_version_supersession_and_historical_resolution(
        store: SqliteKnowledgeStore, corpus: dict[str, str]) -> None:
    pipeline = IngestionPipeline(store)
    service = DefaultRetrievalService(store)
    before = run(service.search(request(query="idempotency")))
    v1_chunk = next(item.chunk for item in before.items
                    if item.chunk.locator.document_id
                    == corpus["security.txt"].document_id)

    result = run(pipeline.ingest(
        IngestRequest(source_path="docs/security.txt", mode="auto",
                      source_id=corpus["security.txt"].source_id),
        (FIXTURES / "security.txt").read_bytes()
        + b"\n\nAudit webhook signatures expire after 24 hours.\n",
    ))
    assert result.created_new_version is True

    after = run(service.search(request(query="idempotency")))
    assert v1_chunk.chunk_id not in [item.chunk.chunk_id for item in after.items]
    evidence_service = DefaultEvidenceService(store)
    lookup = run(evidence_service.get(
        make_evidence_id(UUID(v1_chunk.locator.version_id), v1_chunk.chunk_id)))
    assert lookup.evidence.quote == v1_chunk.text  # historical quote intact


# ---------------------------------------------------------------------------
# Malformed / empty / fallback cases
# ---------------------------------------------------------------------------


def test_empty_search_is_not_an_error(
        store: SqliteKnowledgeStore, corpus: dict[str, str]) -> None:
    service = DefaultRetrievalService(store)
    result = run(service.search(request(query="zzzunfindable")))
    assert result.items == []
    assert result.completeness is Completeness.EMPTY


def test_malformed_query_and_scope_rejected(
        store: SqliteKnowledgeStore, corpus: dict[str, str]) -> None:
    service = DefaultRetrievalService(store)
    with pytest.raises(VerityError) as exc:
        run(service.search(request(query="   ")))
    assert exc.value.code == "INVALID_REQUEST"
    with pytest.raises(VerityError) as exc:
        run(service.search(
            request(document_ids=["24da624f-7fd0-41ea-a49b-8449cbb179d9"])))
    assert exc.value.code == "DOCUMENT_NOT_FOUND"


def test_lexical_fallback_without_embedding_model(
        store: SqliteKnowledgeStore, corpus: dict[str, str]) -> None:
    # Offline deployment with default config (reranker_enabled=true) but
    # neither model provisioned: every missing capability is disclosed.
    service = DefaultRetrievalService(store, provider=None)
    result = run(service.search(request(query="refund window")))
    assert result.retrieval_mode is RetrievalMode.LEXICAL_ONLY
    assert result.completeness is Completeness.PARTIAL
    assert result.omissions == ["semantic_model_unavailable",
                                "reranker_unavailable"]
    assert result.reranker_used is False
    assert result.items  # lexical results still served (offline story)


def test_pdf_results_carry_page_provenance(
        store: SqliteKnowledgeStore, corpus: dict[str, str]) -> None:
    service = DefaultRetrievalService(store)
    result = run(service.search(request(query="30 days")))
    assert any(item.chunk.locator.page == 2 for item in result.items)
    for item in result.items:
        if item.chunk.locator.page is not None:
            assert item.chunk.locator.page >= 1