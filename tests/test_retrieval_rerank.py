"""P8 reranker tests (contract 06 acceptance: top-30, model revision,
``reranker_used=false`` truthful fallback).

The reranker is optional (contract 14 ``reranker_enabled``): on success items
order by descending rerank score, then RRF, then ``chunk_id`` with ``score``
as the rerank score; on disable/absence/failure items keep RRF order with
``score`` as the RRF score and ``reranker_used=false``. Fake model only —
nothing here runs or downloads a real model.
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

from fakes.fake_retrieval import FakeReranker, ranked

from verity.retrieval import (
    RERANK_INPUT_CAP,
    RERANKER_UNAVAILABLE,
    FusedCandidate,
    FusedRun,
    rerank,
)


def run(coro):
    return asyncio.run(coro)


CHUNK_A = "chk_" + "a" * 64
CHUNK_B = "chk_" + "b" * 64
CHUNK_C = "chk_" + "c" * 64
QUERY = "refund window"


def fused(*specs) -> FusedRun:
    """Build a FusedRun from (chunk_id, rrf_score) pairs."""
    return FusedRun(items=tuple(
        FusedCandidate(chunk=ranked(chunk_id).chunk, rrf_score=score)
        for chunk_id, score in specs
    ))


def test_rerank_orders_by_score_then_rrf_then_chunk_id() -> None:
    # Rerank scores: A 0.1, B 0.5, C 0.5 -> B/C tie on rerank; B has higher
    # RRF so B first; equal rerank AND RRF would fall back to chunk_id.
    run_data = fused((CHUNK_A, 0.02), (CHUNK_B, 0.01), (CHUNK_C, 0.01))
    result = run(rerank(QUERY, run_data,
                        FakeReranker(scores=(0.1, 0.5, 0.5))))
    assert [item.chunk.chunk_id for item in result.items] == [CHUNK_B, CHUNK_C, CHUNK_A]
    assert result.reranker_used is True


def test_rerank_tie_falls_through_to_chunk_id() -> None:
    run_data = fused((CHUNK_C, 0.01), (CHUNK_A, 0.01))
    result = run(rerank(QUERY, run_data, FakeReranker(scores=(0.5, 0.5))))
    assert [item.chunk.chunk_id for item in result.items] == [CHUNK_A, CHUNK_C]


def test_success_records_rerank_scores_and_model_revision() -> None:
    run_data = fused((CHUNK_A, 0.02), (CHUNK_B, 0.01))
    fake = FakeReranker(scores=(0.9, 0.4))
    result = run(rerank(QUERY, run_data, fake))
    assert result.reranker_used is True
    assert result.reranker_model_id == "fake/bge-reranker-v2-m3@test"
    assert [item.score for item in result.items] == [0.9, 0.4]
    assert [item.rerank_score for item in result.items] == [0.9, 0.4]
    assert result.items[0].rrf_score == 0.02  # provenance preserved


def test_config_disabled_falls_back_without_calling_model() -> None:
    run_data = fused((CHUNK_A, 0.02), (CHUNK_B, 0.01))
    fake = FakeReranker(scores=(0.9, 0.4))
    result = run(rerank(QUERY, run_data, fake, enabled=False))
    assert result.reranker_used is False
    assert result.reranker_model_id is None
    assert fake.calls == []  # deliberately disabled -> model never runs
    assert [item.chunk.chunk_id for item in result.items] == [CHUNK_A, CHUNK_B]
    assert [item.score for item in result.items] == [0.02, 0.01]  # RRF scores
    assert all(item.rerank_score is None for item in result.items)
    assert result.omissions == ()  # config-off is not a capability gap


def test_absent_reranker_falls_back_with_omission() -> None:
    run_data = fused((CHUNK_B, 0.01), (CHUNK_A, 0.02))
    result = run(rerank(QUERY, run_data, None))
    assert result.reranker_used is False
    assert [item.chunk.chunk_id for item in result.items] == [CHUNK_A, CHUNK_B]
    assert result.omissions == (RERANKER_UNAVAILABLE,)


def test_reranker_failure_falls_back_with_omission() -> None:
    run_data = fused((CHUNK_A, 0.02), (CHUNK_B, 0.01))
    result = run(rerank(QUERY, run_data, FakeReranker(fail=True)))
    assert result.reranker_used is False
    assert [item.chunk.chunk_id for item in result.items] == [CHUNK_A, CHUNK_B]
    assert result.omissions == (RERANKER_UNAVAILABLE,)


def test_wrong_length_scores_fall_back_with_omission() -> None:
    run_data = fused((CHUNK_A, 0.02), (CHUNK_B, 0.01))
    result = run(rerank(QUERY, run_data, FakeReranker(wrong_length=True)))
    assert result.reranker_used is False
    assert result.omissions == (RERANKER_UNAVAILABLE,)


def test_non_numeric_scores_fall_back_with_omission() -> None:
    run_data = fused((CHUNK_A, 0.02), (CHUNK_B, 0.01))
    for bad in (("nope", "nope"), (float("nan"), float("nan")),
                (None, None)):
        result = run(rerank(QUERY, run_data, FakeReranker(scores=bad)))
        assert result.reranker_used is False
        assert [item.chunk.chunk_id for item in result.items] == [CHUNK_A, CHUNK_B]
        assert result.omissions == (RERANKER_UNAVAILABLE,)


def test_top_30_cap_limits_reranker_input() -> None:
    run_data = fused(*(
        ("chk_" + f"{i:064x}", 1.0 / (60 + i + 1)) for i in range(35)
    ))
    fake = FakeReranker()
    result = run(rerank(QUERY, run_data, fake))
    assert fake.calls == [(QUERY, RERANK_INPUT_CAP)]  # exact query, top 30
    assert len(result.items) == RERANK_INPUT_CAP


def test_exact_query_passed_to_reranker() -> None:
    run_data = fused((CHUNK_A, 0.02))
    fake = FakeReranker()
    odd_query = "  Refund \"window\" (exact)  "
    run(rerank(odd_query, run_data, fake))
    assert fake.calls[0][0] == odd_query  # unmodified


def test_empty_fused_run_shortcuts_without_model() -> None:
    fake = FakeReranker()
    result = run(rerank(QUERY, FusedRun(items=()), fake))
    assert result.items == ()
    assert result.reranker_used is False
    assert fake.calls == []


def test_branch_omissions_pass_through() -> None:
    run_data = FusedRun(
        items=fused((CHUNK_A, 0.02)).items,
        omissions=("semantic_model_unavailable",),
    )
    ok = run(rerank(QUERY, run_data, FakeReranker(scores=(0.7,))))
    assert ok.omissions == ("semantic_model_unavailable",)
    failed = run(rerank(QUERY, run_data, FakeReranker(fail=True)))
    assert failed.omissions == ("semantic_model_unavailable",
                                RERANKER_UNAVAILABLE)