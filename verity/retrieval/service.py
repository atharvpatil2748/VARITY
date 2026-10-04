"""Multi-document ``RetrievalService.search`` (contract 06; P9, owner Piyush).

The one public knowledge-search operation (D1 resolved, change log 1.0.2):
``async def search(self, request: SearchRequest) -> RetrievalRun``.

Flow (contract 06/08): validate + normalize the query (trim + NFC;
empty-after-trim is ``INVALID_REQUEST``); scope-check ``document_ids``
(unknown -> ``DOCUMENT_NOT_FOUND``, never silently broaden); run both
candidate branches (P6), RRF-fuse (P7), rerank-or-fallback (P8); apply
``per_document_limit`` after global scoring then the final ``limit``,
preserving relative rank; assemble the ``RetrievalRun`` with truthful
``retrieval_mode``/``completeness``/``omissions``. **Both branches failed
is ``RETRIEVAL_UNAVAILABLE``**; a successful empty search is never an error.

No model downloads at serving time; budgets are constructor config
(contract 14 ``lexical_candidates``/``semantic_candidates``/
``rerank_candidates``).
"""

from __future__ import annotations

import unicodedata
from typing import Any
from uuid import UUID

from ..errors import VerityError
from ..models import (
    Completeness,
    RetrievalMode,
    RetrievalResult,
    RetrievalRun,
    SearchRequest,
)
from .branches import BRANCH_CANDIDATE_BUDGET, BranchResult
from .dense import DenseBranch
from .fusion import FUSED_CAP, FusedRun, fuse
from .lexical import LexicalBranch
from .rerank import rerank

__all__ = ["DefaultRetrievalService", "normalize_query"]


def normalize_query(query: str) -> str:
    """Trim and NFC-normalize a user query (contract 06)."""
    return unicodedata.normalize("NFC", query.strip())


class DefaultRetrievalService:
    """Contract-16 ``RetrievalService`` over a store + optional models.

    ``provider``/``reranker`` are injected behind the frozen protocols
    (offline, config-pinned); ``None`` means the capability is not
    provisioned and degrades with a truthful omission.
    """

    def __init__(
        self,
        store: Any,
        provider: Any | None = None,
        reranker: Any | None = None,
        *,
        rerank_enabled: bool = True,
        lexical_budget: int = BRANCH_CANDIDATE_BUDGET,
        semantic_budget: int = BRANCH_CANDIDATE_BUDGET,
        fused_cap: int = FUSED_CAP,
    ) -> None:
        self._store = store
        self._reranker = reranker
        self._rerank_enabled = rerank_enabled
        self._fused_cap = fused_cap
        self._lexical = LexicalBranch(store, lexical_budget)
        self._dense = DenseBranch(store, provider, semantic_budget)

    async def search(self, request: SearchRequest) -> RetrievalRun:
        query = self._validated_query(request)
        await self._check_scope(request)

        lexical = await self._lexical.candidates(request)
        dense = await self._dense.candidates(request)
        fused: FusedRun = fuse(lexical, dense, cap=self._fused_cap)
        reranked = await rerank(query, fused, self._reranker,
                                enabled=self._rerank_enabled)
        items = self._apply_limits(reranked.items, request)

        lexical_failed = bool(lexical.omissions)
        dense_failed = bool(dense.omissions)
        if lexical_failed and dense_failed:
            raise VerityError(
                "RETRIEVAL_UNAVAILABLE",
                "both retrieval branches are unavailable",
                {"omissions": list(reranked.omissions)},
            )

        if dense_failed:
            mode = RetrievalMode.LEXICAL_ONLY
        elif lexical_failed:
            mode = RetrievalMode.SEMANTIC_ONLY
        else:
            mode = RetrievalMode.HYBRID

        if not items:
            completeness = Completeness.EMPTY
        elif reranked.omissions:
            completeness = Completeness.PARTIAL
        else:
            completeness = Completeness.COMPLETE

        return RetrievalRun(
            items=[
                RetrievalResult(
                    chunk=item.chunk,
                    score=item.score,
                    dense_rank=item.dense_rank,
                    lexical_rank=item.lexical_rank,
                    rrf_score=item.rrf_score,
                    rerank_score=item.rerank_score,
                )
                for item in items
            ],
            retrieval_mode=mode,
            reranker_used=reranked.reranker_used,
            completeness=completeness,
            omissions=list(reranked.omissions),
        )

    # -- helpers ----------------------------------------------------------
    def _validated_query(self, request: SearchRequest) -> str:
        if not isinstance(request.query, str):
            raise VerityError("INVALID_REQUEST", "query must be a string",
                              {"field": "query"})
        query = normalize_query(request.query)
        if not query:
            raise VerityError(
                "INVALID_REQUEST",
                "query must be nonempty after trimming",
                {"field": "query"},
            )
        if not 2 <= len(query) <= 2000:
            raise VerityError(
                "INVALID_REQUEST",
                "query length must be 2-2000 after normalization",
                {"field": "query"},
            )
        request.validate()  # remaining SearchRequest bounds (contract 03)
        return query

    async def _check_scope(self, request: SearchRequest) -> None:
        """Unknown document IDs fail loudly (contract 06)."""
        if request.document_ids is None:
            return
        for document_id in request.document_ids:
            document = await self._store.get_document(UUID(document_id))
            if document is None:
                raise VerityError(
                    "DOCUMENT_NOT_FOUND",
                    "requested document is not registered",
                    {"document_id": document_id},
                )

    @staticmethod
    def _apply_limits(items, request: SearchRequest):
        """Per-document cap after global scoring, then the final limit."""
        capped = []
        per_document: dict[str, int] = {}
        for item in items:
            key = item.chunk.locator.document_id
            if request.per_document_limit is not None:
                if per_document.get(key, 0) >= request.per_document_limit:
                    continue
                per_document[key] = per_document.get(key, 0) + 1
            capped.append(item)
            if len(capped) >= request.limit:
                break
        return capped