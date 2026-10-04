"""Optional reranker stage (contract 06; P8, owner Piyush).

Takes the fused top candidates from P7 and either reranks them or falls back
to truthful RRF ordering (contract 06):

* The reranker receives the **exact query** and at most the **top 30** fused
  candidates (frozen budget). On success items are ordered by descending
  rerank score, then descending RRF score, then ascending ``chunk_id`` and
  ``score`` becomes the rerank score.
* If the reranker is disabled by config (``reranker_enabled=false``, contract
  14), absent, or fails (including a wrong-length score vector), items keep
  RRF order, ``score`` stays the RRF score, ``rerank_score`` is ``null`` and
  ``reranker_used=false`` is recorded. A missing/failed reranker adds the
  ``reranker_unavailable`` omission; a deliberate config-off fallback adds
  none — ``reranker_used`` is the truthful record either way.

The reranker is injected behind the contract-16 ``Reranker`` protocol
(config-pinned model revision; no serving-time download). Internal record
types only; P9 materializes canonical ``RetrievalResult``/``RetrievalRun``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import Chunk
from .fusion import FusedCandidate, FusedRun

#: Contract 06: the reranker receives at most the top 30 fused candidates.
RERANK_INPUT_CAP = 30

#: Omission label: reranker enabled but absent or failed.
RERANKER_UNAVAILABLE = "reranker_unavailable"


@dataclass(frozen=True)
class ScoredCandidate:
    """One final candidate: ``score`` is rerank score if used, else RRF."""

    chunk: Chunk
    score: float
    rrf_score: float
    rerank_score: float | None = None
    lexical_rank: int | None = None
    dense_rank: int | None = None


@dataclass(frozen=True)
class RerankedRun:
    """Reranked (or truthful RRF-ordered) candidates for P9."""

    items: tuple[ScoredCandidate, ...]
    reranker_used: bool
    reranker_model_id: str | None = None
    omissions: tuple[str, ...] = ()


def _rrf_fallback(fused: FusedRun, candidates: tuple[FusedCandidate, ...],
                  omission: str | None) -> RerankedRun:
    ordered = sorted(
        candidates, key=lambda item: (-item.rrf_score, item.chunk.chunk_id)
    )
    items = tuple(
        ScoredCandidate(
            chunk=item.chunk, score=item.rrf_score, rrf_score=item.rrf_score,
            rerank_score=None, lexical_rank=item.lexical_rank,
            dense_rank=item.dense_rank,
        )
        for item in ordered
    )
    omissions = tuple(fused.omissions)
    if omission is not None and omission not in omissions:
        omissions = omissions + (omission,)
    return RerankedRun(items=items, reranker_used=False,
                       reranker_model_id=None, omissions=omissions)


async def rerank(query: str, fused: FusedRun, reranker: Any | None = None,
                 enabled: bool = True) -> RerankedRun:
    """Rerank the fused top candidates or fall back to RRF order (contract 06)."""
    candidates = fused.items[:RERANK_INPUT_CAP]
    if not candidates:
        return _rrf_fallback(fused, (), None)
    if not enabled:
        # Deliberate config-off: reranker_used=false is the record; no omission.
        return _rrf_fallback(fused, candidates, None)
    if reranker is None:
        return _rrf_fallback(fused, candidates, RERANKER_UNAVAILABLE)
    try:
        scores = await reranker.score(
            query, tuple(item.chunk for item in candidates))
        if len(scores) != len(candidates):
            return _rrf_fallback(fused, candidates, RERANKER_UNAVAILABLE)
        numeric = tuple(float(score) for score in scores)
        if not all(score == score and abs(score) != float("inf") for score in numeric):
            return _rrf_fallback(fused, candidates, RERANKER_UNAVAILABLE)
    except Exception:
        return _rrf_fallback(fused, candidates, RERANKER_UNAVAILABLE)

    items = [
        ScoredCandidate(
            chunk=item.chunk, score=score, rrf_score=item.rrf_score,
            rerank_score=score, lexical_rank=item.lexical_rank,
            dense_rank=item.dense_rank,
        )
        for item, score in zip(candidates, numeric)
    ]
    items.sort(key=lambda item: (-item.score, -item.rrf_score,
                                 item.chunk.chunk_id))
    return RerankedRun(
        items=tuple(items),
        reranker_used=True,
        reranker_model_id=getattr(reranker, "model_id", None),
        omissions=tuple(fused.omissions),
    )