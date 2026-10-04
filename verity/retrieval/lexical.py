"""Lexical candidate branch (contract 06; P6, owner Piyush).

Internal strategy behind ``RetrievalService.search``: pulls up to ``budget``
lexical candidates (default 50) from ``KnowledgeStore.lexical_candidates``
with the request's filters applied **before** branch top-k (contract 08 —
one document can never hide candidates from excluded documents; the store's
active-version filter applies at the same time).

A failing branch degrades with the ``lexical_unavailable`` omission and an
empty stream — never an error and never fabricated results. Nothing here
loads or downloads models.
"""

from __future__ import annotations

from typing import Any

from ..models import SearchRequest
from .branches import (
    BRANCH_CANDIDATE_BUDGET,
    LEXICAL_UNAVAILABLE,
    BranchResult,
    normalize,
)


class LexicalBranch:
    """FTS5 candidate stream over the store's lexical reader (contract 06)."""

    def __init__(self, store: Any, budget: int = BRANCH_CANDIDATE_BUDGET) -> None:
        if not 1 <= budget <= BRANCH_CANDIDATE_BUDGET:
            raise ValueError(
                f"budget must be 1..{BRANCH_CANDIDATE_BUDGET} (contract 06)"
            )
        self._store = store
        self._budget = budget

    async def candidates(self, request: SearchRequest) -> BranchResult:
        try:
            stream = await self._store.lexical_candidates(request, self._budget)
        except Exception:
            # Contract 06: a failed branch degrades with an omission; the
            # caller (P9) turns two failed branches into RETRIEVAL_UNAVAILABLE.
            return BranchResult(items=(), omissions=(LEXICAL_UNAVAILABLE,))
        return BranchResult(items=normalize(stream, self._budget))