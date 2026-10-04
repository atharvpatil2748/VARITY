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
from .interfaces import EmbeddingProvider, Reranker, RetrievalService
from .lexical import LexicalBranch

__all__ = [
    "BRANCH_CANDIDATE_BUDGET",
    "BranchResult",
    "DenseBranch",
    "EmbeddingProvider",
    "LEXICAL_UNAVAILABLE",
    "LexicalBranch",
    "Reranker",
    "RetrievalService",
    "SEMANTIC_MODEL_UNAVAILABLE",
    "SEMANTIC_UNAVAILABLE",
]