"""V8 acceptance (roadmap 04, step V8): chat routes. No gateway configured is
a truthful 503 SDK_UNAVAILABLE (contract 10); with a gateway duck-type the
routes validate ChatInput/ChatSession shapes and delegate once - the HTTP
adapter never builds its own agent (contracts 10/11/17/21)."""

from __future__ import annotations

import copy
import uuid

import pytest
from fastapi.testclient import TestClient

from conftest import validate_wire
from verity.errors import VerityError
from verity.http import create_app

SESSION_ID = "b1e4a2c3-9d48-4e2a-8f6b-3c1d5e7a9b0f"
MESSAGES = "/api/v1/chat/sessions/{session_id}/messages"


class FakeGateway:
    """Provisional SDK-gateway duck-type (contract 10 discovery lands in PR-A5)."""

    def __init__(self, fixtures: dict) -> None:
        self._fixtures = fixtures
        self.calls: list = []

    def create_session(self) -> dict:
        self.calls.append("create_session")
        return copy.deepcopy(self._fixtures["chat_session"])

    def send_message(self, session_id: str, text: str) -> dict:
        self.calls.append(("send_message", session_id, text))
        if session_id != self._fixtures["chat_session"]["session_id"]:
            raise VerityError("SESSION_NOT_FOUND", "No chat session matches the given session ID.")
        return copy.deepcopy(self._fixtures["chat_response"])


@pytest.fixture
def plain_client(fake_service) -> TestClient:
    return TestClient(create_app(fake_service))


@pytest.fixture
def gateway_client(wire_fixtures, fake_service) -> tuple[TestClient, FakeGateway]:
    gateway = FakeGateway(wire_fixtures)
    return TestClient(create_app(fake_service, gateway=gateway)), gateway


def test_sessions_unavailable_503(schemas, plain_client):
    response = plain_client.post("/api/v1/chat/sessions", json={})
    assert response.status_code == 503
    body = response.json()
    validate_wire(schemas, "HttpError", body)
    assert body["error"]["code"] == "SDK_UNAVAILABLE"
    assert body["error"]["retryable"] is True


def test_messages_unavailable_503(schemas, plain_client):
    response = plain_client.post(MESSAGES.format(session_id=SESSION_ID), json={"text": "hello"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SDK_UNAVAILABLE"


def test_messages_bad_session_uuid_400_before_gateway_check(plain_client):
    response = plain_client.post(MESSAGES.format(session_id="nope"), json={"text": "hello"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_sessions_nonempty_body_400(plain_client):
    response = plain_client.post("/api/v1/chat/sessions", json={"unexpected": 1})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_sessions_with_gateway_201_canonical(schemas, gateway_client):
    client, gateway = gateway_client
    response = client.post("/api/v1/chat/sessions", json={})
    assert response.status_code == 201
    body = response.json()
    validate_wire(schemas, "ChatSession", body)
    assert gateway.calls == ["create_session"]
    assert response.headers["content-type"].startswith("application/json")


def test_messages_with_gateway_200_canonical(schemas, wire_fixtures, gateway_client):
    client, gateway = gateway_client
    response = client.post(MESSAGES.format(session_id=SESSION_ID), json={"text": "What is the refund window?"})
    assert response.status_code == 200
    body = response.json()
    validate_wire(schemas, "ChatResponse", body)
    assert body == wire_fixtures["chat_response"]
    assert gateway.calls == [("send_message", SESSION_ID, "What is the refund window?")]


def test_messages_unknown_session_404(schemas, gateway_client):
    client, _ = gateway_client
    response = client.post(MESSAGES.format(session_id=str(uuid.uuid4())), json={"text": "hello"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.parametrize(
    "payload",
    [{"text": ""}, {"text": "x" * 8001}, {"text": "ok", "extra": 1}, {}],
)
def test_messages_invalid_input_400(gateway_client, payload):
    client, _ = gateway_client
    response = client.post(MESSAGES.format(session_id=SESSION_ID), json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"