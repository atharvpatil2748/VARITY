"""V6 acceptance (roadmap 04, step V6): document/source routes over the fake
service with canonical IngestResult/Document/ListPage wire objects (contracts
05/11/16/21). Upload semantics: 201 new, 200 same bytes, 25 MiB cap, modes."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from conftest import validate_wire
from verity.http import create_app
from verity.http.app import CONTRACT_VERSION_HEADER, REQUEST_ID_HEADER

DOCUMENT_ID = "ebc2352e-ff9c-4167-b11a-1e30d550411d"
SOURCE_ID = "24da624f-7fd0-41ea-a49b-8449cbb179d9"


@pytest.fixture
def client(fake_service) -> TestClient:
    return TestClient(create_app(fake_service))


def _upload(client, content=b"# Payments spec\n", filename="payments.md", **form):
    return client.post(
        "/api/v1/documents",
        files={"file": (filename, content, "application/octet-stream")},
        data=form,
    )


def test_upload_new_source_201_canonical(schemas, wire_fixtures, client, fake_service):
    response = _upload(client)
    assert response.status_code == 201
    body = response.json()
    assert body == wire_fixtures["ingest_result"]
    validate_wire(schemas, "IngestResult", body)
    assert fake_service.call_counts["ingest_result"] == 1
    assert response.headers[CONTRACT_VERSION_HEADER] == "1.0.0"
    assert uuid.UUID(response.headers[REQUEST_ID_HEADER]).version == 4
    assert response.headers["content-type"].startswith("application/json")


def test_upload_same_bytes_200_idempotent(schemas, client):
    assert _upload(client).status_code == 201
    again = _upload(client)
    assert again.status_code == 200
    body = again.json()
    validate_wire(schemas, "IngestResult", body)
    assert body["created_new_version"] is False


def test_upload_new_bytes_201_new_version(client):
    _upload(client)
    changed = _upload(client, content=b"# Payments spec v2\n")
    assert changed.status_code == 201
    assert changed.json()["created_new_version"] is True


def test_upload_missing_file_400(schemas, client):
    response = client.post("/api/v1/documents", data={"mode": "auto"})
    assert response.status_code == 400
    validate_wire(schemas, "HttpError", response.json())
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_upload_bad_mode_400(client):
    response = _upload(client, mode="nope")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_upload_bad_source_id_400(client):
    response = _upload(client, source_id="not-a-uuid")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_upload_reingest_with_source_id_201(client):
    response = _upload(client, source_id=SOURCE_ID)
    assert response.status_code == 201
    assert response.json()["created_new_version"] is True


def test_upload_oversize_413(schemas, monkeypatch, client):
    monkeypatch.setattr("verity.http.routes.MAX_UPLOAD_BYTES", 10)
    response = _upload(client, content=b"x" * 11)
    assert response.status_code == 413
    validate_wire(schemas, "HttpError", response.json())
    assert response.json()["error"]["code"] == "LIMIT_EXCEEDED"


def test_upload_unsupported_extension_415(schemas, client):
    response = _upload(client, filename="malware.exe", content=b"xx")
    assert response.status_code == 415
    validate_wire(schemas, "HttpError", response.json())
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_list_documents_canonical(schemas, wire_fixtures, client, fake_service):
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "ListPageDocument", body)
    assert body["items"] == [wire_fixtures["document"]]
    assert (body["limit"], body["offset"], body["total"]) == (50, 0, 1)
    assert fake_service.call_counts["list_page_documents"] == 1
    paged = client.get("/api/v1/documents", params={"limit": 5, "offset": 1})
    assert (paged.json()["limit"], paged.json()["offset"]) == (5, 1)


def test_list_documents_kind_filter(client):
    spec = client.get("/api/v1/documents", params={"kind": "spec"})
    general = client.get("/api/v1/documents", params={"kind": "general"})
    assert spec.json()["total"] == 1
    assert general.json()["items"] == []
    assert general.json()["total"] == 0


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"kind": "nope"}])
def test_list_documents_bad_params_400(schemas, client, params):
    response = client.get("/api/v1/documents", params=params)
    assert response.status_code == 400
    validate_wire(schemas, "HttpError", response.json())
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_get_document_found(schemas, wire_fixtures, client):
    response = client.get(f"/api/v1/documents/{DOCUMENT_ID}")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "Document", body)
    assert body == wire_fixtures["document"]


def test_get_document_unknown_404(schemas, client):
    response = client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert response.status_code == 404
    validate_wire(schemas, "HttpError", response.json())
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_get_document_bad_uuid_400(client):
    response = client.get("/api/v1/documents/not-a-uuid")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_list_sources_canonical(schemas, wire_fixtures, client, fake_service):
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "ListPageSource", body)
    assert body["items"] == [wire_fixtures["source"]]
    assert (body["limit"], body["offset"], body["total"]) == (50, 0, 1)
    assert fake_service.call_counts["list_page_sources"] == 1


def test_list_sources_bad_offset_400(client):
    response = client.get("/api/v1/sources", params={"offset": -2})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"