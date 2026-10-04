"""V7 acceptance (roadmap 04, step V7): search/evidence/coverage routes over
the fake service with canonical wire objects, contract-11 statuses and the
deadline/crash guarantees (contracts 07/11/16/17/21)."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from conftest import validate_wire
from fakes.fake_verity_service import FakeVerityService
from verity.http import create_app

REQ_ID = "req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2"
EV_ID = "ev_0a9948f2aa8b8cc5e499ef43626c5847eeab8df548ba5961e38a9a1126e4dc8e"
COVERAGE_ID = "c3ddf6fc-feba-4489-a8c1-129d97312b6b"
BAD_REQ_ID = "req_" + "f" * 64


@pytest.fixture
def client(fake_service) -> TestClient:
    return TestClient(create_app(fake_service))


def test_search_canonical(schemas, wire_fixtures, client, fake_service):
    response = client.post("/api/v1/search", json={"query": "refund window"})
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "SearchResult", body)
    assert body == wire_fixtures["search_result"]
    assert fake_service.call_counts["search_result"] == 1


@pytest.mark.parametrize(
    "payload",
    [{}, {"query": "x"}, {"query": "ok", "extra": 1}, {"query": "ok", "limit": 21}],
)
def test_search_invalid_400(schemas, client, payload):
    response = client.post("/api/v1/search", json=payload)
    assert response.status_code == 400
    validate_wire(schemas, "HttpError", response.json())
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_search_malformed_json_400(client):
    response = client.post("/api/v1/search", content=b"{not json", headers={"content-type": "application/json"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_get_requirement_found(schemas, wire_fixtures, client):
    response = client.get(f"/api/v1/requirements/{REQ_ID}")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "Requirement", body)
    assert body == wire_fixtures["requirement"]


def test_get_requirement_bad_pattern_400(client):
    response = client.get("/api/v1/requirements/REQ_123")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_get_requirement_unknown_404(schemas, client):
    response = client.get(f"/api/v1/requirements/{BAD_REQ_ID}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REQUIREMENT_NOT_FOUND"


def test_get_evidence_found(schemas, wire_fixtures, client):
    response = client.get(f"/api/v1/evidence/{EV_ID}")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "EvidenceLookup", body)
    assert body == wire_fixtures["evidence_lookup"]
    assert body["evidence"]["score"] is None


def test_get_evidence_context_bounds(schemas, client):
    ok = client.get(f"/api/v1/evidence/{EV_ID}", params={"context_chars": 4000})
    bad_high = client.get(f"/api/v1/evidence/{EV_ID}", params={"context_chars": 4001})
    assert ok.status_code == 200
    assert bad_high.status_code == 400
    assert bad_high.json()["error"]["code"] == "INVALID_REQUEST"


def test_get_evidence_unknown_404(schemas, client):
    response = client.get(f"/api/v1/evidence/ev_{'a' * 64}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"


def test_coverage_canonical(schemas, wire_fixtures, client, fake_service):
    response = client.post("/api/v1/coverage", json={"requirement_ids": [REQ_ID], "workspace_id": "demo"})
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "CoverageResult", body)
    assert body == wire_fixtures["coverage_result"]
    assert fake_service.call_counts["coverage_result"] == 1


def test_coverage_unknown_requirement_404(schemas, client):
    response = client.post("/api/v1/coverage", json={"requirement_ids": [BAD_REQ_ID], "workspace_id": "demo"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REQUIREMENT_NOT_FOUND"


def test_coverage_unknown_workspace_404(schemas, client):
    response = client.post("/api/v1/coverage", json={"requirement_ids": [REQ_ID], "workspace_id": "nope"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"


def test_coverage_invalid_body_400(client):
    response = client.post("/api/v1/coverage", json={"requirement_ids": [REQ_ID]})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_get_coverage_stored_run(schemas, wire_fixtures, client):
    response = client.get(f"/api/v1/coverage/{COVERAGE_ID}")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "CoverageResult", body)
    assert body == wire_fixtures["coverage_result"]


def test_get_coverage_unknown_404(schemas, client):
    response = client.get(f"/api/v1/coverage/{COVERAGE_ID[:-1]}a")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "COVERAGE_NOT_FOUND"


def test_get_coverage_bad_uuid_400(client):
    response = client.get("/api/v1/coverage/not-a-uuid")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_route_timeout_504(wire_fixtures):
    class SlowFake(FakeVerityService):
        async def search_evidence(self, request):
            await asyncio.sleep(0.5)
            return await super().search_evidence(request)

    app = create_app(SlowFake(wire_fixtures), deadlines={"search": 0.05})
    response = TestClient(app).post("/api/v1/search", json={"query": "refund window"})
    assert response.status_code == 504
    payload = response.json()
    assert payload["error"]["code"] == "TIMEOUT"
    assert payload["error"]["retryable"] is True


def test_route_crash_sanitized_500(wire_fixtures):
    class ExplodingFake(FakeVerityService):
        async def get_requirement(self, requirement_id):
            raise RuntimeError("secret /home/user/creds")

    response = TestClient(create_app(ExplodingFake(wire_fixtures)), raise_server_exceptions=False).get(
        f"/api/v1/requirements/{REQ_ID}"
    )
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in json.dumps(payload)
    assert "RuntimeError" not in json.dumps(payload)