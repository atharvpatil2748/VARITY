"""Reciprocal-rank fusion with deterministic ties.

Contract: Docs/contracts/06_VERITY_RETRIEVAL_CONTRACT.md. Owner Piyush.

``score(u) = sum(1 / (60 + rank_i(u)))`` across the dense and lexical
lists; ties break by ``unit_id`` ascending. Deduplicate on ``unit_id``,
never on text alone.
"""

from __future__ import annotations

from collections.abc import Sequence

RRF_K = 60


def fuse_rrf(ranked_lists: Sequence[Sequence[str]]) -> list[tuple[str, float]]:
    """Fuse ranked ID lists into ``(unit_id, rrf_score)`` ordered pairs.

    Deterministic: equal scores order by ``unit_id``.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, unit_id in enumerate(ranked, start=1):
            scores[unit_id] = scores.get(unit_id, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))