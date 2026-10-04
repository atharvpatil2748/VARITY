"""Optional local cross-encoder reranker.

Contract: Docs/contracts/06_VERITY_RETRIEVAL_CONTRACT.md. Owner Piyush.

Reranks the top fused units (default 30). On absence or failure the
caller keeps RRF order and reports ``reranker_used: false``; failures
never silently change ranking semantics.
"""

from __future__ import annotations

from typing import Sequence


def rerank(query: str, unit_ids: Sequence[str]) -> list[tuple[str, float]]:
    """Return ``(unit_id, rerank_score)`` pairs. Skeleton for Phase 11."""
    raise NotImplementedError("rerank: scheduled Phase 11, contract 06")