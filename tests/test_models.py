"""Focused model/error contract tests: JSON round trip, validation, nullability."""

from __future__ import annotations

import copy
import json

import pytest

from verity.errors import ERROR_CODES, VerityError
from verity.models import (
    Chunk,
    ChunkKind,
    Document,
    DocumentMetadata,
    DocumentStatus,
    Evidence,
    Error,
    IngestMode,
    IngestRequest,
    Locator,
    ParsedDocument,
    Requirement,
    SearchRequest,
    Source,
)

VERSION_ID = "129dcd06-1ba1-4f0c-bf7e-c678f905b624"
SOURCE_ID = "24da624f-7fd0-41ea-a49b-8449cbb179d9"
DOCUMENT_ID = "ebc2352e-ff9c-4167-b11a-1e30d550411d"
CHUNK_ID = "chk_71bb4eb1f7917adbd4771acd9946ee1a30994af19c4ebbf66ecd2b1e4b89b16a"
EVIDENCE_ID = "ev_0a9948f2aa8b8cc5e499ef43626c5847eeab8df548ba5961e38a9a1126e4dc8e"
REQ_ID = "req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2"

LOCATOR = {
    "source_id": SOURCE_ID,
    "document_id": DOCUMENT_ID,
    "version_id": VERSION_ID,
    "source_path": "specs/payments.md",
    "page": None,
    "start_line": 10,
    "end_line": 12,
    "start_offset": None,
    "end_offset": None,
    "heading_path": ["Requirements", "REQ-003"],
}

PROVENANCE = {
    "schema_version": "1.0.0",
    "content_sha256": "a" * 64,
    "parser_name": "markdown",
    "parser_version": "1.0.0",
    "chunker_version": "1.0.0",
    "embedding_model": None,
    "indexed_at": "2026-10-04T10:00:00Z",
}

CHUNK = {
    "schema_version": "1.0.0",
    "chunk_id": CHUNK_ID,
    "kind": "requirement",
    "text": "Refund requests MUST be accepted only within 30 days.",
    "locator": LOCATOR,
    "block_start": 0,
    "block_end": 1,
    "ordinal": 0,
    "requirement_id": REQ_ID,
}

EVIDENCE = {
    "schema_version": "1.0.0",
    "evidence_id": EVIDENCE_ID,
    "chunk_id": CHUNK_ID,
    "kind": "requirement",
    "quote": "Refund requests MUST be accepted only within 30 days.",
    "requirement_id": REQ_ID,
    "citation": {
        "evidence_id": EVIDENCE_ID,
        "label": "payments.md — § Requirements / REQ-003 [REQ-003]",
        "locator": LOCATOR,
    },
    "provenance": PROVENANCE,
    "score": 0.0317,
    "ranking": {"dense_rank": 1, "lexical_rank": 2, "rrf_score": 0.0317,
                "rerank_score": None},
}


def _source_dict() -> dict:
    return {
        "schema_version": "1.0.0",
        "source_id": SOURCE_ID,
        "source_key": "payments-api",
        "source_path": "specs/payments.md",
        "registered_at": "2026-10-04T09:00:00Z",
    }


def _document_dict() -> dict:
    return {
        "schema_version": "1.0.0",
        "document_id": DOCUMENT_ID,
        "source_id": SOURCE_ID,
        "version_id": VERSION_ID,
        "name": "payments-api.md",
        "media_type": "text/markdown",
        "kind": "spec",
        "status": "ready",
        "content_sha256": "b" * 64,
        "metadata": {
            "metadata_version": "1.0.0",
            "title": "Payments API",
            "source_key": "payments-api",
            "project": "payment-service",
            "spec_version": "1.0",
            "language": "en",
            "page_count": None,
            "parser_name": "markdown",
            "parser_version": "1.0.0",
            "warnings": [],
        },
        "indexed_at": None,
    }


def _requirement_dict() -> dict:
    return {
        "schema_version": "1.0.0",
        "requirement_id": REQ_ID,
        "local_id": "REQ-003",
        "source_id": SOURCE_ID,
        "document_id": DOCUMENT_ID,
        "version_id": VERSION_ID,
        "title": "Refund window",
        "text": "Refund requests MUST be accepted only within 30 days.",
        "chunk_id": CHUNK_ID,
        "evidence_id": EVIDENCE_ID,
        "locator": LOCATOR,
        "constraints": ["No refunds after 30 days"],
        "edge_cases": [],
        "acceptance_criteria": [],
        "api_refs": [],
        "reference_ids": [],
    }


def _roundtrip(cls, payload: dict) -> None:
    model = cls.from_dict(payload)
    assert model.to_dict() == payload


# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------


def test_source_roundtrip_and_null_key() -> None:
    _roundtrip(Source, _source_dict())
    payload = _source_dict()
    payload["source_key"] = None
    _roundtrip(Source, payload)


def test_document_roundtrip() -> None:
    _roundtrip(Document, _document_dict())


def test_requirement_roundtrip_with_defaults() -> None:
    payload = _requirement_dict()
    assert Requirement.from_dict(payload).to_dict() == payload


def test_chunk_and_evidence_roundtrip() -> None:
    _roundtrip(Chunk, CHUNK)
    _roundtrip(Evidence, EVIDENCE)


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


def test_missing_required_field_rejected() -> None:
    payload = _source_dict()
    del payload["source_path"]
    with pytest.raises(VerityError) as exc:
        Source.from_dict(payload)
    assert exc.value.code == "INVALID_REQUEST"


def test_unknown_field_rejected() -> None:
    payload = _source_dict()
    payload["extra"] = 1
    with pytest.raises(VerityError) as exc:
        Source.from_dict(payload)
    assert "unknown" in exc.value.message.lower()


def test_bad_uuid_rejected() -> None:
    payload = _source_dict()
    payload["source_id"] = "not-a-uuid"
    with pytest.raises(VerityError):
        Source.from_dict(payload)


def test_bad_schema_version_rejected() -> None:
    payload = _document_dict()
    payload["schema_version"] = "2.0.0"
    with pytest.raises(VerityError):
        Document.from_dict(payload)


def test_locator_line_pair_must_be_joint() -> None:
    payload = copy.deepcopy(LOCATOR)
    payload["end_line"] = None
    with pytest.raises(VerityError):
        Locator.from_dict(payload)


def test_search_request_bounds() -> None:
    with pytest.raises(VerityError):
        SearchRequest.from_dict({
            "query": "x", "document_ids": None,
            "document_kinds": None, "chunk_kinds": None,
        })
    with pytest.raises(VerityError):
        SearchRequest.from_dict({
            "query": "valid query", "document_ids": [],
            "document_kinds": None, "chunk_kinds": None,
        })
    with pytest.raises(VerityError):
        SearchRequest.from_dict({
            "query": "valid query", "document_ids": None,
            "document_kinds": None, "chunk_kinds": None, "limit": 21,
        })
    ok = SearchRequest.from_dict({
        "query": "valid query", "document_ids": None,
        "document_kinds": None, "chunk_kinds": None, "limit": 8,
    })
    assert ok.limit == 8


def test_parsed_document_contiguous_ordinals() -> None:
    def block(ordinal: int) -> dict:
        return {
            "ordinal": ordinal, "text": "text", "block_type": "paragraph",
            "page": None, "start_line": 1, "end_line": 1,
            "start_offset": None, "end_offset": None, "heading_path": [],
        }

    doc = {
        "metadata": _document_dict()["metadata"],
        "blocks": [block(0), block(1)],
        "media_type": "text/markdown",
        "kind": "general",
        "spec_requirements": [],
        "spec_entities": [],
    }
    parsed = ParsedDocument.from_dict(doc)
    assert [b.ordinal for b in parsed.blocks] == [0, 1]
    doc["blocks"] = [block(0), block(2)]
    with pytest.raises(VerityError):
        ParsedDocument.from_dict(doc)


def test_ingest_request_rejects_absolute_path() -> None:
    with pytest.raises(VerityError):
        IngestRequest.from_dict({"source_path": "C:/secrets/x.md",
                                 "mode": "auto", "source_id": None})
    ok = IngestRequest.from_dict({"source_path": "specs/payments.md"})
    assert ok.mode is IngestMode.AUTO


def test_error_model_shape() -> None:
    error = Error.from_dict({
        "schema_version": "1.0.0",
        "code": "DOCUMENT_NOT_FOUND",
        "message": "no such document",
        "request_id": "b4031e7a-9294-4a46-802f-43a738fdb713",
        "details": None,
        "retryable": False,
    })
    assert error.to_dict() == json.loads(json.dumps(error.to_dict()))
    with pytest.raises(VerityError):
        Error.from_dict({
            "schema_version": "1.0.0",
            "code": "NOT_A_CODE",
            "message": "x",
            "request_id": "b4031e7a-9294-4a46-802f-43a738fdb713",
            "retryable": False,
        })


def test_verity_error_defaults_and_serialization() -> None:
    err = VerityError("MODEL_UNAVAILABLE", "local model missing")
    assert err.retryable is True
    err = VerityError("DOCUMENT_NOT_FOUND", "gone")
    assert err.retryable is False
    assert err.to_dict("b4031e7a-9294-4a46-802f-43a738fdb713") == {
        "schema_version": "1.0.0",
        "code": "DOCUMENT_NOT_FOUND",
        "message": "gone",
        "details": None,
        "request_id": "b4031e7a-9294-4a46-802f-43a738fdb713",
        "retryable": False,
    }
    with pytest.raises(ValueError):
        VerityError("MADE_UP", "x")


def test_all_contract_codes_present() -> None:
    assert len(ERROR_CODES) == 23