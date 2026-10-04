"""Canonical Evidence, citation and resolution service (contracts 07/16).

Owner: Atharv. Adapters must not build or rename Evidence fields.

* ``from_retrieval`` converts a ``RetrievalRun`` into the canonical
  ``SearchResult`` of ``Evidence`` objects (one Evidence per immutable
  ``(version_id, chunk_id)`` pair; quote equals the stored normalized
  ``Chunk.text`` exactly).
* ``get`` resolves an ``evidence_id`` against the stored version, verifying
  the version and chunk still exist, and returns adjacent canonical block
  context. Historical versions stay resolvable (change log 1.0.3); a
  never-known ID is ``EVIDENCE_NOT_FOUND``. Retention cleanup must later
  distinguish ``EVIDENCE_GONE`` via tombstones (contract 07).
* ``format_citation`` builds the single canonical citation label:
  ``<document name> — <location parts> [<local requirement ID>]``.

Citation construction never calls a model. Evidence scores indicate
retrieval ranking, not truth or coverage.
"""

from __future__ import annotations

import re
from uuid import UUID

from .errors import VerityError
from .ids import make_evidence_id
from .models import (
    Citation,
    Evidence,
    EvidenceLookup,
    Locator,
    Ranking,
    RetrievalRun,
    SearchResult,
)

SCHEMA_VERSION = "1.0.0"

#: Canonical citation marker for Cline/SDK answer text (contract 07):
#: ``[[ev_<64 lowercase hex>]]``. The UI parses only this exact form.
CITATION_MARKER_RE = re.compile(r"\[\[ev_[0-9a-f]{64}\]\]")
_EVIDENCE_ID_RE = re.compile(r"^ev_[0-9a-f]{64}$")

#: Contract 07 bound for ``context_chars``.
CONTEXT_CHARS_MAX = 4000


def citation_marker(evidence_id: str) -> str:
    """The canonical marker string for an evidence ID: ``[[ev_<hex>]]``."""
    return f"[[{evidence_id}]]"


class EvidenceService:
    """Contract 16 protocol: canonical Evidence assembly and resolution."""

    async def from_retrieval(self, request, run: RetrievalRun) -> SearchResult: ...
    async def get(self, evidence_id: str, context_chars: int = 1000) -> EvidenceLookup: ...
    def format_citation(
        self, evidence_id: str, document_name: str, locator: Locator,
        local_id: str | None,
    ) -> Citation: ...


class DefaultEvidenceService(EvidenceService):
    """Canonical implementation over a contract-16 ``KnowledgeStore``.

    No SQL, retrieval strategy, model call or transport shape happens here:
    the service resolves origins through the store's evidence path and
    assembles the one canonical ``Evidence`` object.
    """

    def __init__(self, store) -> None:
        self._store = store

    def format_citation(
        self, evidence_id: str, document_name: str, locator: Locator,
        local_id: str | None,
    ) -> Citation:
        """Build the canonical citation label (contract 07 grammar).

        ``<document name> — <location parts> [<local requirement ID>]``;
        location parts in order, separated by ``; ``: ``p. <page>`` when page
        nonnull; ``§ <h1> / <h2>`` when heading path nonempty;
        ``L<start>-<end>`` when both lines nonnull. Absent parts are omitted,
        the bracketed local ID is omitted when ``local_id`` is None, and with
        no location parts the label is the document name alone.
        """
        parts: list[str] = []
        if locator.page is not None:
            parts.append(f"p. {locator.page}")
        if locator.heading_path:
            parts.append("§ " + " / ".join(locator.heading_path))
        if locator.start_line is not None and locator.end_line is not None:
            parts.append(f"L{locator.start_line}-{locator.end_line}")
        label = document_name
        if parts:
            label += " — " + "; ".join(parts)
        if local_id is not None:
            label += f" [{local_id}]"
        return Citation(evidence_id=evidence_id, label=label, locator=locator)


    async def from_retrieval(self, request, run: RetrievalRun) -> SearchResult:
        """Convert a retrieval run into the canonical SearchResult (contract 03).

        ``Evidence.score`` equals the rerank score when the reranker ran,
        otherwise the RRF score (``RetrievalResult.score`` carries exactly
        this). Ranking provenance is preserved on every item.
        """
        items: list[Evidence] = []
        for result in run.items:
            chunk = result.chunk
            evidence_id = make_evidence_id(
                UUID(chunk.locator.version_id), chunk.chunk_id
            )
            origin = await self._store.get_evidence_origin(evidence_id)
            if origin is None:
                raise VerityError(
                    "INTERNAL_ERROR",
                    "retrieval returned a chunk with no evidence origin",
                    {"chunk_id": chunk.chunk_id},
                )
            _chunk, document, provenance = origin
            local_id = None
            if chunk.requirement_id is not None:
                local_id = self._store.get_requirement_local_id(
                    chunk.locator.version_id, chunk.requirement_id
                )
            items.append(Evidence(
                schema_version=SCHEMA_VERSION,
                evidence_id=evidence_id,
                chunk_id=chunk.chunk_id,
                kind=chunk.kind,
                quote=chunk.text,
                requirement_id=chunk.requirement_id,
                citation=self.format_citation(
                    evidence_id, document.name, chunk.locator, local_id
                ),
                provenance=provenance,
                score=result.score,
                ranking=Ranking(
                    dense_rank=result.dense_rank,
                    lexical_rank=result.lexical_rank,
                    rrf_score=result.rrf_score,
                    rerank_score=result.rerank_score,
                ),
            ))
        return SearchResult(
            schema_version=SCHEMA_VERSION,
            query=request.query,
            retrieval_mode=run.retrieval_mode,
            completeness=run.completeness,
            total_returned=len(items),
            items=items,
            reranker_used=run.reranker_used,
            omissions=list(run.omissions),
        )

    async def get(self, evidence_id: str, context_chars: int = 1000) -> EvidenceLookup:
        """Resolve one evidence ID against its stored version (contract 07).

        The quote is verified against the stored normalized chunk text by
        construction (it is read back from the store). Direct lookup sets
        ``score=null`` and all ranking fields null. Historical versions
        resolve through the version-bound origin (change log 1.0.3).
        """
        if not isinstance(evidence_id, str) or not _EVIDENCE_ID_RE.fullmatch(evidence_id):
            raise VerityError(
                "INVALID_REQUEST",
                "evidence_id must match ev_ + 64 lowercase hex",
                {"field": "evidence_id"},
            )
        if not isinstance(context_chars, int) or isinstance(context_chars, bool) \
                or not 0 <= context_chars <= CONTEXT_CHARS_MAX:
            raise VerityError(
                "INVALID_REQUEST",
                f"context_chars must be an integer 0-{CONTEXT_CHARS_MAX}",
                {"field": "context_chars"},
            )
        origin = await self._store.get_evidence_origin(evidence_id)
        if origin is None:
            # v1 retains all versions (contract 13); retention cleanup must
            # report EVIDENCE_GONE via tombstones when it exists.
            raise VerityError(
                "EVIDENCE_NOT_FOUND",
                "no such evidence ID",
                {"evidence_id": evidence_id},
            )
        chunk, document, provenance = origin
        local_id = None
        if chunk.requirement_id is not None:
            local_id = self._store.get_requirement_local_id(
                chunk.locator.version_id, chunk.requirement_id
            )
        evidence = Evidence(
            schema_version=SCHEMA_VERSION,
            evidence_id=evidence_id,
            chunk_id=chunk.chunk_id,
            kind=chunk.kind,
            quote=chunk.text,
            requirement_id=chunk.requirement_id,
            citation=self.format_citation(
                evidence_id, document.name, chunk.locator, local_id
            ),
            provenance=provenance,
            score=None,
            ranking=Ranking(
                dense_rank=None, lexical_rank=None,
                rrf_score=None, rerank_score=None,
            ),
        )
        before, after = self._store.get_block_context(
            chunk.locator.version_id, chunk.block_start, chunk.block_end,
            context_chars,
        )
        return EvidenceLookup(
            schema_version=SCHEMA_VERSION,
            evidence=evidence,
            context_before=before,
            context_after=after,
        )