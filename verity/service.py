"""VERITY transport-independent application API (service boundary).

Contract: Docs/contracts/16_VERITY_PUBLIC_INTERFACES.md; structure reference:
Docs/ARCHITECTURE.md Phase 9. Owner Atharv.

``VerityService`` owns ``ingest``, ``search_evidence``, ``get_requirement``,
``get_evidence``, ``compare_sources`` and ``check_coverage``. CLI, MCP, HTTP
and SDK adapters call this API; no transport writes SQL or ranks results.
This module is a v1 skeleton: signatures are frozen, bodies are implemented
per the Phase 10/11 plan (contracts 03/06/12/16).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for annotations
    from .config import VerityConfig
    from .models import (
        CoverageRequest,
        CoverageResult,
        Evidence,
        EvidenceLookup,
        IngestRequest,
        IngestResult,
        Requirement,
        RetrievalResult,
        SearchRequest,
    )


class VerityService:
    """Transport-independent application boundary (contract 16).

    Adapters (MCP stdio, HTTP v1, Cline SDK tools, CLI) delegate here and
    only translate payloads; they never query storage directly.
    """

    def __init__(self, config: VerityConfig) -> None:
        self.config = config
        # Wired in Phase 11 integration: storage store, ingestion pipeline,
        # retrieval stack and coverage evaluator per contract 15 boundaries.

    def ingest(self, request: IngestRequest) -> IngestResult:
        """Hash, version, parse, chunk and index one document (contract 05).

        Persists original bytes under ``data/originals/<sha256>`` in one
        transaction per document version.
        """
        raise NotImplementedError("ingest: scheduled Phase 11, contract 05")

    def search_evidence(self, request: SearchRequest) -> RetrievalResult:
        """Hybrid lexical/semantic search fused via RRF (contract 06).

        Filters by document first, then ranks; reports ``retrieval_mode``,
        ``reranker_used``, completeness and oissions truthfully.
        """
        raise NotImplementedError("search_evidence: scheduled Phase 11, contract 06")

    def get_requirement(self, requirement_key: str) -> Requirement:
        """Return one explicit spec entity; never inferred status (contract 03)."""
        raise NotImplementedError("get_requirement: scheduled Phase 11, contract 03")

    def get_evidence(self, evidence_id: str) -> Evidence:
        """Resolve a citation to its immutable version and quote (contract 07)."""
        raise NotImplementedError("get_evidence: scheduled Phase 11, contract 07")

    def compare_sources(
        self, request: SearchRequest
    ) -> dict[str, object]:
        """Group evidence per source for cross-document comparison.

        MVP assessment is always ``unassessed`` (contract 08); Cline owns
        agreement/conflict synthesis.
        """
        raise NotImplementedError("compare_sources: scheduled Phase 11, contract 08")

    def check_coverage(self, request: CoverageRequest) -> CoverageResult:
        """Inspect configured workspace code/tests against requirements (contract 12)."""
        raise NotImplementedError("check_coverage: scheduled Phase 11, contract 12")