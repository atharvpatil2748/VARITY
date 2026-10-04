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