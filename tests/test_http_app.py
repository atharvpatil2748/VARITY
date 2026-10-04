"""V5 acceptance (roadmap 04, step V5): loopback /api/v1 bootstrap with
contract-11 headers, request IDs, Health ok/degraded/503 states and canonical
HttpError bodies, validated live against the frozen contract-21 $defs."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import validate_wire
from verity.errors import VerityError
from verity.http import HealthState, create_app
from verity.http.app import CONTRACT_VERSION_HEADER, REQUEST_ID_HEADER


@pytest.fixture
def client(fake_service) -> TestClient:
    return TestClient(create_app(fake_service, HealthState()))


def _assert_headers(response, request_id_is_uuid: bool = True) -> None:
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers[CONTRACT_VERSION_HEADER] == "1.0.0"
    rid = response.headers[REQUEST_ID_HEADER]
    assert isinstance(rid, str) and len(rid) == 36
    if request_id_is_uuid:
        assert uuid.UUID(rid).version == 4


def test_health_ok_canonical(schemas, client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "Health", body)
    assert body == {
        "schema_version": "1.0.0",
        "status": "ok",
        "database": "ready",
        "retrieval_mode": "hybrid",
        "sdk_available": False,
    }
    _assert_headers(response)


def test_health_request_ids_unique_per_call(client):
    first = client.get("/api/v1/health")
    second = client.get("/api/v1/health")
    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]


def test_health_degraded_200_when_retrieval_missing(schemas, fake_service):
    app = create_app(fake_service, HealthState(retrieval_mode=None))
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "Health", body)
    assert body["status"] == "degraded"
    _assert_headers(response)


def test_health_503_when_database_unavailable(schemas, fake_service):
    app = create_app(fake_service, HealthState(database_ready=False))
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 503
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    error = body["error"]
    assert error["code"] == "CONFIG_INVALID"
    assert error["retryable"] is False
    assert uuid.UUID(error["request_id"]).version == 4
    _assert_headers(response)


def test_unknown_route_is_canonical_400(schemas, client):
    response = client.get("/api/v1/zz-not-a-route")
    assert response.status_code == 400
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] == "INVALID_REQUEST"
    _assert_headers(response)


def test_unknown_method_is_canonical_400(schemas, client):
    response = client.post("/api/v1/health")
    assert response.status_code == 400
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("EVIDENCE_GONE", 410),
        ("WORKSPACE_DENIED", 403),
        ("SDK_UNAVAILABLE", 503),
        ("TIMEOUT", 504),
    ],
)
def test_verity_error_status_mapping(schemas, fake_service, code, status):
    app = create_app(fake_service)

    @app.get("/api/v1/_probe")
    async def _probe():
        raise VerityError(code, "probe failure requested by test")

    response = TestClient(app).get("/api/v1/_probe")
    assert response.status_code == status
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] == code
    assert response.headers[REQUEST_ID_HEADER] == body["error"]["request_id"]


def test_validation_error_is_canonical_400_without_input_leak(schemas, fake_service):
    app = create_app(fake_service)

    @app.get("/api/v1/_probe")
    async def _probe(digits: int):  # noqa: ANN001 - deliberate typed param
        return {"digits": digits}

    response = TestClient(app).get("/api/v1/_probe?digits=not-a-number")
    assert response.status_code == 400
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    error = body["error"]
    assert error["code"] == "INVALID_REQUEST"
    leaked = json.dumps(body)
    assert "not-a-number" not in leaked
    assert "input" not in error["details"]["errors"][0]
    assert error["details"]["errors"][0]["field"] == "query.digits"


def test_crash_is_sanitized_internal_error(schemas, fake_service):
    app = create_app(fake_service)

    @app.get("/api/v1/_probe")
    async def _probe():
        raise RuntimeError("secret /home/user/creds")

    response = TestClient(app, raise_server_exceptions=False).get("/api/v1/_probe")
    assert response.status_code == 500
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["retryable"] is True
    assert "secret" not in json.dumps(body)
    assert "RuntimeError" not in json.dumps(body)


def test_create_app_rejects_non_service():
    with pytest.raises(VerityError) as excinfo:
        create_app(object())
    assert excinfo.value.code == "INVALID_REQUEST"


def test_app_state_carries_service(fake_service):
    app = create_app(fake_service)
    assert isinstance(app, FastAPI)
    assert app.state.service is fake_service