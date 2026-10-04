"""VerityService — the transport-independent application boundary (contract 16).

Owner: Atharv. This is the ONLY adapter-facing core API: MCP, HTTP, SDK and
CLI delegate here and never touch SQL, retrieval strategies, citation
assembly or coverage evaluation directly.

``build_service()`` (zero-arg, agreed with Vandit in the PR #3 review) is the
frozen factory entrypoint: it reads config via ``verity.config.load_config``
and wires the real composition — SQLite store (PR-A2), ingestion pipeline
(Piyush P5), canonical evidence service (PR-A3) and coverage service
(Vanashree N1/N2) — plus the retrieval seam.

Error discipline (contract 17): the service raises only typed ``VerityError``
with frozen codes; a store-None lookup is translated here to the matching
NOT_FOUND error (``REQUIREMENT_NOT_FOUND`` / ``DOCUMENT_NOT_FOUND`` /
``EVIDENCE_NOT_FOUND`` / ``COVERAGE_NOT_FOUND``); None never crosses this
boundary. A no-match search is a successful SearchResult with ``items: []``,
never an error. ``request_id`` is never placed in ``details`` (adapters add
it).

Cancellation: service methods are async and the local SQLite work they await
is bounded and in-process. Any future collaborator that can exceed ~100ms
(embedding, rerank, model calls) must offload via ``anyio.to_thread`` and
must not claim a cancelled TIMEOUT stopped work it cannot interrupt.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable
from uuid import UUID

from .errors import VerityError
from .evidence import DefaultEvidenceService
from .models import (
    Completeness,
    CoverageRequest,
    CoverageResult,
    Document,
    DocumentKind,
    EvidenceLookup,
    IngestRequest,
    IngestResult,
    ListPage,
    Requirement,
    RetrievalMode,
    RetrievalResult,
    RetrievalRun,
    SearchRequest,
    SearchResult,
)
from .storage import SqliteKnowledgeStore

#: Contract 17: malformed ID syntax is INVALID_REQUEST, never *_NOT_FOUND.
_REQ_ID_RE = re.compile(r"^req_[0-9a-f]{64}$")
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _require_req_id(requirement_id: str) -> str:
    if not isinstance(requirement_id, str) or not _REQ_ID_RE.fullmatch(requirement_id):
        raise VerityError(
            "INVALID_REQUEST",
            "requirement_id must match req_ + 64 lowercase hex",
            {"field": "requirement_id"},
        )
    return requirement_id


def _require_uuid4(value: str, field: str) -> str:
    text = str(value)
    if not _UUID4_RE.fullmatch(text):
        raise VerityError(
            "INVALID_REQUEST",
            f"{field} must be a UUIDv4 string",
            {"field": field},
        )
    return text


@runtime_checkable
class VerityService(Protocol):
    """Contract 16 surface: the adapter-facing core API."""

    async def ingest(self, request: IngestRequest, data: bytes) -> IngestResult: ...
    async def search_evidence(self, request: SearchRequest) -> SearchResult: ...
    async def get_requirement(self, requirement_id: str) -> Requirement: ...
    async def get_evidence(self, evidence_id: str, context_chars: int = 1000) -> EvidenceLookup: ...
    async def check_coverage(self, request: CoverageRequest) -> CoverageResult: ...
    async def get_coverage(self, coverage_id: UUID) -> CoverageResult: ...
    async def get_document(self, document_id: UUID) -> Document: ...
    async def list_documents(self, limit: int, offset: int, kind: DocumentKind | None) -> ListPage: ...
    async def list_sources(self, limit: int, offset: int) -> ListPage: ...


class _LexicalOnlyRetrieval:
    """Interim retrieval seam until the retrieval owner's P6-P9 stack lands.

    Uses only ``KnowledgeStore.lexical_candidates`` (contract 16) and reports
    exactly what ran: ``retrieval_mode=lexical_only``, truthful omissions and
    ``completeness=partial`` while a branch is missing. The single-branch RRF
    score uses the frozen contract-06 constant (``1/(60 + rank)``). When
    Piyush's retrieval stack merges, ``build_service(retrieval=...)`` swaps
    this out with no other change.
    """

    _RRF_K = 60

    def __init__(self, store) -> None:
        self._store = store

    async def search(self, request: SearchRequest) -> RetrievalRun:
        candidates = await self._store.lexical_candidates(request, limit=50)
        per_doc = request.per_document_limit
        kept = []
        counts: dict[str, int] = {}
        for candidate in candidates:
            doc_id = candidate.chunk.locator.document_id
            if per_doc is not None and counts.get(doc_id, 0) >= per_doc:
                continue
            counts[doc_id] = counts.get(doc_id, 0) + 1
            kept.append(candidate)
            if len(kept) >= request.limit:
                break
        items = tuple(
            RetrievalResult(
                chunk=c.chunk,
                score=1.0 / (self._RRF_K + c.rank),
                dense_rank=None,
                lexical_rank=c.rank,
                rrf_score=1.0 / (self._RRF_K + c.rank),
                rerank_score=None,
            )
            for c in kept
        )
        if not items:
            return RetrievalRun(
                items=(), retrieval_mode=RetrievalMode.LEXICAL_ONLY,
                reranker_used=False, completeness=Completeness.EMPTY,
                omissions=("semantic_model_unavailable", "reranker_unavailable"),
            )
        return RetrievalRun(
            items=items, retrieval_mode=RetrievalMode.LEXICAL_ONLY,
            reranker_used=False, completeness=Completeness.PARTIAL,
            omissions=("semantic_model_unavailable", "reranker_unavailable"),
        )


class DefaultVerityService:
    """Real composition over injected collaborators (contract 16)."""

    def __init__(self, config, store, ingestion, retrieval, evidence, coverage) -> None:
        self.config = config
        self._store = store
        self._ingestion = ingestion
        self._retrieval = retrieval
        self._evidence = evidence
        self._coverage = coverage

    async def ingest(self, request: IngestRequest, data: bytes) -> IngestResult:
        return await self._ingestion.ingest(request, data)

    async def search_evidence(self, request: SearchRequest) -> SearchResult:
        run = await self._retrieval.search(request)
        return await self._evidence.from_retrieval(request, run)

    async def get_requirement(self, requirement_id: str) -> Requirement:
        _require_req_id(requirement_id)
        requirement = await self._store.get_requirement(requirement_id)
        if requirement is None:
            raise VerityError(
                "REQUIREMENT_NOT_FOUND",
                "no active requirement with that ID",
                {"requirement_id": requirement_id},
            )
        return requirement

    async def get_evidence(self, evidence_id: str, context_chars: int = 1000) -> EvidenceLookup:
        return await self._evidence.get(evidence_id, context_chars)

    async def check_coverage(self, request: CoverageRequest) -> CoverageResult:
        result = await self._coverage.check(request)
        # Contract 12: one immutable report row after evaluation.
        await self._store.save_coverage(result)
        return result

    async def get_coverage(self, coverage_id: UUID) -> CoverageResult:
        _require_uuid4(coverage_id, "coverage_id")
        result = await self._store.get_coverage(coverage_id)
        if result is None:
            raise VerityError(
                "COVERAGE_NOT_FOUND",
                "no coverage run with that ID",
                {"coverage_id": str(coverage_id)},
            )
        return result

    async def get_document(self, document_id: UUID) -> Document:
        _require_uuid4(document_id, "document_id")
        document = await self._store.get_document(document_id)
        if document is None:
            raise VerityError(
                "DOCUMENT_NOT_FOUND",
                "no document with that ID",
                {"document_id": str(document_id)},
            )
        return document

    async def list_documents(self, limit: int, offset: int, kind: DocumentKind | None) -> ListPage:
        return await self._store.list_documents(limit, offset, kind)

    async def list_sources(self, limit: int, offset: int) -> ListPage:
        return await self._store.list_sources(limit, offset)


def build_service(config=None, *, store=None, ingestion=None, retrieval=None,
                  coverage=None) -> DefaultVerityService:
    """The frozen factory entrypoint (zero-arg works; see module docstring).

    ``verity.service.build_service()`` returns a contract-16-compatible
    service wired to the real composition. Optional keyword collaborators are
    for tests and for swapping Piyush's retrieval stack in when PR-P3 lands.
    """
    if config is None:
        from .config import load_config

        config = load_config()
    if store is None:
        store = SqliteKnowledgeStore(config.database_path, config.data_dir)
        store.open()
    if ingestion is None:
        from .ingestion.pipeline import IngestionPipeline

        ingestion = IngestionPipeline(store)
    if retrieval is None:
        retrieval = _LexicalOnlyRetrieval(store)
    if coverage is None:
        from .coverage.candidates import FakeCodeEvidenceRetriever
        from .coverage.evaluator import DefaultRequirementEvaluator
        from .coverage.service import DefaultCoverageService
        from .coverage.workspace import RealWorkspaceScanner

        async def _lookup(requirement_id: str) -> Requirement:
            requirement = await store.get_requirement(requirement_id)
            if requirement is None:
                raise VerityError(
                    "REQUIREMENT_NOT_FOUND",
                    "no active requirement with that ID",
                    {"requirement_id": requirement_id},
                )
            return requirement

        coverage = DefaultCoverageService(
            RealWorkspaceScanner(config),
            FakeCodeEvidenceRetriever({}),  # real candidate search is N3
            DefaultRequirementEvaluator(),
            _lookup,
        )
    evidence = DefaultEvidenceService(store)
    return DefaultVerityService(config, store, ingestion, retrieval, evidence, coverage)