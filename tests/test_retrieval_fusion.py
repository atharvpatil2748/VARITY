"""P7 RRF fusion tests (contract 06 acceptance: ``1/(60+rank)`` formula,
tie-break by ascending chunk_id, 30-candidate cap, no cross-version merge).

Fusion runs over ``BranchResult`` streams from P6 branches (fakes; roadmap 03:
"PARALLEL AFTER CONTRACTS ... no pull required"). Output is the deduplicated
``FusedRun`` that P8 reranks and P9 materializes into ``RetrievalRun``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from fakes.fake_retrieval import ranked

from verity.retrieval import BranchResult
from verity.retrieval.fusion import FUSED_CAP, RRF_K, fuse

CHUNK_A = "chk_" + "a" * 64
CHUNK_B = "chk_" + "b" * 64
CHUNK_C = "chk_" + "c" * 64


def test_rrf_formula_single_branch() -> None:
    fused = fuse(BranchResult(items=(ranked(CHUNK_A, rank=1),)), BranchResult())
    assert len(fused.items) == 1
    assert fused.items[0].rrf_score == pytest.approx(1.0 / (RRF_K + 1))


def test_rrf_formula_sums_both_branches() -> None:
    fused = fuse(
        BranchResult(items=(ranked(CHUNK_A, rank=2),)),
        BranchResult(items=(ranked(CHUNK_A, rank=4),)),
    )
    assert fused.items[0].rrf_score == pytest.approx(
        1.0 / (RRF_K + 2) + 1.0 / (RRF_K + 4))


def test_dedupe_by_chunk_id_preserves_rank_provenance() -> None:
    fused = fuse(
        BranchResult(items=(ranked(CHUNK_A, rank=2), ranked(CHUNK_B, rank=1))),
        BranchResult(items=(ranked(CHUNK_A, rank=4),)),
    )
    by_id = {item.chunk.chunk_id: item for item in fused.items}
    assert set(by_id) == {CHUNK_A, CHUNK_B}  # deduplicated by chunk_id
    assert by_id[CHUNK_A].lexical_rank == 2
    assert by_id[CHUNK_A].dense_rank == 4
    assert by_id[CHUNK_B].lexical_rank == 1
    assert by_id[CHUNK_B].dense_rank is None


def test_tie_break_by_ascending_chunk_id() -> None:
    # Equal single-branch scores (same rank) -> order purely by chunk_id.
    fused = fuse(
        BranchResult(items=(ranked(CHUNK_B, rank=1), ranked(CHUNK_A, rank=1))),
        BranchResult(),
    )
    assert [item.chunk.chunk_id for item in fused.items] == [CHUNK_A, CHUNK_B]


def test_ordering_is_descending_rrf_score() -> None:
    fused = fuse(
        BranchResult(items=(ranked(CHUNK_A, rank=10),)),
        BranchResult(items=(ranked(CHUNK_B, rank=1), ranked(CHUNK_A, rank=1))),
    )
    # CHUNK_A appears in both branches and outranks the lexical-only chunk.
    assert fused.items[0].chunk.chunk_id == CHUNK_A
    assert fused.items[1].chunk.chunk_id == CHUNK_B


def test_fused_cap_30_default_and_override() -> None:
    stream = tuple(ranked("chk_" + f"{i:064x}", rank=i + 1) for i in range(40))
    fused = fuse(BranchResult(items=stream), BranchResult())
    assert len(fused.items) == FUSED_CAP == 30
    assert fused.items[0].chunk.chunk_id == "chk_" + f"{0:064x}"  # rank 1 wins
    small = fuse(BranchResult(items=stream), BranchResult(), cap=5)
    assert len(small.items) == 5


def test_no_cross_version_merge() -> None:
    # Same normalized text, different versions -> different chunk_ids
    # (contract 03); fusion must keep both candidates distinct.
    v1_chunk = ranked(CHUNK_A, rank=1)
    v2_chunk = ranked(CHUNK_B, rank=1)
    assert v1_chunk.chunk.text == v2_chunk.chunk.text
    fused = fuse(BranchResult(items=(v1_chunk,)), BranchResult(items=(v2_chunk,)))
    assert [item.chunk.chunk_id for item in fused.items] == [CHUNK_A, CHUNK_B]


def test_omissions_pass_through_deduped() -> None:
    fused = fuse(
        BranchResult(items=(), omissions=("lexical_unavailable",)),
        BranchResult(items=(), omissions=("semantic_model_unavailable",
                                          "semantic_model_unavailable")),
    )
    assert fused.omissions == ("lexical_unavailable", "semantic_model_unavailable")


def test_empty_branches_yield_empty_run() -> None:
    fused = fuse(BranchResult(items=()), BranchResult(items=()))
    assert fused.items == ()
    assert fused.omissions == ()


def test_cap_must_be_positive() -> None:
    with pytest.raises(ValueError):
        fuse(BranchResult(items=()), BranchResult(items=()), cap=0)