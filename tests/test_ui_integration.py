"""U6 UI integration tests (owner Vanashree): the real /api/v1 wire.

Spins the real VerityService (build_service) behind the real FastAPI app
and exercises exactly the states the UI renders: empty states, missing
resources, invalid input, contract headers for loading, navigation route
shapes, honest SDK_UNAVAILABLE chat, and no path leakage.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import validate_wire
from verity.http import HealthState, create_app

FRONTEND = Path(__file__).parent.parent / "sdk-ui" / "frontend"


@pytest.fixture(scope="module")
def client() -> TestClient:
    from verity.config import VerityConfig, WorkspaceConfig
    from verity.service import build_service

    tmp = Path(tempfile.mkdtemp(prefix="verity-u6-"))
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
    service = build_service(config=config)
    return TestClient(create_app(service, HealthState(sdk_available=False)))


def test_real_client_surface_matches_mock() -> None:
    """U6 acceptance: the real client is a drop-in for the mock client."""
    mock = (FRONTEND / "api-mock" / "client.js").read_text(encoding="utf-8")
    real = (FRONTEND / "api-client.js").read_text(encoding="utf-8")
    methods = [m for m in re.findall(r"async (\w+)\(", mock) if not m.startswith("_")]
    real_methods = {
        m for m in re.findall(r"async (\w+)\(", real) if not m.startswith("_")
    }
    missing = [m for m in methods if m not in real_methods]
    assert not missing, f"real client missing methods the views call: {missing}"


def test_app_router_selects_real_client_when_requested() -> None:
    """The ?api=real switch exists and defaults to the offline mock."""
    app_js = (FRONTEND / "views" / "app.js").read_text(encoding="utf-8")
    assert 'get("api") === "real"' in app_js
    assert "RealApiClient" in app_js and "MockApiClient" in app_js


def test_empty_documents_is_an_empty_state_not_an_error(schemas, client) -> None:
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "ListPageDocument", body)
    assert body["items"] == [] and body["total"] == 0


def test_empty_sources_is_an_empty_state_not_an_error(schemas, client) -> None:
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "ListPageSource", body)
    assert body["items"] == []


def test_missing_evidence_is_canonical_404_card(schemas, client) -> None:
    response = client.get(f"/api/v1/evidence/ev_{'a' * 64}")
    assert response.status_code == 404
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] == "EVIDENCE_NOT_FOUND"


def test_invalid_search_is_canonical_400_card(schemas, client) -> None:
    response = client.post("/api/v1/search", json={"query": " "})
    assert response.status_code == 400
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] == "INVALID_REQUEST"


def test_unknown_workspace_is_canonical_404_card(schemas, client) -> None:
    response = client.post(
        "/api/v1/coverage",
        json={"requirement_ids": [f"req_{'0' * 64}"],
              "workspace_id": "missing", "run_tests": False},
    )
    assert response.status_code == 404
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] in ("WORKSPACE_NOT_FOUND", "REQUIREMENT_NOT_FOUND")


def test_health_and_headers_support_loading_states(schemas, client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    validate_wire(schemas, "Health", response.json())
    assert response.headers["X-VERITY-Contract-Version"] == "1.0.0"
    assert len(response.headers["X-Request-ID"]) == 36


def test_chat_without_gateway_is_honest_sdk_unavailable(schemas, client) -> None:
    response = client.post("/api/v1/chat/sessions", json={})
    assert response.status_code == 503
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] == "SDK_UNAVAILABLE"


def _no_leak(value, markers) -> bool:
    if isinstance(value, str):
        return not any(m in value for m in markers)
    if isinstance(value, dict):
        return all(_no_leak(v, markers) for v in value.values())
    if isinstance(value, list):
        return all(_no_leak(v, markers) for v in value)
    return True


def test_no_absolute_path_leak_in_success_or_error_bodies(client) -> None:
    """Contract 12/14: only relative paths cross the wire."""
    leak_markers = (
        "C:", "C\\", ":\\", ":/", "/Users/", "/home/", tempfile.gettempdir(),
    )
    responses = [
        client.get("/api/v1/documents"),
        client.get("/api/v1/sources"),
        client.get(f"/api/v1/evidence/ev_{'a' * 64}"),
        client.post("/api/v1/search", json={"query": " "}),
        client.post("/api/v1/chat/sessions", json={}),
    ]
    for response in responses:
        assert _no_leak(response.json(), leak_markers), (
            f"absolute path leaked in {response.url}"
        )


def test_navigation_route_shapes_exist(client) -> None:
    """Every UI nav target answers canonical JSON on the real API."""
    for path in ("/api/v1/health", "/api/v1/documents", "/api/v1/sources"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json().get("schema_version") == "1.0.0", path