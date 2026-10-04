"""Retrieval interface tests (contract 16 signatures, P1 skeleton + roadmap 09).

Verifies the frozen cross-module signatures of ``EmbeddingProvider``,
``Reranker`` and ``RetrievalService`` and the shared ``FakeRetrievalService``
sample run shape (RetrievalRun per contract 16, chunk per contract 03/21).
D1 is resolved (issue #2, docs 1.0.2): ``search`` returns ``RetrievalRun``
per both contracts 06 and 16. The concrete ``search`` implementation (P9)
still waits for PR-A3 real store wiring; fixture/fake work continues.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from fakes.fake_retrieval import FakeRetrievalService, sample_retrieval_run
from support import schema_check

from verity.retrieval import EmbeddingProvider, Reranker, RetrievalService

SCHEMA = schema_check.load_schema()


def test_embedding_provider_signatures() -> None:
    assert [p for p in inspect.signature(EmbeddingProvider.embed).parameters] == ["self", "text"]
    assert [p for p in inspect.signature(EmbeddingProvider.embed_batch).parameters] == ["self", "texts"]
    assert "model_id" in EmbeddingProvider.__annotations__


def test_reranker_signature() -> None:
    assert [p for p in inspect.signature(Reranker.score).parameters] == ["self", "query", "chunks"]
    assert "model_id" in Reranker.__annotations__


def test_retrieval_service_search_signature_matches_contract16() -> None:
    params = inspect.signature(RetrievalService.search).parameters
    assert list(params) == ["self", "request"]
    assert params["request"].annotation in ("SearchRequest", "'SearchRequest'")
    assert "RetrievalRun" in str(RetrievalService.search.__annotations__["return"])


def test_sample_retrieval_run_shape() -> None:
    run = sample_retrieval_run()
    assert set(run) == {
        "items", "retrieval_mode", "reranker_used", "completeness", "omissions",
    }
    assert run["retrieval_mode"] in ("hybrid", "lexical_only", "semantic_only")
    assert run["completeness"] in ("complete", "partial", "empty")
    assert isinstance(run["reranker_used"], bool)
    assert isinstance(run["omissions"], list)
    assert run["omissions"] == ["semantic_model_unavailable"]
    item = run["items"][0]
    assert set(item) == {"chunk", "score", "dense_rank", "lexical_rank", "rrf_score", "rerank_score"}
    assert schema_check.validate(item["chunk"], SCHEMA["$defs"]["Chunk"], SCHEMA) == []


def test_fake_retrieval_service_records_requests() -> None:
    import asyncio

    fake = FakeRetrievalService()
    request = {"query": "refund window"}
    run = asyncio.run(fake.search(request))
    assert run == sample_retrieval_run()
    assert fake.requests == [request]