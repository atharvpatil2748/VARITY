"""SDK gateway tests — PR-A5 gate (contract 10).

Gate per roadmap 02: installed Cline SDK smoke, tool parity/session/error
tests and no duplicate retrieval. The SDK smoke lives in test_sdk_smoke.py
(skipped honestly when the pinned SDK is not installed).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from verity.config import VerityConfig, WorkspaceConfig
from verity.errors import VerityError
from verity.ids import make_requirement_id
from verity.models import DocumentKind, IngestMode, IngestRequest

from sdk_ui_imports import (  # noqa: E402  (helper adds sdk-ui to sys.path)
    SdkChatGateway, FakeAgentRuntime, TOOL_INPUT_SCHEMAS, TOOL_NAMES,
    execute_tool,
)

FIXTURES = Path(__file__).parent / "fixtures" / "contracts_v1"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def service(tmp_path: Path, workspace_root: Path):
    from verity.service import build_service

    config = VerityConfig(
        data_dir=tmp_path / "data",
        source_root=tmp_path / "documents",
        database_path=tmp_path / "data" / "verity.sqlite3",
        workspaces={"demo": WorkspaceConfig(workspace_id="demo", root=workspace_root)},
    )
    return build_service(config=config)


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "demo-workspace"
    root.mkdir()
    return root


@pytest.fixture()
def gateway(service):
    return SdkChatGateway(service, runtime=FakeAgentRuntime())


# ---------------------------------------------------------------------------
# Tool parity (contract 10: identical to contract 09)
# ---------------------------------------------------------------------------


def test_tool_names_and_schemas_identical_to_mcp() -> None:
    from verity.mcp.tools import TOOL_SCHEMAS as MCP_SCHEMAS

    assert list(TOOL_NAMES) == [
        "search_evidence", "get_requirement", "get_evidence", "check_coverage"]
    assert TOOL_INPUT_SCHEMAS == MCP_SCHEMAS


# ---------------------------------------------------------------------------
# Session lifecycle and errors (PR-A5 gate)
# ---------------------------------------------------------------------------


def test_create_session_returns_canonical_session(gateway) -> None:
    session = gateway.create_session()
    assert session.schema_version == "1.0.0"
    assert session.session_id.count("-") == 4  # UUIDv4 shape
    assert session.created_at.endswith("Z")


def test_send_message_unknown_session(gateway) -> None:
    with pytest.raises(VerityError) as exc:
        gateway.send_message(str(uuid4()), "hello")
    assert exc.value.code == "SESSION_NOT_FOUND"


def test_send_message_invalid_session_or_text(gateway) -> None:
    session = gateway.create_session()
    for bad_session in ("not-a-uuid", 42, ""):
        with pytest.raises(VerityError) as exc:
            gateway.send_message(bad_session, "hello")
        assert exc.value.code == "INVALID_REQUEST"
    for bad_text in ("", "x" * 8001, None):
        with pytest.raises(VerityError) as exc:
            gateway.send_message(session.session_id, bad_text)
        assert exc.value.code == "INVALID_REQUEST"


def test_run_then_continue_one_agent_per_session(service) -> None:
    runtime = FakeAgentRuntime(default_answer="ok")
    gateway = SdkChatGateway(service, runtime=runtime)
    session = gateway.create_session()
    first = gateway.send_message(session.session_id, "first turn")
    second = gateway.send_message(session.session_id, "second turn")
    assert first.message.role == "assistant" and first.message.text == "ok"
    assert second.session_id == session.session_id


def test_unavailable_runtime_reports_sdk_unavailable(service) -> None:
    class UnavailableRuntime(FakeAgentRuntime):
        @property
        def available(self) -> bool:
            return False

    gateway = SdkChatGateway(service, runtime=UnavailableRuntime())
    with pytest.raises(VerityError) as exc:
        gateway.create_session()
    assert exc.value.code == "SDK_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Marker extraction and evidence resolution (contracts 07/10)
# ---------------------------------------------------------------------------


def test_markers_resolved_and_unresolved_flagged(service) -> None:
    # Ingest so a real evidence id exists.
    data = (FIXTURES / "payments.md").read_bytes()
    result = run(service.ingest(
        IngestRequest(source_path="payments.md", mode=IngestMode.AUTO, source_id=None),
        data))
    requirement_id = make_requirement_id(
        __import__("uuid").UUID(result.document.source_id), "REQ-001")
    requirement = run(service.get_requirement(requirement_id))
    real = requirement.evidence_id

    answer = (
        f"The spec says refunds are 30 days [[{real}]]. "
        "But this claim is unsupported [[ev_" + "a" * 64 + "]]."
    )
    runtime = FakeAgentRuntime(default_answer=answer)
    gateway = SdkChatGateway(service, runtime=runtime)
    session = gateway.create_session()
    response = gateway.send_message(session.session_id, "what is the refund window?")

    # Only the resolved marker becomes a citation/evidence entry.
    assert response.message.citations == [real]
    assert [e.evidence_id for e in response.evidence] == [real]
    # The unresolved marker stays visible in the text for the UI to flag.
    assert "ev_" + "a" * 64 in response.message.text
    # Never a fabricated label: every citation maps to resolved evidence.
    assert all(e.citation.evidence_id in response.message.citations
               for e in response.evidence)


def test_duplicate_markers_resolve_once(service) -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    result = run(service.ingest(
        IngestRequest(source_path="payments.md", mode=IngestMode.AUTO, source_id=None),
        data))
    requirement_id = make_requirement_id(
        __import__("uuid").UUID(result.document.source_id), "REQ-001")
    real = run(service.get_requirement(requirement_id)).evidence_id
    runtime = FakeAgentRuntime(default_answer=f"[[{real}]] and again [[{real}]]")
    gateway = SdkChatGateway(service, runtime=runtime)
    session = gateway.create_session()
    response = gateway.send_message(session.session_id, "q?")
    assert response.message.citations == [real]
    assert len(response.evidence) == 1


# ---------------------------------------------------------------------------
# execute_tool: delegation and structured Error data (no duplicate retrieval)
# ---------------------------------------------------------------------------


def test_execute_tool_delegates_to_service_only(service) -> None:
    calls: list[str] = []
    original = service.search_evidence

    async def spy(request):
        calls.append("search_evidence")
        return await original(request)

    service.search_evidence = spy  # type: ignore[assignment]
    result = run(execute_tool(service, "search_evidence", {"query": "refund window"}))
    assert calls == ["search_evidence"]  # exactly one service call per tool
    assert "items" in result and result["schema_version"] == "1.0.0"


def test_execute_tool_returns_structured_error_data(service) -> None:
    out = run(execute_tool(service, "get_requirement",
                           {"requirement_id": "req_" + "9" * 64}))
    assert out["code"] == "REQUIREMENT_NOT_FOUND"
    assert out["schema_version"] == "1.0.0"
    bad = run(execute_tool(service, "get_requirement", {"requirement_id": "nope"}))
    assert bad["code"] == "INVALID_REQUEST"
    unknown = run(execute_tool(service, "compare_sources", {}))
    assert unknown["code"] == "INVALID_REQUEST"  # no fifth tool in v1