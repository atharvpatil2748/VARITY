"""VERITY retrieval package (owner: Piyush Ghayal).

Public interfaces (contract 16): ``EmbeddingProvider``, ``Reranker``,
``RetrievalService``. Internal candidate branches (P6): ``LexicalBranch``
and ``DenseBranch`` producing ``BranchResult`` streams; RRF fusion (P7),
reranking (P8) and multi-document search (P9) land behind these. The final
``RetrievalService.search`` returns ``RetrievalRun`` (D1 resolved, docs
1.0.2); its real wiring waits for PR-A3 per roadmap 08.
"""

from __future__ import annotations

from .branches import (
    BRANCH_CANDIDATE_BUDGET,
    LEXICAL_UNAVAILABLE,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_UNAVAILABLE,
    BranchResult,
)
from .dense import DenseBranch
from .fusion import FUSED_CAP, RRF_K, FusedCandidate, FusedRun, fuse
from .interfaces import EmbeddingProvider, Reranker, RetrievalService
from .lexical import LexicalBranch
from .rerank import (
    RERANK_INPUT_CAP,
    RERANKER_UNAVAILABLE,
    RerankedRun,
    ScoredCandidate,
    rerank,
)
from .service import DefaultRetrievalService, normalize_query

__all__ = [
    "BRANCH_CANDIDATE_BUDGET",
    "BranchResult",
    "DefaultRetrievalService",
    "DenseBranch",
    "EmbeddingProvider",
    "FUSED_CAP",
    "FusedCandidate",
    "FusedRun",
    "LEXICAL_UNAVAILABLE",
    "LexicalBranch",
    "RERANK_INPUT_CAP",
    "RERANKER_UNAVAILABLE",
    "RRF_K",
    "RerankedRun",
    "Reranker",
    "RetrievalService",
    "SEMANTIC_MODEL_UNAVAILABLE",
    "SEMANTIC_UNAVAILABLE",
    "ScoredCandidate",
    "fuse",
    "normalize_query",
    "rerank",
]