"""Evidence service tests (contracts 07/16) — PR-A3 gate.

Gate per roadmap 02: origin/history/citation tests. Covers the canonical
citation label grammar, from_retrieval -> SearchResult assembly, get ->
EvidenceLookup resolution (score null, bounded block context), and
historical evidence origin (change log 1.0.3 D3 semantics).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from verity.errors import VerityError
from verity.evidence import (
    CITATION_MARKER_RE,
    DefaultEvidenceService,
    citation_marker,
)
from verity.ids import make_chunk_id, make_evidence_id, make_requirement_id
from verity.models import (
    Chunk,
    ChunkDraft,
    ChunkKind,
    Completeness,
    DocumentKind,
    DocumentMetadata,
    IngestRequest,
    Locator,
    ParsedBlock,
    ParsedDocument,
    RetrievalMode,
    RetrievalResult,
    RetrievalRun,
    SearchRequest,
)
from verity.storage import SqliteKnowledgeStore


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path: Path):
    s = SqliteKnowledgeStore(tmp_path / "verity.sqlite3", tmp_path)
    s.open()
    yield s
    s.close()


@pytest.fixture()
def service(store):
    return DefaultEvidenceService(store)


def _metadata(name: str = "payments.md") -> DocumentMetadata:
    return DocumentMetadata(
        metadata_version="1.0.0", title="Payments", source_key="payments-api",
        project="payment-service", spec_version="1.0", language="en",
        page_count=None, parser_name="markdown", parser_version="1.0.0",
        warnings=[],
    )


def _locator(identity, heading=(), page=None, lines=(None, None)) -> Locator:
    return Locator(
        source_id=str(identity.source_id),
        document_id=str(identity.document_id),
        version_id=str(identity.version_id),
        source_path="specs/payments.md",
        page=page,
        start_line=lines[0], end_line=lines[1],
        start_offset=None, end_offset=None,
        heading_path=list(heading),
    )


def _ingest(store, block_texts, chunk_specs, source_id=None):
    """Ingest a document of blocks; chunk_specs = (block_start, block_end,
    kind, requirement_id, text) per chunk. Returns (identity, chunk models)."""
    texts = list(block_texts)
    request = IngestRequest(source_path="specs/payments.md", source_id=source_id)
    import hashlib

    sha = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
    identity = run(store.prepare_ingestion(request, sha, "payments-api"))
    parsed = ParsedDocument(
        metadata=_metadata(),
        blocks=[ParsedBlock(
            ordinal=i, text=t, block_type="paragraph", page=None,
            start_line=i + 1, end_line=i + 1,
            start_offset=None, end_offset=None, heading_path=["Intro"],
        ) for i, t in enumerate(texts)],
        media_type="text/markdown",
        kind=DocumentKind.SPEC,
    )
    chunks = []
    for block_start, block_end, kind, requirement_id, text in chunk_specs:
        draft = ChunkDraft(
            kind=kind, text=text, block_start=block_start, block_end=block_end,
            start_offset=None, end_offset=None,
            requirement_id=requirement_id,
        )
        chunks.append(Chunk(
            schema_version="1.0.0",
            chunk_id=make_chunk_id(identity.version_id, draft),
            kind=kind, text=text,
            locator=_locator(identity, heading=("Intro",)),
            block_start=block_start, block_end=block_end,
            ordinal=len(chunks), requirement_id=requirement_id,
        ))
    result = run(store.activate_ingestion(
        identity, request, parsed, tuple(chunks), (), (),
        "\n".join(texts).encode("utf-8"),
    ))
    return identity, tuple(chunks), result


# ---------------------------------------------------------------------------
# Citation label grammar (contract 07)
# ---------------------------------------------------------------------------


def test_format_citation_full_label(service) -> None:
    locator = Locator(
        source_id=str(uuid4()), document_id=str(uuid4()),
        version_id=str(uuid4()), source_path="docs/payments-api.pdf",
        page=10, start_line=10, end_line=12,
        start_offset=None, end_offset=None,
        heading_path=["Refunds", "Duplicate requests"],
    )
    citation = service.format_citation(
        "ev_" + "a" * 64, "payments-api.pdf", locator, "REQ-003")
    assert citation.label == (
        "payments-api.pdf — p. 10; § Refunds / Duplicate requests; L10-12 [REQ-003]"
    )
    assert citation.evidence_id == "ev_" + "a" * 64


def test_format_citation_contract_example(service) -> None:
    # The exact example from contract 07.
    locator = Locator(
        source_id=str(uuid4()), document_id=str(uuid4()),
        version_id=str(uuid4()), source_path="docs/payments-api.pdf",
        page=10, start_line=None, end_line=None,
        start_offset=None, end_offset=None,
        heading_path=["Refunds", "Duplicate requests"],
    )
    citation = service.format_citation(
        "ev_" + "a" * 64, "payments-api.pdf", locator, "REQ-003")
    assert citation.label == "payments-api.pdf — p. 10; § Refunds / Duplicate requests [REQ-003]"


def test_format_citation_name_only_when_no_location(service) -> None:
    locator = Locator(
        source_id=str(uuid4()), document_id=str(uuid4()),
        version_id=str(uuid4()), source_path="notes.txt",
        page=None, start_line=None, end_line=None,
        start_offset=None, end_offset=None, heading_path=[],
    )
    assert service.format_citation("ev_" + "b" * 64, "notes.txt", locator, None) \
        .label == "notes.txt"


def test_format_citation_omits_null_local_id_and_partial_parts(service) -> None:
    locator = Locator(
        source_id=str(uuid4()), document_id=str(uuid4()),
        version_id=str(uuid4()), source_path="src/refund.py",
        page=None, start_line=5, end_line=7,
        start_offset=None, end_offset=None, heading_path=[],
    )
    assert service.format_citation("ev_" + "c" * 64, "refund.py", locator, None) \
        .label == "refund.py — L5-7"


def test_citation_marker_exact_form() -> None:
    evidence_id = "ev_" + "d" * 64
    assert citation_marker(evidence_id) == f"[[{evidence_id}]]"
    assert CITATION_MARKER_RE.fullmatch(citation_marker(evidence_id))
    assert not CITATION_MARKER_RE.fullmatch("[[ev_short]]")


# ---------------------------------------------------------------------------
# get: origin, quote exactness, bounded context (contract 07)
# ---------------------------------------------------------------------------


def test_get_round_trip_score_null_with_context(store, service) -> None:
    identity, chunks, _ = _ingest(
        store,
        ["Heading block", "Target chunk block", "Trailing block"],
        [(1, 1, ChunkKind.GENERAL_CHUNK, None, "Target chunk block")],
    )
    evidence_id = make_evidence_id(identity.version_id, chunks[0].chunk_id)
    lookup = run(service.get(evidence_id))
    assert lookup.schema_version == "1.0.0"
    assert lookup.evidence.quote == "Target chunk block"  # exact stored text
    assert lookup.evidence.score is None  # direct lookup: no query score
    assert lookup.evidence.ranking.dense_rank is None
    assert lookup.evidence.ranking.lexical_rank is None
    assert lookup.evidence.ranking.rrf_score is None
    assert lookup.evidence.ranking.rerank_score is None
    # Context comes from adjacent canonical blocks of the same version.
    assert lookup.context_before == "Heading block"
    assert lookup.context_after == "Trailing block"


def test_get_context_chars_cap_and_zero(store, service) -> None:
    identity, chunks, _ = _ingest(
        store,
        ["AAAAAAAAAA", "target", "BBBBBBBBBB"],
        [(1, 1, ChunkKind.GENERAL_CHUNK, None, "target")],
    )
    evidence_id = make_evidence_id(identity.version_id, chunks[0].chunk_id)
    lookup = run(service.get(evidence_id, context_chars=4))
    assert lookup.context_before == "AAAA"
    assert lookup.context_after == "BBBB"
    zero = run(service.get(evidence_id, context_chars=0))
    assert zero.context_before == "" and zero.context_after == ""


def test_get_context_chars_bounds(store, service) -> None:
    identity, chunks, _ = _ingest(
        store, ["only"], [(0, 0, ChunkKind.GENERAL_CHUNK, None, "only")])
    evidence_id = make_evidence_id(identity.version_id, chunks[0].chunk_id)
    run(service.get(evidence_id, context_chars=4000))  # upper bound ok
    for bad in (-1, 4001, True, "10"):
        with pytest.raises(VerityError) as exc:
            run(service.get(evidence_id, context_chars=bad))
        assert exc.value.code == "INVALID_REQUEST"


def test_get_not_found_and_malformed(service) -> None:
    with pytest.raises(VerityError) as exc:
        run(service.get("ev_" + "9" * 64))
    assert exc.value.code == "EVIDENCE_NOT_FOUND"
    for bad in ("ev_ZZ", "chk_" + "a" * 64, "", 42):
        with pytest.raises(VerityError) as exc:
            run(service.get(bad))
        assert exc.value.code == "INVALID_REQUEST"


# ---------------------------------------------------------------------------
# from_retrieval: SearchResult assembly (contract 03/07)
# ---------------------------------------------------------------------------


def test_from_retrieval_builds_search_result(store, service) -> None:
    identity, chunks, _ = _ingest(
        store,
        ["Alpha block", "Beta block"],
        [(0, 0, ChunkKind.GENERAL_CHUNK, None, "Alpha block"),
         (1, 1, ChunkKind.GENERAL_CHUNK, None, "Beta block")],
    )
    run_ = RetrievalRun(
        items=(
            RetrievalResult(chunk=chunks[0], score=0.0317,
                            dense_rank=1, lexical_rank=2,
                            rrf_score=0.0317, rerank_score=None),
            RetrievalResult(chunk=chunks[1], score=0.0123,
                            dense_rank=2, lexical_rank=1,
                            rrf_score=0.0123, rerank_score=None),
        ),
        retrieval_mode=RetrievalMode.HYBRID,
        reranker_used=False,
        completeness=Completeness.COMPLETE,
        omissions=["semantic_model_unavailable"],
    )
    request = SearchRequest(
        query="refund window", document_ids=None,
        document_kinds=None, chunk_kinds=None)
    result = run(service.from_retrieval(request, run_))
    assert result.schema_version == "1.0.0"
    assert result.query == "refund window"
    assert result.total_returned == 2 == len(result.items)
    assert result.retrieval_mode is RetrievalMode.HYBRID
    assert result.reranker_used is False
    assert result.completeness is Completeness.COMPLETE
    assert result.omissions == ["semantic_model_unavailable"]
    first = result.items[0]
    # Score equals rerank when used, otherwise RRF (RetrievalResult.score).
    assert first.score == 0.0317 == first.ranking.rrf_score
    assert first.quote == "Alpha block"  # exact stored text
    assert first.citation.label.startswith("payments.md — § Intro")
    assert first.provenance.parser_name == "markdown"


def test_from_retrieval_rerank_score_when_used(store, service) -> None:
    identity, chunks, _ = _ingest(
        store, ["Gamma block"], [(0, 0, ChunkKind.GENERAL_CHUNK, None, "Gamma block")])
    run_ = RetrievalRun(
        items=(RetrievalResult(chunk=chunks[0], score=0.9,
                               dense_rank=1, lexical_rank=1,
                               rrf_score=0.03, rerank_score=0.9),),
        retrieval_mode=RetrievalMode.HYBRID,
        reranker_used=True,
        completeness=Completeness.COMPLETE,
        omissions=(),
    )
    request = SearchRequest(
        query="gamma", document_ids=None, document_kinds=None, chunk_kinds=None)
    result = run(service.from_retrieval(request, run_))
    assert result.items[0].score == 0.9 == result.items[0].ranking.rerank_score


# ---------------------------------------------------------------------------
# Historical origin (change log 1.0.3, D3 Option B)
# ---------------------------------------------------------------------------


def test_historical_evidence_resolves_with_version_bound_document(
    store, service,
) -> None:
    identity_v1, chunks_v1, _ = _ingest(
        store, ["Old refund policy v1"],
        [(0, 0, ChunkKind.GENERAL_CHUNK, None, "Old refund policy v1")])
    old_evidence_id = make_evidence_id(
        identity_v1.version_id, chunks_v1[0].chunk_id)
    # Changed content creates v2 and supersedes v1.
    identity_v2, chunks_v2, second = _ingest(
        store, ["New refund policy v2"],
        [(0, 0, ChunkKind.GENERAL_CHUNK, None, "New refund policy v2")],
        source_id=identity_v1.source_id)
    assert second.created_new_version is True

    # Historical citation still resolves against the old version (contract 07).
    lookup = run(service.get(old_evidence_id))
    assert lookup.evidence.quote == "Old refund policy v1"
    # D3 Option B: the origin Document describes the evidence's version.
    origin = run(store.get_evidence_origin(old_evidence_id))
    assert origin is not None and origin[1].version_id == str(identity_v1.version_id)
    # The active document reports the new version everywhere else.
    active = run(store.get_document(identity_v2.document_id))
    assert active.version_id == str(identity_v2.version_id)


def test_get_requirement_local_id_resolution(store, service) -> None:
    import hashlib

    from verity.models import Requirement

    text = "Refund window MUST be configurable."
    request = IngestRequest(source_path="specs/payments.md")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    identity = run(store.prepare_ingestion(request, sha, "payments-api"))
    requirement_id = make_requirement_id(identity.source_id, "REQ-001")
    locator = _locator(identity, heading=("Requirements", "REQ-001"))
    draft = ChunkDraft(
        kind=ChunkKind.REQUIREMENT, text=text, block_start=0, block_end=0,
        start_offset=None, end_offset=None, requirement_id=requirement_id)
    chunk = Chunk(
        schema_version="1.0.0",
        chunk_id=make_chunk_id(identity.version_id, draft),
        kind=ChunkKind.REQUIREMENT, text=text, locator=locator,
        block_start=0, block_end=0, ordinal=0, requirement_id=requirement_id)
    requirement = Requirement(
        schema_version="1.0.0", requirement_id=requirement_id,
        local_id="REQ-001", source_id=str(identity.source_id),
        document_id=str(identity.document_id), version_id=str(identity.version_id),
        title="Refund window", text=text, chunk_id=chunk.chunk_id,
        evidence_id=make_evidence_id(identity.version_id, chunk.chunk_id),
        locator=locator)
    parsed = ParsedDocument(
        metadata=_metadata(), blocks=[ParsedBlock(
            ordinal=0, text=text, block_type="paragraph", page=None,
            start_line=1, end_line=1, start_offset=None, end_offset=None,
            heading_path=["Requirements", "REQ-001"])],
        media_type="text/markdown", kind=DocumentKind.SPEC)
    run(store.activate_ingestion(
        identity, request, parsed, (chunk,), (requirement,), (), text.encode("utf-8")))

    lookup = run(service.get(make_evidence_id(identity.version_id, chunk.chunk_id)))
    # Local ID resolved from the requirement record, never guessed from text.
    assert lookup.evidence.citation.label == (
        "payments.md — § Requirements / REQ-001 [REQ-001]"
    )
    assert lookup.evidence.requirement_id == requirement_id