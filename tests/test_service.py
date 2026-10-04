"""VerityService composition tests — PR-A4 gate.

Gate per roadmap 02: real service delegation and integration test. Exercises
build_service() (the frozen zero-arg factory promised to Vandit), real
delegation across ingestion/retrieval/evidence/coverage, store-None -> typed
error translation, empty-search success semantics, and the validate_wire
integration test against contract 21 (promised at PR-A4 acceptance).
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from support import schema_check

from verity.config import VerityConfig, WorkspaceConfig
from verity.errors import VerityError
from verity.ids import make_requirement_id
from verity.models import (
    CoverageRequest,
    DocumentKind,
    IngestMode,
    IngestRequest,
    SearchRequest,
)
from verity.service import build_service

FIXTURES = Path(__file__).parent / "fixtures" / "contracts_v1"
SCHEMA = schema_check.load_schema()


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "demo-workspace"
    root.mkdir()
    return root


@pytest.fixture()
def config(tmp_path: Path, workspace_root: Path) -> VerityConfig:
    return VerityConfig(
        data_dir=tmp_path / "data",
        source_root=tmp_path / "documents",
        database_path=tmp_path / "data" / "verity.sqlite3",
        workspaces={"demo": WorkspaceConfig(workspace_id="demo", root=workspace_root)},
    )


@pytest.fixture()
def service(config):
    return build_service(config=config)


def _search(query: str, **kwargs) -> SearchRequest:
    return SearchRequest(
        query=query, document_ids=None, document_kinds=None,
        chunk_kinds=None, **kwargs)


def test_build_service_zero_arg_surface(service) -> None:
    # The frozen factory shape promised to Vandit in the PR #3 review.
    import verity.service as service_module

    assert callable(service_module.build_service)
    for name in ("ingest", "search_evidence", "get_requirement", "get_evidence",
                 "check_coverage", "get_coverage", "get_document",
                 "list_documents", "list_sources"):
        method = getattr(service, name)
        assert inspect.iscoroutinefunction(method), name
    assert isinstance(service, service_module.VerityService)


def test_ingest_search_get_round_trip(service) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    result = run(service.ingest(
        IngestRequest(source_path="payments.md", mode=IngestMode.AUTO, source_id=None),
        data))
    assert result.created_new_version is True
    assert result.document.kind is DocumentKind.SPEC

    # search_evidence: honest lexical-only until Piyush's P6-P9 stack lands.
    found = run(service.search_evidence(_search("refund window")))
    assert found.total_returned >= 1
    assert found.retrieval_mode.value == "lexical_only"
    assert found.reranker_used is False
    assert found.omissions  # truthful: semantic/rerank unavailable
    top = found.items[0]
    assert "refund" in top.quote.lower()

    # get_requirement resolves the canonical requirement the search cited.
    requirement_id = make_requirement_id(
        UUID(result.document.source_id), "REQ-001")
    requirement = run(service.get_requirement(requirement_id))
    assert requirement.local_id == "REQ-001"

    # get_evidence resolves the requirement's primary evidence.
    lookup = run(service.get_evidence(requirement.evidence_id))
    assert lookup.evidence.evidence_id == requirement.evidence_id
    # The requirement chunk's quote contains the full authored requirement.
    assert requirement.text in lookup.evidence.quote


def test_empty_search_is_success_not_error(service) -> None:
    result = run(service.search_evidence(_search("zzq-no-such-term-anywhere")))
    assert result.items == []
    assert result.total_returned == 0
    assert result.completeness.value == "empty"


def test_store_none_translated_to_typed_errors(service) -> None:
    # Commitment from the PR #3 review: None never crosses the boundary.
    with pytest.raises(VerityError) as exc:
        run(service.get_requirement("req_" + "9" * 64))
    assert exc.value.code == "REQUIREMENT_NOT_FOUND"
    assert "request_id" not in (exc.value.details or {})
    with pytest.raises(VerityError) as exc:
        run(service.get_document(uuid4()))
    assert exc.value.code == "DOCUMENT_NOT_FOUND"
    with pytest.raises(VerityError) as exc:
        run(service.get_coverage(uuid4()))
    assert exc.value.code == "COVERAGE_NOT_FOUND"
    with pytest.raises(VerityError) as exc:
        run(service.get_evidence("ev_" + "9" * 64))
    assert exc.value.code == "EVIDENCE_NOT_FOUND"


def test_check_coverage_persists_immutable_report(service, workspace_root) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    result = run(service.ingest(
        IngestRequest(source_path="payments.md", mode=IngestMode.AUTO, source_id=None),
        data))
    requirement_id = make_requirement_id(
        UUID(result.document.source_id), "REQ-001")
    coverage = run(service.check_coverage(CoverageRequest(
        requirement_ids=[requirement_id], workspace_id="demo", run_tests=False)))
    assert len(coverage.results) == 1
    # Honest UNCERTAIN until real candidate search (N3) lands.
    assert coverage.results[0].status.value == "UNCERTAIN"
    # Persisted as an immutable run, retrievable through the service.
    loaded = run(service.get_coverage(UUID(coverage.coverage_id)))
    assert loaded.to_dict() == coverage.to_dict()


def test_list_documents_and_sources(service) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    run(service.ingest(
        IngestRequest(source_path="payments.md", mode=IngestMode.AUTO, source_id=None),
        data))
    docs = run(service.list_documents(10, 0, None))
    assert docs.total == 1 and len(docs.items) == 1
    sources = run(service.list_sources(10, 0))
    assert sources.total == 1


# ---------------------------------------------------------------------------
# validate_wire integration test (promised at PR-A4 acceptance)
# ---------------------------------------------------------------------------


def test_validate_wire_real_service_outputs(service) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    result = run(service.ingest(
        IngestRequest(source_path="payments.md", mode=IngestMode.AUTO, source_id=None),
        data))
    requirement_id = make_requirement_id(
        UUID(result.document.source_id), "REQ-001")
    found = run(service.search_evidence(_search("refund window")))
    assert schema_check.validate(
        found.to_dict(), SCHEMA["$defs"]["SearchResult"], SCHEMA) == []
    requirement = run(service.get_requirement(requirement_id))
    assert schema_check.validate(
        requirement.to_dict(), SCHEMA["$defs"]["Requirement"], SCHEMA) == []
    lookup = run(service.get_evidence(requirement.evidence_id))
    assert schema_check.validate(
        lookup.to_dict(), SCHEMA["$defs"]["EvidenceLookup"], SCHEMA) == []
    coverage = run(service.check_coverage(CoverageRequest(
        requirement_ids=[requirement_id], workspace_id="demo", run_tests=False)))
    assert schema_check.validate(
        coverage.to_dict(), SCHEMA["$defs"]["CoverageResult"], SCHEMA) == []