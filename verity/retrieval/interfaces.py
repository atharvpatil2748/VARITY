"""Public cross-module retrieval interfaces owned by Piyush (contract 16).

Exact frozen signatures from ``Docs/contracts/16_VERITY_PUBLIC_INTERFACES.md``:

* ``EmbeddingProvider`` — BGE-M3 semantic vectors (offline, pre-provisioned).
* ``Reranker`` — optional BGE reranker scoring.
* ``RetrievalService.search`` — the one public knowledge-search operation.

**D1 note (open issue #2):** contract 06 states the return as
``tuple[RetrievalResult, ...]`` while contract 16 states ``RetrievalRun``.
Until the team approves an amendment, code stubs follow ``16`` because
contract 01 assigns callable-signature authority to ``16`` (roadmap 06 D1
row), but no final public search implementation is published here and PR-P3
stays blocked. Retrieval internals (P6-P8) continue against fakes.
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