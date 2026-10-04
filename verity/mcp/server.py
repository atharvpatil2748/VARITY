"""VERITY MCP stdio server (roadmap V2 + V4).

Contract: Docs/contracts/09_VERITY_MCP_CONTRACT.md (four frozen tools, exact
input schemas, deadlines, dual payload, stdout discipline), 16 (VerityService
surface), 17 (canonical Error mapping). The server owns registration,
validation dispatch, one service call per tool, per-tool deadlines and
serialization only - no SQL, retrieval, citation formatting or coverage
evaluation ever happens in a tool handler.

stdout carries ONLY JSON-RPC frames; every log line goes to stderr.
Run with: python -m verity.mcp
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from collections.abc import Mapping
from typing import Any

import anyio
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from verity.errors import VerityError
from verity.models import VerityModel
from verity.mcp.tools import (
    TOOL_DESCRIPTIONS,
    TOOL_NAMES,
    TOOL_SCHEMAS,
    parse_check_coverage_args,
    parse_get_evidence_args,
    parse_get_requirement_args,
    parse_search_args,
)

log = logging.getLogger("verity.mcp")

SERVER_NAME = "verity-mcp"
SERVER_VERSION = "1.0.0"

#: Frozen per-tool deadlines in seconds (contract 09).
CONTRACT_DEADLINES: dict[str, float] = {
    "search_evidence": 15.0,
    "get_requirement": 5.0,
    "get_evidence": 5.0,
    "check_coverage": 30.0,
}

_SERVICE_METHODS = ("search_evidence", "get_requirement", "get_evidence", "check_coverage")


def _dump(payload: dict[str, Any]) -> str:
    """Canonical compact JSON used for the text twin of structuredContent."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _to_wire(result: Any) -> dict[str, Any]:
    """Serialize a service result (canonical model or plain dict) to wire form."""
    if isinstance(result, VerityModel):
        return result.to_dict()
    if isinstance(result, dict):
        return dict(result)
    raise VerityError("INTERNAL_ERROR", "service returned an unsupported result type")


def _success(payload: dict[str, Any]) -> types.CallToolResult:
    """Dual payload: structuredContent and the identical compact JSON text."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=_dump(payload))],
        structured_content=payload,
        is_error=False,
    )


def _error_result(err: VerityError, request_id: str) -> types.CallToolResult:
    """Canonical in-band Error (contract 03/17) with ``is_error=True``."""
    payload = err.to_dict(request_id)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=_dump(payload))],
        structured_content=payload,
        is_error=True,
    )


async def _with_deadline(tool: str, deadline: float, call: Any) -> Any:
    """Await ``call()`` under the tool's deadline; map overrun to TIMEOUT."""
    with anyio.move_on_after(deadline) as scope:
        return await call()
    raise VerityError(
        "TIMEOUT",
        f"{tool} exceeded its {deadline:g} s deadline",
        {"tool": tool},
    )


def build_server(service: Any, deadlines: Mapping[str, float] | None = None) -> Server:
    """Build the four-tool MCP server bound to a VerityService-like object.

    ``service`` must expose the contract-16 surface (search_evidence,
    get_requirement, get_evidence, check_coverage). ``deadlines`` may override
    per-tool seconds for tests only; production always uses the frozen
    contract-09 values.
    """
    missing = [m for m in _SERVICE_METHODS if not callable(getattr(service, m, None))]
    if missing:
        raise ValueError(
            f"service does not satisfy the VerityService surface (contract 16); missing: {missing}"
        )
    dl = dict(CONTRACT_DEADLINES)
    if deadlines is not None:
        unknown = set(deadlines) - set(CONTRACT_DEADLINES)
        if unknown:
            raise ValueError(f"unknown deadline overrides: {sorted(unknown)}")
        dl.update(deadlines)

    async def on_list_tools(ctx, params) -> types.ListToolsResult:  # noqa: ANN001
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=name,
                    description=TOOL_DESCRIPTIONS[name],
                    input_schema=TOOL_SCHEMAS[name],
                )
                for name in TOOL_NAMES
            ]
        )

    async def on_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        args = params.arguments or {}
        request_id = str(uuid.uuid4())
        if name not in TOOL_NAMES:
            return _error_result(
                VerityError("INVALID_REQUEST", f"unknown tool: {name}", {"tool": name}), request_id
            )
        try:
            if name == "search_evidence":
                request = parse_search_args(args)
                payload = _to_wire(await _with_deadline(name, dl[name], lambda: service.search_evidence(request)))
            elif name == "get_requirement":
                requirement_id = parse_get_requirement_args(args)
                payload = _to_wire(await _with_deadline(name, dl[name], lambda: service.get_requirement(requirement_id)))
            elif name == "get_evidence":
                evidence_id, context_chars = parse_get_evidence_args(args)
                payload = _to_wire(
                    await _with_deadline(name, dl[name], lambda: service.get_evidence(evidence_id, context_chars))
                )
            else:
                request = parse_check_coverage_args(args)
                payload = _to_wire(await _with_deadline(name, dl[name], lambda: service.check_coverage(request)))
        except VerityError as err:
            log.info("tool %s failed code=%s request_id=%s", name, err.code, request_id)
            return _error_result(err, request_id)
        except Exception:
            log.exception("tool %s crashed request_id=%s", name, request_id)
            # Contract 17: details never duplicates top-level Error fields, so
            # no request_id here - _error_result sets it via err.to_dict().
            return _error_result(
                VerityError("INTERNAL_ERROR", "internal server error"),
                request_id,
            )
        log.info("tool %s ok request_id=%s", name, request_id)
        return _success(payload)

    # mcp 2.x registers handlers via constructor hooks (old @server decorators are gone).
    return Server(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def _load_real_service() -> Any:
    """Load the real VerityService from core (integration point for PR-A4).

    The stdio entrypoint never silently substitutes the fake service
    (roadmap 04 waiting rules); it fails fast with a clear stderr message.
    """
    try:
        from verity.service import build_service
    except ImportError:
        log.error(
            "verity.service (real VerityService, PR-A4) is not available yet; "
            "refusing to start the stdio server on a fake service. "
            "Tests inject FakeVerityService explicitly."
        )
        raise SystemExit(2) from None
    return build_service()


async def _run_stdio(service: Any) -> None:
    server = build_server(service)
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main(service: Any | None = None) -> None:
    """Entrypoint: serve the four frozen tools over stdio. Logs -> stderr only."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if service is None:
        service = _load_real_service()
    log.info(
        "%s %s starting on stdio (mcp_transport=stdio per contract 14)",
        SERVER_NAME,
        SERVER_VERSION,
    )
    anyio.run(_run_stdio, service)


if __name__ == "__main__":
    main()