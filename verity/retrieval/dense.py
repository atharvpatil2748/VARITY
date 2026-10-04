"""Semantic candidate branch (contract 06; P6, owner Piyush).

Internal strategy behind ``RetrievalService.search``: embeds the query with
the injected ``EmbeddingProvider`` and pulls up to ``budget`` candidates
(default 50) from ``KnowledgeStore.vector_candidates`` with the request's
filters applied before branch top-k.

**No serving-time download (contract 06/14):** the branch never imports a
model runtime, never loads or downloads weights. The provider is a
pre-provisioned, config-pinned object (BGE-M3 offline); if it is absent or
fails, the branch degrades with the ``semantic_model_unavailable`` omission
and the run continues lexical-only (contract 06 degradation rules).
"""

from __future__ import annotations

from typing import Any

from ..models import SearchRequest
from .branches import (
    BRANCH_CANDIDATE_BUDGET,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_UNAVAILABLE,
    BranchResult,
    normalize,
)


class DenseBranch:
    """Embedding candidate stream over the store's vector reader (contract 06)."""

    def __init__(self, store: Any, provider: Any | None,
                 budget: int = BRANCH_CANDIDATE_BUDGET) -> None:
        if not 1 <= budget <= BRANCH_CANDIDATE_BUDGET:
            raise ValueError(
                f"budget must be 1..{BRANCH_CANDIDATE_BUDGET} (contract 06)"
            )
        self._store = store
        self._provider = provider
        self._budget = budget

    async def candidates(self, request: SearchRequest) -> BranchResult:
        if self._provider is None:
            return BranchResult(items=(), omissions=(SEMANTIC_MODEL_UNAVAILABLE,))
        try:
            vector = await self._provider.embed(request.query)
        except Exception:
            # Model unavailable/failed at serving: truthful omission, never a
            # silent download attempt and never fabricated embeddings.
            return BranchResult(items=(), omissions=(SEMANTIC_MODEL_UNAVAILABLE,))
        try:
            stream = await self._store.vector_candidates(
                vector, request, self._provider.model_id, self._budget
            )
        except Exception:
            return BranchResult(items=(), omissions=(SEMANTIC_UNAVAILABLE,))
        return BranchResult(items=normalize(stream, self._budget))