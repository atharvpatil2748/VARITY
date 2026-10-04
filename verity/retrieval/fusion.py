"""RRF fusion (contract 06; P7, owner Piyush).

Fuses the two ranked branch streams into deduplicated candidates:

* ``score(u) = sum(1/(60 + rank_i(u)))`` over the branches that returned
  ``u`` (frozen RRF constant 60, contract 06).
* Deduplicate strictly by ``chunk_id`` — chunk IDs are version-specific
  (contract 03), so equal text from different document versions is **never**
  merged ("no cross-version merge").
* Ties break by ascending ``chunk_id``; at most ``FUSED_CAP`` (30) fused
  candidates pass on to the reranker (contract 06 budget).
* Branch ranks are preserved as ``lexical_rank``/``dense_rank`` provenance
  for ``RetrievalResult`` (contract 03) and branch omission labels pass
  through for the final ``RetrievalRun.omissions``.

Internal record types only — not wire objects; P8 attaches rerank scores and
P9 materializes canonical ``RetrievalResult``/``RetrievalRun``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Chunk
from .branches import BranchResult

#: Frozen RRF constant (contract 06).
RRF_K = 60

#: At most 30 fused candidates reach the reranker (contract 06).
FUSED_CAP = 30


@dataclass(frozen=True)
class FusedCandidate:
    """One deduplicated candidate with RRF score and branch rank provenance."""

    chunk: Chunk
    rrf_score: float
    lexical_rank: int | None = None
    dense_rank: int | None = None


@dataclass(frozen=True)
class FusedRun:
    """Fused candidate list (best first) plus carried branch omissions."""

    items: tuple[FusedCandidate, ...]
    omissions: tuple[str, ...] = ()


def _best_ranks(stream: tuple) -> dict[str, tuple[Chunk, int]]:
    best: dict[str, tuple[Chunk, int]] = {}
    for ranked in stream:
        chunk_id = ranked.chunk.chunk_id
        if chunk_id not in best or ranked.rank < best[chunk_id][1]:
            best[chunk_id] = (ranked.chunk, ranked.rank)
    return best


def fuse(lexical: BranchResult, dense: BranchResult,
         cap: int = FUSED_CAP) -> FusedRun:
    """RRF-fuse two branch results into at most ``cap`` candidates."""
    if cap < 1:
        raise ValueError("cap must be >= 1")
    lexical_best = _best_ranks(lexical.items)
    dense_best = _best_ranks(dense.items)

    fused: list[FusedCandidate] = []
    for chunk_id in set(lexical_best) | set(dense_best):
        score = 0.0
        lexical_rank = dense_rank = None
        chunk = None
        if chunk_id in lexical_best:
            chunk, lexical_rank = lexical_best[chunk_id]
            score += 1.0 / (RRF_K + lexical_rank)
        if chunk_id in dense_best:
            chunk, dense_rank = dense_best[chunk_id]
            score += 1.0 / (RRF_K + dense_rank)
        fused.append(FusedCandidate(
            chunk=chunk, rrf_score=score,
            lexical_rank=lexical_rank, dense_rank=dense_rank,
        ))

    fused.sort(key=lambda item: (-item.rrf_score, item.chunk.chunk_id))
    omissions: list[str] = []
    for label in tuple(lexical.omissions) + tuple(dense.omissions):
        if label not in omissions:
            omissions.append(label)
    return FusedRun(items=tuple(fused[:cap]), omissions=tuple(omissions))