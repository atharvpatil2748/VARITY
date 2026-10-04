"""VERITY retrieval package (owner: Piyush Ghayal).

Public interfaces (contract 16): ``EmbeddingProvider``, ``Reranker``,
``RetrievalService``. Candidate strategies (P6), RRF fusion (P7), reranking
(P8) and multi-document search (P9) land here behind these interfaces; the
final ``RetrievalService.search`` signature/wiring waits for the team-approved
D1 amendment (open issue #2) and PR-A3.
"""

from __future__ import annotations

from .interfaces import EmbeddingProvider, Reranker, RetrievalService

__all__ = ["EmbeddingProvider", "Reranker", "RetrievalService"]