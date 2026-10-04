"""V9 real-binding preparation (roadmap 04, PR-V3 gate prep).

These tests SKIP entirely until the real VerityService lands (PR-A4:
``verity.service.build_service``). Once importable they validate the real
service's contract-16 surface and error discipline against the live
contract-21 $defs - the same drift-proof harness the fixture tests use, and
the integration check Atharv accepted at PR-V3 review. They need no
ingested data: not-found paths, strict validation failures and canonical
empty-result shapes are exercised on an empty database.
"""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from pathlib import Path

import pytest

from conftest import validate_wire
from verity.errors import VerityError
from verity.mcp.tools import parse_search_args

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("verity.service") is None,
    reason="verity.service (PR-A4) not merged yet; transport runs on FakeVerityService",
)

BAD_REQ_ID = "req_" + "f" * 64
BAD_EV_ID = "ev_" + "a" * 64

_SURFACE = (
    "search_evidence",
    "get_requirement",
    "get_evidence",
    "check_coverage",
    "ingest",
    "get_document",
    "list_documents",
    "list_sources",
    "get_coverage",
)


def run(coro):
    return asyncio.run(coro)


def to_wire(result):
    to_dict = getattr(result, "to_dict", None)
    return to_dict() if callable(to_dict) else result


@pytest.fixture(scope="module")
def real_service():
    from verity.service import build_service

    # Always run against an isolated temp config: hermetic tests must not
    # write into the repo-local ./data database (which the V10 demo seeds).
    import tempfile

    from verity.config import VerityConfig, WorkspaceConfig

    tmp = Path(tempfile.mkdtemp(prefix="verity-v9-"))
    data_dir = tmp / "data"
    documents = tmp / "documents"
    data_dir.mkdir()
    documents.mkdir()
    config = VerityConfig(
        data_dir=data_dir,
        source_root=documents,
        database_path=data_dir / "verity.sqlite3",
        workspaces={"demo": WorkspaceConfig(workspace_id="demo", root=tmp)},
    )
    return build_service(config=config)


def test_build_service_zero_arg_constructs():
    """The frozen zero-arg factory works from this checkout (the demo
    workspace root is present per contract 14); construction only."""

    from verity.service import build_service

    service = build_service()
    assert callable(getattr(service, "search_evidence", None))


def test_build_service_exposes_contract16_surface(real_service):
    missing = [name for name in _SURFACE if not callable(getattr(real_service, name, None))]
    assert not missing, f"real service is missing contract-16 methods: {missing}"


def test_no_match_search_is_canonical_success(schemas, real_service):
    # "zz-no-match" is the suite-wide no-match sentinel: the real service
    # returns an empty SearchResult for it (contract 09), never an error.
    request = parse_search_args({"query": "zz-no-match"})
    payload = to_wire(run(real_service.search_evidence(request)))
    validate_wire(schemas, "SearchResult", payload)
    assert payload["items"] == []


def test_invalid_query_rejected(real_service):
    with pytest.raises(VerityError) as excinfo:
        run(real_service.search_evidence(parse_search_args({"query": "x"})))
    assert excinfo.value.code == "INVALID_REQUEST"


def test_malformed_requirement_id_rejected(real_service):
    with pytest.raises(VerityError) as excinfo:
        run(real_service.get_requirement("REQ_123"))
    assert excinfo.value.code == "INVALID_REQUEST"


def test_unknown_requirement_not_found(real_service):
    with pytest.raises(VerityError) as excinfo:
        run(real_service.get_requirement(BAD_REQ_ID))
    assert excinfo.value.code == "REQUIREMENT_NOT_FOUND"
    assert excinfo.value.retryable is False


def test_unknown_evidence_not_found(real_service):
    with pytest.raises(VerityError) as excinfo:
        run(real_service.get_evidence(BAD_EV_ID, 1000))
    assert excinfo.value.code == "EVIDENCE_NOT_FOUND"


def test_unknown_document_not_found(real_service):
    with pytest.raises(VerityError) as excinfo:
        run(real_service.get_document(str(uuid.uuid4())))
    assert excinfo.value.code == "DOCUMENT_NOT_FOUND"


def test_unknown_coverage_run_not_found(schemas, real_service):
    with pytest.raises(VerityError) as excinfo:
        run(real_service.get_coverage(str(uuid.uuid4())))
    assert excinfo.value.code == "COVERAGE_NOT_FOUND"


def test_list_documents_canonical(schemas, real_service):
    payload = to_wire(run(real_service.list_documents(10, 0, None)))
    validate_wire(schemas, "ListPageDocument", payload)


def test_list_sources_canonical(schemas, real_service):
    payload = to_wire(run(real_service.list_sources(10, 0)))
    validate_wire(schemas, "ListPageSource", payload)


def test_unknown_workspace_not_found(real_service):
    from verity.mcp.tools import parse_check_coverage_args

    request = parse_check_coverage_args({"requirement_ids": [BAD_REQ_ID], "workspace_id": "no-such"})
    with pytest.raises(VerityError) as excinfo:
        run(real_service.check_coverage(request))
    assert excinfo.value.code == "WORKSPACE_NOT_FOUND"


def test_ingest_happy_path_when_pipeline_available(schemas, real_service):
    from verity.models import IngestMode, IngestRequest

    request = IngestRequest(source_path="uploads/real-binding-probe.md", mode=IngestMode.GENERAL)
    try:
        payload = to_wire(run(real_service.ingest(request, b"# Probe\n\nRefund window text for V9.\n")))
    except VerityError as err:
        if err.code in ("UNSUPPORTED_FORMAT", "PARSER_ERROR", "SPEC_VALIDATION_ERROR"):
            pytest.skip(f"ingestion pipeline not fully available yet: {err.code}")
        raise
    validate_wire(schemas, "IngestResult", payload)