"""Smoke test for the real VERITY MCP server (roadmap V2-V4), fully offline.

Validates on this exact machine:
  1. installed mcp version + structuredContent support,
  2. an in-memory client<->server session over FakeVerityService: initialize
     handshake, tools/list with the four frozen tools, successful tools/call
     with dual-payload parity, and canonical in-band errors,
  3. a REAL stdio subprocess round-trip through tests/_stdio_entry.py,
     spawned exactly the way an external Cline client would.

Run from repo root:  python tests/smoke_mcp.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for _p in (str(ROOT), str(TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mcp.types as types  # noqa: E402
from mcp.client.session import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402
from mcp.shared.memory import create_client_server_memory_streams  # noqa: E402

from fakes.fake_verity_service import FakeVerityService  # noqa: E402
from verity.mcp.server import build_server  # noqa: E402

REQ_ID = "req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2"
EV_ID = "ev_0a9948f2aa8b8cc5e499ef43626c5847eeab8df548ba5961e38a9a1126e4dc8e"
BAD_REQ_ID = "req_" + "f" * 64
FOUR = ["check_coverage", "get_evidence", "get_requirement", "search_evidence"]

_RESULTS: list[tuple[str, bool]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    _RESULTS.append((label, ok))
    status = "PASS" if ok else "FAIL"
    suffix = f"  -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")


def load_fixtures() -> dict:
    from conftest import FIXTURE_DEF_MAP

    fixture_dir = TESTS / "fixtures" / "v1"
    return {
        stem: json.loads((fixture_dir / f"{stem}.json").read_text(encoding="utf-8"))
        for stem in FIXTURE_DEF_MAP
    }


def parity(result) -> bool:
    """content[0].text must be the identical JSON of structuredContent."""
    return bool(result.content) and json.loads(result.content[0].text) == result.structured_content


async def in_memory_test(fixtures: dict) -> None:
    print("\nTest 1: in-memory session over FakeVerityService")
    service = FakeVerityService(fixtures)
    server = build_server(service)
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        server_task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
        try:
            async with ClientSession(*client_streams) as client:
                init = await client.initialize()
                check(
                    "initialize handshake",
                    init.server_info.name == "verity-mcp",
                    f"server={init.server_info.name} v{init.server_info.version}",
                )

                listed = await client.list_tools()
                names = sorted(t.name for t in listed.tools)
                check("tools/list returns the four frozen tools", names == FOUR, f"got {names}")

                search = await client.call_tool("search_evidence", {"query": "refund window"})
                check(
                    "search_evidence returns canonical SearchResult",
                    search.structured_content == fixtures["search_result"],
                )
                check("search_evidence dual-payload parity", parity(search))
                check("search_evidence is_error=False", search.is_error is False)
                check("search_evidence called the service once", service.call_counts["search_result"] == 1)

                empty = await client.call_tool("search_evidence", {"query": "zz-no-match"})
                check(
                    "no-match search is a success with empty items",
                    empty.is_error is False and empty.structured_content["items"] == [],
                )

                req = await client.call_tool("get_requirement", {"requirement_id": REQ_ID})
                check(
                    "get_requirement returns canonical Requirement",
                    req.structured_content == fixtures["requirement"],
                )
                check("get_requirement dual-payload parity", parity(req))

                ev = await client.call_tool("get_evidence", {"evidence_id": EV_ID})
                check(
                    "get_evidence returns canonical EvidenceLookup",
                    ev.structured_content == fixtures["evidence_lookup"],
                )
                check(
                    "get_evidence direct lookup has null score",
                    ev.structured_content["evidence"]["score"] is None,
                )

                cov = await client.call_tool(
                    "check_coverage", {"requirement_ids": [REQ_ID], "workspace_id": "demo"}
                )
                check(
                    "check_coverage returns canonical CoverageResult",
                    cov.structured_content == fixtures["coverage_result"],
                )
                check("check_coverage dual-payload parity", parity(cov))

                invalid = await client.call_tool("get_requirement", {"requirement_id": "bad"})
                check(
                    "invalid ID -> in-band INVALID_REQUEST",
                    invalid.is_error is True and invalid.structured_content["code"] == "INVALID_REQUEST",
                )
                check(
                    "error carries request_id",
                    isinstance(invalid.structured_content.get("request_id"), str)
                    and len(invalid.structured_content["request_id"]) == 36,
                )
                check("error dual-payload parity", parity(invalid))

                missing = await client.call_tool("get_requirement", {"requirement_id": BAD_REQ_ID})
                check(
                    "unknown ID -> REQUIREMENT_NOT_FOUND",
                    missing.is_error is True
                    and missing.structured_content["code"] == "REQUIREMENT_NOT_FOUND",
                )
        finally:
            server_task.cancel()
            try:
                await server_task
            except BaseException:
                pass


async def stdio_subprocess_test() -> None:
    print("\nTest 2: REAL stdio subprocess (spawned like Cline would)")
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(TESTS / "_stdio_entry.py")],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            init = await client.initialize()
            check(
                "subprocess initialize handshake",
                init.server_info.name == "verity-mcp",
                f"server={init.server_info.name} v{init.server_info.version}",
            )
            listed = await client.list_tools()
            names = sorted(t.name for t in listed.tools)
            check("subprocess tools/list", names == FOUR, f"got {names}")

            result = await client.call_tool("search_evidence", {"query": "over real pipes"})
            check(
                "subprocess tools/call structuredContent",
                result.structured_content is not None
                and result.structured_content["total_returned"] >= 1,
            )
            check("subprocess dual-payload parity", parity(result))
            check("subprocess success is_error=False", result.is_error is False)


async def main_async() -> None:
    print(f"mcp SDK version: {pkg_version('mcp')}")
    fields = list(types.CallToolResult.model_fields)
    check("CallToolResult supports structured_content", "structured_content" in fields, str(fields))

    fixtures = load_fixtures()
    await in_memory_test(fixtures)
    await stdio_subprocess_test()

    passed = sum(1 for _, ok in _RESULTS if ok)
    total = len(_RESULTS)
    print(f"\n=== SMOKE TEST: {passed}/{total} checks passed ===")
    if passed != total:
        for label, ok in _RESULTS:
            if not ok:
                print(f"  FAILED: {label}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main_async())