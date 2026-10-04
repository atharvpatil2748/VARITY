"""P9 multi-document RetrievalService tests (contract 06/08 acceptance:
global rank, source IDs, per-document cap, empty/one-branch).

``DefaultRetrievalService.search`` returns the frozen ``RetrievalRun``
(D1 resolved, change log 1.0.2) over fake branches; real-store corpus
integration is the P10 suite. Covers query normalization (trim+NFC),
DOCUMENT_NOT_FOUND scope checks, mode/completeness/omissions truthfulness
and RETRIEVAL_UNAVAILABLE when both branches fail.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from fakes.fake_retrieval import (
    FakeCandidateStore,
    FakeEmbeddingProvider,
    FakeReranker,
    ranked,
)

from verity.errors import VerityError
from verity.models import Completeness, RetrievalMode, SearchRequest
from verity.retrieval import DefaultRetrievalService, normalize_query

DOC_A = "ebc2352e-ff9c-4167-b11a-1e30d550411d"
DOC_B = "129dcd06-1ba1-4f0c-bf7e-c678f905b624"
UNKNOWN_DOC = "24da624f-7fd0-41ea-a49b-8449cbb179d9"
CHUNK_A = "chk_" + "a" * 64
CHUNK_B = "chk_" + "b" * 64
CHUNK_C = "chk_" + "c" * 64


def run(coro):
    return asyncio.run(coro)


def request(**overrides) -> SearchRequest:
    base = dict(query="refund window", document_ids=None,
                document_kinds=None, chunk_kinds=None, limit=8,
                per_document_limit=None)
    base.update(overrides)
    return SearchRequest(**base)


def build(lexical=None, vector=None, provider="default", reranker=None,
          rerank_enabled=None):
    """Minimal deployment by default: no reranker -> deliberate config-off.

    When a reranker is supplied it is enabled unless overridden.
    """
    store = FakeCandidateStore(lexical=lexical, vector=vector)
    store.known_documents = {DOC_A, DOC_B}
    if provider == "default":
        provider = FakeEmbeddingProvider()
    if rerank_enabled is None:
        rerank_enabled = reranker is not None
    service = DefaultRetrievalService(
        store, provider, reranker, rerank_enabled=rerank_enabled,
    )
    return store, service


def test_hybrid_mode_merges_branches_with_rank_provenance() -> None:
    store, service = build(
        lexical=[ranked(CHUNK_A, rank=1), ranked(CHUNK_B, rank=2)],
        vector=[ranked(CHUNK_C, rank=1)],
    )
    result = run(service.search(request()))
    assert result.retrieval_mode is RetrievalMode.HYBRID
    assert result.completeness is Completeness.COMPLETE
    assert result.omissions == []
    assert result.reranker_used is False
    chunk_ids = [item.chunk.chunk_id for item in result.items]
    assert set(chunk_ids) == {CHUNK_A, CHUNK_B, CHUNK_C}
    for item in result.items:
        assert item.rrf_score is not None  # contract 03: required non-null
        # source identity survives aggregation (contract 08)
        assert item.chunk.locator.document_id in (DOC_A, DOC_B)
        assert item.chunk.locator.source_id
        assert item.chunk.locator.source_path == "specs/payments.md"
    # Global ranking: fused by RRF score descending.
    scores = [item.score for item in result.items]
    assert scores == sorted(scores, reverse=True)


def test_per_document_cap_after_global_ranking() -> None:
    store, service = build(lexical=[
        ranked(CHUNK_A, rank=1, document_id=DOC_A),
        ranked(CHUNK_B, rank=2, document_id=DOC_A),
        ranked(CHUNK_C, rank=3, document_id=DOC_B),
    ])
    result = run(service.search(request(per_document_limit=1)))
    assert [item.chunk.chunk_id for item in result.items] == [CHUNK_A, CHUNK_C]
    assert [item.chunk.locator.document_id for item in result.items] == [DOC_A, DOC_B]


def test_final_limit_applied() -> None:
    store, service = build(lexical=[
        ranked(CHUNK_A, rank=1), ranked(CHUNK_B, rank=2), ranked(CHUNK_C, rank=3)])
    result = run(service.search(request(limit=2)))
    assert len(result.items) == 2


def test_empty_search_is_success_not_error() -> None:
    store, service = build(lexical=[], vector=[])
    result = run(service.search(request()))
    assert result.items == []
    assert result.completeness is Completeness.EMPTY
    assert result.retrieval_mode is RetrievalMode.HYBRID
    assert result.omissions == []


def test_one_branch_missing_model_degrades_to_lexical_only() -> None:
    store, service = build(
        lexical=[ranked(CHUNK_A, rank=1)], provider=None)
    result = run(service.search(request()))
    assert result.retrieval_mode is RetrievalMode.LEXICAL_ONLY
    assert result.completeness is Completeness.PARTIAL
    assert result.omissions == ["semantic_model_unavailable"]
    assert [item.chunk.chunk_id for item in result.items] == [CHUNK_A]


def test_lexical_failure_degrades_to_semantic_only() -> None:
    store, service = build(
        lexical=[ranked(CHUNK_A)], vector=[ranked(CHUNK_B, rank=1)])
    store.fail_lexical = True
    result = run(service.search(request()))
    assert result.retrieval_mode is RetrievalMode.SEMANTIC_ONLY
    assert result.completeness is Completeness.PARTIAL
    assert result.omissions == ["lexical_unavailable"]
    assert [item.chunk.chunk_id for item in result.items] == [CHUNK_B]


def test_both_branches_failed_is_retrieval_unavailable() -> None:
    store, service = build(lexical=[ranked(CHUNK_A)], provider=None)
    store.fail_lexical = True
    with pytest.raises(VerityError) as exc:
        run(service.search(request()))
    assert exc.value.code == "RETRIEVAL_UNAVAILABLE"


def test_query_trim_nfc_and_validation() -> None:
    # NFD "café" + padding -> NFC "café" reaches BOTH branches normalized
    # (contract 06: the retrieval query is trimmed and NFC-normalized).
    nfd = "  cafe\u0301 window  "
    store, service = build(lexical=[ranked(CHUNK_A, rank=1)])
    run(service.search(request(query=nfd)))
    assert normalize_query(nfd) == "caf\u00e9 window"
    forwarded, _ = store.lexical_requests[0]
    assert forwarded.query == normalize_query(nfd)
    _, dense_request, _, _ = store.vector_requests[0]
    assert dense_request.query == normalize_query(nfd)
    # empty after trim and short queries are INVALID_REQUEST
    for bad in ("   ", " a "):
        with pytest.raises(VerityError) as exc:
            run(service.search(request(query=bad)))
        assert exc.value.code == "INVALID_REQUEST"


def test_reranker_receives_normalized_exact_query() -> None:
    store, service = build(
        lexical=[ranked(CHUNK_A, rank=1)],
        reranker=FakeReranker(scores=(0.9,)),
    )
    result = run(service.search(request(query="  refund window  ")))
    assert result.reranker_used is True
    assert service._reranker.calls[0][0] == "refund window"  # trimmed
    assert result.items[0].score == 0.9  # rerank score is the item score
    assert result.items[0].rerank_score == 0.9


def test_rerank_disabled_records_false() -> None:
    store, service = build(
        lexical=[ranked(CHUNK_A, rank=1)],
        reranker=FakeReranker(scores=(0.9,)),
        rerank_enabled=False,
    )
    result = run(service.search(request()))
    assert result.reranker_used is False
    assert result.items[0].score == result.items[0].rrf_score


def test_unknown_document_id_is_document_not_found() -> None:
    store, service = build(lexical=[ranked(CHUNK_A, rank=1)])
    with pytest.raises(VerityError) as exc:
        run(service.search(request(document_ids=[UNKNOWN_DOC])))
    assert exc.value.code == "DOCUMENT_NOT_FOUND"


def test_known_document_ids_pass_scope_check() -> None:
    store, service = build(lexical=[ranked(CHUNK_A, rank=1)])
    result = run(service.search(request(document_ids=[DOC_A, DOC_B])))
    assert result.items  # scope check passed, search ran