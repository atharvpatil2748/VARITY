"""V2-V4 acceptance (roadmap 04): real four-tool MCP server over FakeVerityService.

Proves against the frozen contracts, fully offline:
  * tools/list advertises exactly the four canonical tools with the exact
    input schemas from contract 09 (parsed live from the Doc, never copied),
  * V3 parsers accept/reject in lockstep with the contract 09 schemas and
    apply the frozen defaults,
  * each tool makes exactly one service call, returns canonical results
    (validated against contract 21 $defs) in dual payload, with the frozen
    deadlines mapping overrun to TIMEOUT,
  * VerityError maps to the canonical in-band Error with a fresh request_id;
    crashes map to INTERNAL_ERROR with no internals leaked,
  * the REAL stdio subprocess path works through tests/_stdio_entry.py.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.memory import create_client_server_memory_streams

from conftest import FIXTURE_DEF_MAP, ROOT, validate_wire
from fakes.fake_verity_service import FakeVerityService
from verity.errors import VerityError
from verity.mcp import tools
from verity.mcp.server import CONTRACT_DEADLINES, SERVER_NAME, SERVER_VERSION, build_server
from verity.models import CoverageRequest, SearchRequest

REQ_ID = "req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2"
EV_ID = "ev_0a9948f2aa8b8cc5e499ef43626c5847eeab8df548ba5961e38a9a1126e4dc8e"
BAD_REQ_ID = "req_" + "f" * 64
NO_MATCH_QUERY = "zz-no-match"
FOUR_NAMES = ["check_coverage", "get_evidence", "get_requirement", "search_evidence"]

PARSERS = {
    "search_evidence": tools.parse_search_args,
    "get_requirement": tools.parse_get_requirement_args,
    "get_evidence": tools.parse_get_evidence_args,
    "check_coverage": tools.parse_check_coverage_args,
}


@pytest.fixture(scope="module")
def schema09() -> dict:
    """Exact input schemas parsed live from contract 09 (never copied)."""
    text = (ROOT / "Docs" / "contracts" / "09_VERITY_MCP_CONTRACT.md").read_text(encoding="utf-8")
    block = re.search(r"```json\s*(.*?)```", text, re.DOTALL).group(1)
    return json.loads(block)


def call_tools(server, calls):
    """Run tool calls against server in one in-memory session; return results."""

    async def _run():
        results = []
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server_task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    for name, arguments in calls:
                        results.append(await client.call_tool(name, arguments))
            finally:
                server_task.cancel()
                try:
                    await server_task
                except BaseException:
                    pass
        return results

    return asyncio.run(_run())


# --------------------------------------------------------------- registration


def test_tools_list_exact_contract_surface(fake_service, schema09):
    async def _run():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server = build_server(fake_service)
            task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    init = await client.initialize()
                    listed = await client.list_tools()
                    return init, listed
            finally:
                task.cancel()
                try:
                    await task
                except BaseException:
                    pass

    init, listed = asyncio.run(_run())
    assert init.server_info.name == SERVER_NAME == "verity-mcp"
    assert init.server_info.version == SERVER_VERSION
    assert sorted(t.name for t in listed.tools) == FOUR_NAMES
    for tool in listed.tools:
        assert tool.input_schema == schema09[tool.name] == tools.TOOL_SCHEMAS[tool.name]
        assert tool.description == tools.TOOL_DESCRIPTIONS[tool.name]


def test_contract_deadlines_frozen():
    assert CONTRACT_DEADLINES == {
        "search_evidence": 15.0,
        "get_requirement": 5.0,
        "get_evidence": 5.0,
        "check_coverage": 30.0,
    }


def test_build_server_rejects_non_services():
    with pytest.raises(ValueError):
        build_server(object())


# ---------------------------------------------------------- V3 validation


VALID_ARGS = [
    ("search_evidence", {"query": "ok"}),
    ("search_evidence", {"query": "ok", "limit": 20, "per_document_limit": 3}),
    (
        "search_evidence",
        {
            "query": "ok",
            "document_ids": ["24da624f-7fd0-41ea-a49b-8449cbb179d9"],
            "document_kinds": ["spec"],
            "chunk_kinds": ["requirement"],
        },
    ),
    ("get_requirement", {"requirement_id": REQ_ID}),
    ("get_evidence", {"evidence_id": EV_ID}),
    ("get_evidence", {"evidence_id": EV_ID, "context_chars": 4000}),
    ("check_coverage", {"requirement_ids": [REQ_ID], "workspace_id": "demo"}),
    ("check_coverage", {"requirement_ids": [REQ_ID], "workspace_id": "demo", "run_tests": True}),
]


@pytest.mark.parametrize(("tool", "arguments"), VALID_ARGS)
def test_valid_arguments_accepted_and_schema_clean(schema09, tool, arguments):
    PARSERS[tool](arguments)  # parser accepts ...
    Draft202012Validator(schema09[tool], format_checker=FormatChecker()).validate(arguments)


INVALID_ARGS = [
    ("search_evidence", []),
    ("search_evidence", {}),
    ("search_evidence", {"query": "x"}),
    ("search_evidence", {"query": "ok", "limit": 0}),
    ("search_evidence", {"query": "ok", "limit": True}),
    ("search_evidence", {"query": "ok", "per_document_limit": 0}),
    ("search_evidence", {"query": "ok", "extra": 1}),
    ("search_evidence", {"query": "ok", "document_ids": []}),
    ("search_evidence", {"query": "ok", "document_ids": ["not-a-uuid"]}),
    (
        "search_evidence",
        {"query": "ok", "document_ids": ["24da624f-7fd0-41ea-a49b-8449cbb179d9", "24da624f-7fd0-41ea-a49b-8449cbb179d9"]},
    ),
    ("search_evidence", {"query": "ok", "document_kinds": ["nope"]}),
    ("search_evidence", {"query": "ok", "chunk_kinds": ["requirement", "requirement"]}),
    ("get_requirement", {}),
    ("get_requirement", {"requirement_id": "REQ_123"}),
    ("get_requirement", {"requirement_id": "req_" + "A" * 64}),
    ("get_evidence", {"evidence_id": "ev_short"}),
    ("get_evidence", {"evidence_id": EV_ID, "context_chars": 4001}),
    ("get_evidence", {"evidence_id": EV_ID, "context_chars": -1}),
    ("check_coverage", {"workspace_id": "demo"}),
    ("check_coverage", {"requirement_ids": [], "workspace_id": "demo"}),
    ("check_coverage", {"requirement_ids": [REQ_ID, REQ_ID], "workspace_id": "demo"}),
    ("check_coverage", {"requirement_ids": [REQ_ID], "workspace_id": "Demo"}),
    ("check_coverage", {"requirement_ids": [REQ_ID], "workspace_id": "demo", "run_tests": "yes"}),
]


@pytest.mark.parametrize(("tool", "arguments"), INVALID_ARGS)
def test_invalid_arguments_rejected_like_schema(schema09, tool, arguments):
    with pytest.raises(VerityError):
        PARSERS[tool](arguments)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema09[tool], format_checker=FormatChecker()).validate(arguments)


def test_contract_defaults_applied():
    request = tools.parse_search_args({"query": "refund window"})
    assert isinstance(request, SearchRequest)
    assert request.limit == 8
    assert request.document_ids is None
    assert request.document_kinds is None
    assert request.chunk_kinds is None
    assert request.per_document_limit is None
    evidence_id, context_chars = tools.parse_get_evidence_args({"evidence_id": EV_ID})
    assert (evidence_id, context_chars) == (EV_ID, 1000)
    coverage = tools.parse_check_coverage_args({"requirement_ids": [REQ_ID], "workspace_id": "demo"})
    assert isinstance(coverage, CoverageRequest)
    assert coverage.run_tests is False


# -------------------------------------------------------------- V4 transport


@pytest.mark.parametrize(
    ("tool", "arguments", "fixture", "counter"),
    [
        ("search_evidence", {"query": "refund window"}, "search_result", "search_result"),
        ("get_requirement", {"requirement_id": REQ_ID}, "requirement", "requirement"),
        ("get_evidence", {"evidence_id": EV_ID}, "evidence_lookup", "evidence_lookup"),
        (
            "check_coverage",
            {"requirement_ids": [REQ_ID], "workspace_id": "demo"},
            "coverage_result",
            "coverage_result",
        ),
    ],
)
def test_tool_success_roundtrip(fake_service, wire_fixtures, schemas, tool, arguments, fixture, counter):
    (result,) = call_tools(build_server(fake_service), [(tool, arguments)])
    assert result.is_error is False
    payload = result.structured_content
    assert payload == wire_fixtures[fixture]
    validate_wire(schemas, FIXTURE_DEF_MAP[fixture], payload)
    assert json.loads(result.content[0].text) == payload
    assert result.content[0].text == json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    assert fake_service.call_counts[counter] == 1


def test_search_no_match_is_success_not_error(fake_service, schemas):
    (result,) = call_tools(build_server(fake_service), [("search_evidence", {"query": NO_MATCH_QUERY})])
    assert result.is_error is False
    validate_wire(schemas, "SearchResult", result.structured_content)
    assert result.structured_content["items"] == []


def test_requirement_not_found_error(fake_service, schemas):
    (result,) = call_tools(build_server(fake_service), [("get_requirement", {"requirement_id": BAD_REQ_ID})])
    assert result.is_error is True
    payload = result.structured_content
    validate_wire(schemas, "Error", payload)
    assert payload["code"] == "REQUIREMENT_NOT_FOUND"
    assert payload["retryable"] is False
    assert uuid.UUID(payload["request_id"]).version == 4
    assert json.loads(result.content[0].text) == payload


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_requirement", {"requirement_id": "not-a-req-id"}),
        ("search_evidence", {"query": "x"}),
        ("get_evidence", {"evidence_id": EV_ID, "context_chars": 4001}),
        ("check_coverage", {"requirement_ids": [REQ_ID], "workspace_id": "Demo"}),
    ],
)
def test_invalid_request_maps_to_canonical_error(fake_service, schemas, tool, arguments):
    (result,) = call_tools(build_server(fake_service), [(tool, arguments)])
    assert result.is_error is True
    payload = result.structured_content
    validate_wire(schemas, "Error", payload)
    assert payload["code"] == "INVALID_REQUEST"
    assert json.loads(result.content[0].text) == payload


def test_unknown_tool_rejected(fake_service):
    (result,) = call_tools(build_server(fake_service), [("no_such_tool", {})])
    assert result.is_error is True
    assert result.structured_content["code"] == "INVALID_REQUEST"


def test_deadline_overrun_maps_to_timeout(wire_fixtures):
    class SlowFake(FakeVerityService):
        async def get_requirement(self, requirement_id):
            await asyncio.sleep(0.5)
            return await super().get_requirement(requirement_id)

    server = build_server(SlowFake(wire_fixtures), deadlines={"get_requirement": 0.05})
    (result,) = call_tools(server, [("get_requirement", {"requirement_id": REQ_ID})])
    assert result.is_error is True
    payload = result.structured_content
    assert payload["code"] == "TIMEOUT"
    assert payload["retryable"] is True
    assert payload["details"]["tool"] == "get_requirement"


def test_crash_maps_to_internal_error_without_internals(wire_fixtures):
    class ExplodingFake(FakeVerityService):
        async def get_evidence(self, evidence_id, context_chars=1000):
            raise RuntimeError("secret traceback /home/user/creds")

    (result,) = call_tools(build_server(ExplodingFake(wire_fixtures)), [("get_evidence", {"evidence_id": EV_ID})])
    assert result.is_error is True
    payload = result.structured_content
    assert payload["code"] == "INTERNAL_ERROR"
    assert payload["retryable"] is True
    assert "secret" not in json.dumps(payload)
    assert "RuntimeError" not in json.dumps(payload)


def test_subprocess_stdio_roundtrip(wire_fixtures):
    async def _run():
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "tests" / "_stdio_entry.py")],
            cwd=str(ROOT),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                init = await client.initialize()
                listed = await client.list_tools()
                ok = await client.call_tool("search_evidence", {"query": "refund window"})
                err = await client.call_tool("get_requirement", {"requirement_id": "bad"})
                return init, listed, ok, err

    init, listed, ok, err = asyncio.run(_run())
    assert init.server_info.name == "verity-mcp"
    assert sorted(t.name for t in listed.tools) == FOUR_NAMES
    assert ok.is_error is False
    assert ok.structured_content == wire_fixtures["search_result"]
    assert json.loads(ok.content[0].text) == ok.structured_content
    assert err.is_error is True
    assert err.structured_content["code"] == "INVALID_REQUEST"