"""P6 candidate-branch tests (contract 06 acceptance: active filters, branch
omission, no serving-time download).

``LexicalBranch``/``DenseBranch`` run against fakes (roadmap 03 P6: "fake
store/model ... no pull for fake work"); real-store integration lands with
PR-P3 after PR-A3. Branch streams are ``BranchResult`` records with ranks
normalized from 1 and truthful omission labels on failure.
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

from fakes.fake_retrieval import FakeCandidateStore, FakeEmbeddingProvider, ranked

from verity.models import DocumentKind, SearchRequest
from verity.retrieval import (
    LEXICAL_UNAVAILABLE,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_UNAVAILABLE,
    DenseBranch,
    LexicalBranch,
)


def run(coro):
    return asyncio.run(coro)


def request(**overrides) -> SearchRequest:
    base = dict(query="refund window", document_ids=None,
                document_kinds=None, chunk_kinds=None, limit=8,
                per_document_limit=None)
    base.update(overrides)
    return SearchRequest(**base)


CHUNK_A = "chk_" + "a" * 64
CHUNK_B = "chk_" + "b" * 64
CHUNK_C = "chk_" + "c" * 64


# ---------------------------------------------------------------------------
# Lexical branch
# ---------------------------------------------------------------------------


def test_lexical_branch_returns_ranked_stream() -> None:
    store = FakeCandidateStore(
        lexical=[ranked(CHUNK_A, rank=3), ranked(CHUNK_B, rank=7)])
    result = run(LexicalBranch(store).candidates(request()))
    assert [r.chunk.chunk_id for r in result.items] == [CHUNK_A, CHUNK_B]
    assert [r.rank for r in result.items] == [1, 2]  # normalized from 1
    assert result.omissions == ()


def test_lexical_branch_budget_caps_stream() -> None:
    store = FakeCandidateStore(
        lexical=[ranked(CHUNK_A), ranked(CHUNK_B), ranked(CHUNK_C)])
    result = run(LexicalBranch(store, budget=2).candidates(request()))
    assert len(result.items) == 2
    assert store.lexical_requests[0][1] == 2  # store asked within budget


def test_lexical_branch_forwards_filters_for_active_scope() -> None:
    store = FakeCandidateStore(lexical=[ranked(CHUNK_A)])
    req = request(
        document_ids=["ebc2352e-ff9c-4167-b11a-1e30d550411d"],
        document_kinds=[DocumentKind.SPEC],
        per_document_limit=2,
    )
    run(LexicalBranch(store).candidates(req))
    forwarded, limit = store.lexical_requests[0]
    # Filters must reach the store so they apply BEFORE branch top-k
    # (contract 08) together with the store's active-version filter.
    assert forwarded is req
    assert forwarded.document_ids == req.document_ids
    assert forwarded.document_kinds == req.document_kinds
    assert forwarded.per_document_limit == 2
    assert limit == 50


def test_lexical_branch_failure_yields_omission() -> None:
    store = FakeCandidateStore(lexical=[ranked(CHUNK_A)])
    store.fail_lexical = True
    result = run(LexicalBranch(store).candidates(request()))
    assert result.items == ()
    assert result.omissions == (LEXICAL_UNAVAILABLE,)


# ---------------------------------------------------------------------------
# Dense branch
# ---------------------------------------------------------------------------


def test_dense_branch_embeds_query_and_queries_vector() -> None:
    store = FakeCandidateStore(vector=[ranked(CHUNK_B, rank=5)])
    provider = FakeEmbeddingProvider(vector=(0.6, 0.8))
    result = run(DenseBranch(store, provider).candidates(request()))
    assert provider.embed_calls == ["refund window"]  # query embedded once
    vector, forwarded, model_id, limit = store.vector_requests[0]
    assert vector == (0.6, 0.8)
    assert forwarded.document_ids is None  # filters forwarded unchanged
    assert model_id == "fake/bge-m3@test"
    assert limit == 50
    assert [r.chunk.chunk_id for r in result.items] == [CHUNK_B]
    assert [r.rank for r in result.items] == [1]
    assert result.omissions == ()


def test_dense_branch_without_provider_yields_omission() -> None:
    store = FakeCandidateStore(vector=[ranked(CHUNK_B)])
    result = run(DenseBranch(store, None).candidates(request()))
    assert result.items == ()
    assert result.omissions == (SEMANTIC_MODEL_UNAVAILABLE,)
    assert store.vector_requests == []  # nothing scanned without a model


def test_dense_branch_provider_failure_yields_omission() -> None:
    store = FakeCandidateStore(vector=[ranked(CHUNK_B)])
    provider = FakeEmbeddingProvider(fail=True)
    result = run(DenseBranch(store, provider).candidates(request()))
    assert result.items == ()
    assert result.omissions == (SEMANTIC_MODEL_UNAVAILABLE,)
    assert store.vector_requests == []


def test_dense_branch_store_failure_yields_omission() -> None:
    store = FakeCandidateStore(vector=[ranked(CHUNK_B)])
    store.fail_vector = True
    provider = FakeEmbeddingProvider()
    result = run(DenseBranch(store, provider).candidates(request()))
    assert result.items == ()
    assert result.omissions == (SEMANTIC_UNAVAILABLE,)


# ---------------------------------------------------------------------------
# Contract guards
# ---------------------------------------------------------------------------


def test_budget_bounds_enforced() -> None:
    with pytest.raises(ValueError):
        LexicalBranch(FakeCandidateStore(), budget=0)
    with pytest.raises(ValueError):
        DenseBranch(FakeCandidateStore(), FakeEmbeddingProvider(), budget=51)


def test_no_serving_time_download() -> None:
    """Branch modules must never import model runtimes or downloaders."""
    forbidden = ("torch", "transformers", "huggingface", "requests",
                 "urllib", "httpx", "sentence_transformers")
    for name in ("branches.py", "lexical.py", "dense.py", "interfaces.py"):
        source = (REPO_ROOT / "verity" / "retrieval" / name).read_text("utf-8")
        for module in forbidden:
            assert f"import {module}" not in source, f"{name} imports {module}"
    # The provider surface is exactly embed/embed_batch/model_id (contract 16).
    provider = FakeEmbeddingProvider()
    assert not hasattr(provider, "load") and not hasattr(provider, "download")