"""Local BGE-M3 dense retrieval with bounded in-process vector scan.

Contract: Docs/contracts/06_VERITY_RETRIEVAL_CONTRACT.md. Owner Piyush.

Vectors are normalized at embed time; cosine scan runs in-process for the
bounded demo corpus with a measured size ceiling. When the model is
unavailable the service reports ``retrieval_mode: lexical_only`` instead
of silently degrading.
"""

from __future__ import annotations

from typing import Any


def dense_search(query: str, *, limit: int, filters: dict[str, Any]) -> list[str]:
    """Return ``(chunk_id, cosine_rank)`` candidates. Skeleton for Phase 11."""
    raise NotImplementedError("dense search: scheduled Phase 11, contract 06")