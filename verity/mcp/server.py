"""V0 SMOKE SCAFFOLD — VERITY MCP stdio server.

This module is deliberately minimal: it exists only to validate the installed
MCP SDK (mcp 2.3.0) on this machine *before* the real V2–V4 implementation
lands (real tools per Docs/contracts/09_VERITY_MCP_CONTRACT.md).

It already follows the frozen transport rules:

* stdout carries ONLY JSON-RPC frames; all logs go to stderr.
* Tool replies are dual-payload: ``structuredContent`` and the JSON text
  block carry byte-identical JSON.
* Errors are returned as canonical in-band results with ``is_error=True``.

Run with:  python -m verity.mcp
"""

from __future__ import annotations

import json
import logging
import sys

import anyio
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

log = logging.getLogger("verity.mcp")

_SCHEMA_VERSION = "1.0.0"  # smoke placeholder; real envelope comes from contract 21

_ECHO_INPUT_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text"],
    "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 1000}},
}

_FAIL_INPUT_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {},
}


def _dual_result(payload: dict) -> types.CallToolResult:
    """Wrap a dict as the contract's dual payload (structuredContent == JSON text)."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structured_content=payload,
        is_error=False,
    )


def _error_result(code: str, message: str) -> types.CallToolResult:
    payload = {"schema_version": _SCHEMA_VERSION, "code": code, "message": message}
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structured_content=payload,
        is_error=True,
    )


def build_server() -> Server:
    """Build a Server with two dummy tools (echo / fail) for smoke testing."""

    async def on_list_tools(ctx, params) -> types.ListToolsResult:  # noqa: ANN001
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name="echo",
                    description="V0 smoke tool: echoes text back in dual format.",
                    input_schema=_ECHO_INPUT_SCHEMA,
                ),
                types.Tool(
                    name="fail",
                    description="V0 smoke tool: always returns a canonical error result.",
                    input_schema=_FAIL_INPUT_SCHEMA,
                ),
            ]
        )

    async def on_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        args = dict(params.arguments or {})
        if name == "echo":
            return _dual_result({"schema_version": _SCHEMA_VERSION, "echo": args.get("text", "")})
        if name == "fail":
            return _error_result("INVALID_REQUEST", "V0 smoke failure requested by caller")
        return _error_result("INVALID_REQUEST", f"unknown tool: {name}")

    # mcp 2.x registers handlers via constructor hooks (old @server decorators are gone).
    server = Server(name="verity-mcp", version="0.0.0", on_list_tools=on_list_tools, on_call_tool=on_call_tool)
    return server


async def _run_stdio() -> None:
    server = build_server()
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main() -> None:
    """Entrypoint: serve MCP over stdio. Logs go to stderr ONLY."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("verity-mcp (V0 smoke scaffold) starting on stdio")
    anyio.run(_run_stdio)


if __name__ == "__main__":
    main()