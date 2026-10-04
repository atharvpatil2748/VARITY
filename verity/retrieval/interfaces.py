"""Public cross-module retrieval interfaces owned by Piyush (contract 16).

Exact frozen signatures from ``Docs/contracts/16_VERITY_PUBLIC_INTERFACES.md``:

* ``EmbeddingProvider`` — BGE-M3 semantic vectors (offline, pre-provisioned).
* ``Reranker`` — optional BGE reranker scoring.
* ``RetrievalService.search`` — the one public knowledge-search operation.

**D1 resolved (issue #2, docs revision 1.0.2):** contract 06 now reads
``RetrievalService.search(request: SearchRequest) -> RetrievalRun``, aligned
with contract 16. ``RetrievalRun`` is the final public return type; the
``search`` implementation itself (P9) still waits for PR-A3's real store
wiring per roadmap 08, with fixture/fake work continuing meanwhile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from verity.models import Chunk, RetrievalRun, SearchRequest


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Semantic embedding provider (contract 06/16). Models are local-only."""

    model_id: str

    async def embed(self, text: str) -> "tuple[float, ...]":
        ...

    async def embed_batch(self, texts: "tuple[str, ...]") -> "tuple[tuple[float, ...], ...]":
        ...


@runtime_checkable
class Reranker(Protocol):
    """Optional reranker (contract 06/16): score(query, chunks) per chunk."""

    model_id: str

    async def score(self, query: str, chunks: "tuple[Chunk, ...]") -> "tuple[float, ...]":
        ...


@runtime_checkable
class RetrievalService(Protocol):
    """The single public knowledge-search boundary (contract 06/16)."""

    async def search(self, request: "SearchRequest") -> "RetrievalRun":
        ...