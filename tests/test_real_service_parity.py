"""PR-V3 real-binding tests: MCP/HTTP parity and restart proof (roadmap 08).

Gate: "MCP/HTTP real-service parity and restart tests". Binds ONE real
``build_service()`` instance to BOTH transports and asserts the canonical
payload is identical across the MCP stdio tool and the /api/v1 route; then
rebuilds the service (fresh instance, fresh SQLite connection - the
in-process equivalent of a server restart) and proves IDs resolve to
byte-identical canonical payloads. Skips until ``verity.service`` exists.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("verity.service") is None,
    reason="verity.service (PR-A4) not merged yet",
)

from conftest import validate_wire  # noqa: E402
from test_mcp_server import call_tools  # noqa: E402
from verity.config import VerityConfig, WorkspaceConfig  # noqa: E402
from verity.http import create_app  # noqa: E402
from verity.ids import make_requirement_id  # noqa: E402
from verity.mcp.server import build_server  # noqa: E402
from verity.models import IngestMode, IngestRequest  # noqa: E402
from verity.service import build_service  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "contracts_v1"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def config(tmp_path: Path) -> VerityConfig:
    return VerityConfig(
        data_dir=tmp_path / "data",
        source_root=tmp_path / "documents",
        database_path=tmp_path / "data" / "verity.sqlite3",
        workspaces={"demo": WorkspaceConfig(workspace_id="demo", root=tmp_path)},
    )


@pytest.fixture()
def seeded_service(config: VerityConfig):
    """Real service with the canonical payments spec ingested (REQ-001)."""

    service = build_service(config=config)
    result = run(
        service.ingest(
            IngestRequest(source_path="payments.md", mode=IngestMode.AUTO),
            (FIXTURES / "payments.md").read_bytes(),
        )
    )
    assert result.created_new_version is True
    return service


def _source_id(service) -> str:
    page = run(service.list_documents(1, 0, None))
    return page.items[0].source_id


def _requirement_id(service) -> str:
    return make_requirement_id(UUID(_source_id(service)), "REQ-001")


def test_mcp_http_search_parity(schemas, seeded_service):
    mcp_result = call_tools(build_server(seeded_service), [("search_evidence", {"query": "refund window"})])[0]
    assert mcp_result.is_error is False
    mcp_payload = mcp_result.structured_content
    http_payload = TestClient(create_app(seeded_service)).post(
        "/api/v1/search", json={"query": "refund window"}
    ).json()
    assert http_payload == mcp_payload
    validate_wire(schemas, "SearchResult", mcp_payload)
    assert mcp_payload["total_returned"] >= 1


def test_mcp_http_requirement_evidence_parity(schemas, seeded_service):
    requirement_id = _requirement_id(seeded_service)
    mcp_req = call_tools(
        build_server(seeded_service), [("get_requirement", {"requirement_id": requirement_id})]
    )[0].structured_content
    client = TestClient(create_app(seeded_service))
    http_req = client.get(f"/api/v1/requirements/{requirement_id}").json()
    assert http_req == mcp_req
    validate_wire(schemas, "Requirement", mcp_req)

    evidence_id = mcp_req["evidence_id"]
    mcp_ev = call_tools(
        build_server(seeded_service), [("get_evidence", {"evidence_id": evidence_id})]
    )[0].structured_content
    http_ev = client.get(f"/api/v1/evidence/{evidence_id}").json()
    assert http_ev == mcp_ev
    validate_wire(schemas, "EvidenceLookup", mcp_ev)
    assert mcp_ev["evidence"]["score"] is None


def test_mcp_http_coverage_parity(schemas, seeded_service):
    # Coverage runs are immutable once persisted: the MCP tool creates the
    # run, then the HTTP GET /coverage/{id} route must return the identical
    # stored canonical CoverageResult - true cross-transport parity.
    requirement_id = _requirement_id(seeded_service)
    mcp_cov = call_tools(
        build_server(seeded_service),
        [("check_coverage", {"requirement_ids": [requirement_id], "workspace_id": "demo"})],
    )[0].structured_content
    validate_wire(schemas, "CoverageResult", mcp_cov)
    stored = TestClient(create_app(seeded_service)).get(
        f"/api/v1/coverage/{mcp_cov['coverage_id']}"
    ).json()
    assert stored == mcp_cov


def test_restart_ids_resolve_identically(schemas, seeded_service, config):
    """Restart proof: a fresh build_service() on the same DB resolves the
    same IDs (requirement/document) to byte-identical payloads, and
    deterministic lexical search returns the same canonical result."""

    requirement_id = _requirement_id(seeded_service)
    document_id = run(seeded_service.list_documents(1, 0, None)).items[0].document_id

    before_req = call_tools(
        build_server(seeded_service), [("get_requirement", {"requirement_id": requirement_id})]
    )[0].structured_content
    before_search = call_tools(
        build_server(seeded_service), [("search_evidence", {"query": "refund window"})]
    )[0].structured_content
    before_doc = run(seeded_service.get_document(document_id)).to_dict()

    # "Restart": drop the instance (and its SQLite connection), rebuild.
    restarted = build_service(config=config)

    after_req = call_tools(
        build_server(restarted), [("get_requirement", {"requirement_id": requirement_id})]
    )[0].structured_content
    after_search = call_tools(
        build_server(restarted), [("search_evidence", {"query": "refund window"})]
    )[0].structured_content
    after_doc = run(restarted.get_document(document_id)).to_dict()

    assert after_req == before_req
    assert after_search == before_search
    assert after_doc == before_doc
    validate_wire(schemas, "Requirement", after_req)
    validate_wire(schemas, "SearchResult", after_search)