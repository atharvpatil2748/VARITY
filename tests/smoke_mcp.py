"""V0 smoke test for the MCP SDK + VERITY MCP scaffold (fully offline).

Validates, on this exact machine:
  1. installed mcp version + structuredContent support
  2. in-memory client<->server session: initialize, tools/list, tools/call
     success, dual-payload parity, in-band error results
  3. REAL stdio subprocess round-trip: spawn ``python -m verity.mcp`` as a
     child process exactly the way Cline would, then call a tool over pipes.

Run from repo root:  python tests/smoke_mcp.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # make the verity package importable

import mcp.types as types  # noqa: E402
from mcp.client.session import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402
from mcp.shared.memory import create_client_server_memory_streams  # noqa: E402

from verity.mcp.server import build_server  # noqa: E402

_RESULTS: list[tuple[str, bool]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    _RESULTS.append((label, ok))
    status = "PASS" if ok else "FAIL"
    suffix = f"  -- {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")


async def in_memory_test() -> None:
    print("\nTest 1: in-memory session (no subprocess)")
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        server = build_server()
        options = server.create_initialization_options()
        server_task = asyncio.create_task(server.run(*server_streams, options))
        try:
            # mcp 2.x: ClientSession MUST be entered as an async context manager
            async with ClientSession(*client_streams) as client:
                init = await client.initialize()
                check(
                    "initialize handshake",
                    bool(init.protocol_version),
                    f"protocol={init.protocol_version} server={init.server_info.name}",
                )

                tools = await client.list_tools()
                names = [t.name for t in tools.tools]
                check("tools/list returns echo + fail", names == ["echo", "fail"], f"got {names}")
                check(
                    "echo tool advertises inputSchema",
                    tools.tools[0].input_schema.get("required") == ["text"],
                )

                result = await client.call_tool("echo", {"text": "verity-v0-smoke"})
                sc = result.structured_content
                check("structuredContent present & correct", isinstance(sc, dict) and sc.get("echo") == "verity-v0-smoke", str(sc))
                text = result.content[0].text if result.content else ""
                check("text fallback is identical JSON", json.loads(text) == sc)
                check("success result is_error=False", result.is_error is False)

                err = await client.call_tool("fail", {})
                check("error result is_error=True", err.is_error is True)
                check(
                    "error carries canonical code",
                    isinstance(err.structured_content, dict)
                    and err.structured_content.get("code") == "INVALID_REQUEST",
                    str(err.structured_content),
                )
                check(
                    "error text parity",
                    json.loads(err.content[0].text) == err.structured_content,
                )
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass


async def stdio_subprocess_test() -> None:
    print("\nTest 2: REAL stdio subprocess (spawned like Cline would)")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "verity.mcp"],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as streams:
        read, write = streams
        async with ClientSession(read, write) as client:
            init = await client.initialize()
            check(
                "subprocess initialize handshake",
                init.server_info.name == "verity-mcp",
                f"server={init.server_info.name} v{init.server_info.version}",
            )

            tools = await client.list_tools()
            names = [t.name for t in tools.tools]
            check("subprocess tools/list", names == ["echo", "fail"], f"got {names}")

            result = await client.call_tool("echo", {"text": "over-real-pipes"})
            sc = result.structured_content
            check(
                "subprocess tools/call structuredContent",
                isinstance(sc, dict) and sc.get("echo") == "over-real-pipes",
                str(sc),
            )
            check("subprocess dual-payload parity", json.loads(result.content[0].text) == sc)
            check("subprocess success is_error=False", result.is_error is False)


async def main_async() -> None:
    print(f"mcp SDK version: {pkg_version('mcp')}")
    fields = list(types.CallToolResult.model_fields)
    check("CallToolResult supports structured_content", "structured_content" in fields, str(fields))

    await in_memory_test()
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