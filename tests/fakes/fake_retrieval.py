"""FakeRetrievalService sample object (roadmap 09 shared mocks, Piyush).

Returns a ``RetrievalRun``-shaped JSON instance (contract 16/03) with ranked
chunks, ranking metadata and truthful omissions without loading any model.
Atharv's EvidenceService tests can construct their own local fake from this
sample. D1 (open issue #2) must be approved before production wiring; this
fake intentionally does not implement a final public search signature.
"""

from __future__ import annotations

from typing import Any, Mapping


def sample_retrieval_run() -> dict:
    """One deterministic retrieval run over the payments fixture chunk."""
    chunk = {
        "schema_version": "1.0.0",
        "chunk_id": "chk_71bb4eb1f7917adbd4771acd9946ee1a30994af19c4ebbf66ecd2b1e4b89b16a",
        "kind": "requirement",
        "text": "Refund requests MUST be accepted only within 30 days.",
        "locator": {
            "source_id": "24da624f-7fd0-41ea-a49b-8449cbb179d9",
            "document_id": "ebc2352e-ff9c-4167-b11a-1e30d550411d",
            "version_id": "129dcd06-1ba1-4f0c-bf7e-c678f905b624",
            "source_path": "specs/payments.md",
            "page": None,
            "heading_path": ["Requirements", "REQ-001: Refund window"],
            "start_line": 12,
            "end_line": 12,
            "start_offset": None,
            "end_offset": None,
        },
        "block_start": 1,
        "block_end": 2,
        "ordinal": 1,
        "requirement_id": "req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2",
    }
    return {
        "items": [
            {
                "chunk": chunk,
                "score": 0.016129032258064516,
                "dense_rank": None,
                "lexical_rank": 1,
                "rrf_score": 0.016129032258064516,
                "rerank_score": None,
            }
        ],
        "retrieval_mode": "lexical_only",
        "reranker_used": False,
        "completeness": "complete",
        "omissions": ["semantic_model_unavailable"],
    }


class FakeRetrievalService:
    """Minimal fake returning the frozen RetrievalRun shape (roadmap 09)."""

    def __init__(self, run: Mapping[str, Any] | None = None) -> None:
        self._run = dict(run) if run is not None else sample_retrieval_run()
        self.requests: list[Mapping[str, Any]] = []

    async def search(self, request: Mapping[str, Any]) -> dict:
        self.requests.append(request)
        return self._run


class FakeEmbeddingProvider:
    """Pre-provisioned embedding stand-in (P6); never loads/downloads models."""

    model_id = "fake/bge-m3@test"

    def __init__(self, vector: tuple[float, ...] = (1.0, 0.0),
                 fail: bool = False) -> None:
        self.vector = vector
        self.fail = fail
        self.embed_calls: list[str] = []

    async def embed(self, text: str) -> tuple[float, ...]:
        self.embed_calls.append(text)
        if self.fail:
            raise RuntimeError("model not provisioned")
        return self.vector

    async def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(await self.embed(text) for text in texts)


class FakeCandidateStore:
    """Scriptable candidate reader for P6 branch tests (no SQL)."""

    def __init__(self, lexical=None, vector=None) -> None:
        self.lexical = tuple(lexical or ())
        self.vector = tuple(vector or ())
        self.fail_lexical = False
        self.fail_vector = False
        self.lexical_requests: list[Any] = []
        self.vector_requests: list[Any] = []

    async def lexical_candidates(self, request, limit):
        self.lexical_requests.append((request, limit))
        if self.fail_lexical:
            raise RuntimeError("fts index corrupt")
        return self.lexical[:limit]

    async def vector_candidates(self, query_vector, request, model_id, limit):
        self.vector_requests.append((query_vector, request, model_id, limit))
        if self.fail_vector:
            raise RuntimeError("vector scan failed")
        return self.vector[:limit]


def ranked(chunk_id: str, rank: int = 1, score: float = 1.0):
    """Build a RankedChunk over a minimal canonical Chunk (test helper)."""
    from verity.models import Chunk, ChunkKind, Locator
    from verity.storage.base import RankedChunk

    locator = Locator(
        source_id="24da624f-7fd0-41ea-a49b-8449cbb179d9",
        document_id="ebc2352e-ff9c-4167-b11a-1e30d550411d",
        version_id="129dcd06-1ba1-4f0c-bf7e-c678f905b624",
        source_path="specs/payments.md", page=None,
        start_line=1, end_line=1, start_offset=None, end_offset=None,
        heading_path=["Requirements"],
    )
    chunk = Chunk(
        schema_version="1.0.0", chunk_id=chunk_id, kind=ChunkKind.GENERAL_CHUNK,
        text="Refund window policy.", locator=locator,
        block_start=0, block_end=0, ordinal=0, requirement_id=None,
    )
    return RankedChunk(chunk=chunk, rank=rank, raw_score=score)