"""VERITY /api/v1 route handlers (roadmap 04, steps V6-V8).

Contracts: 11 (frozen routes/statuses/bodies), 05 (upload limits, modes,
supported formats), 10 (chat delegates to the Cline SDK gateway; absent
gateway is a truthful SDK_UNAVAILABLE, never a fake agent), 16 (the
VerityService surface each route delegates to exactly once), 17 (error
codes/statuses), 21 ($defs for every response). The router only
validates/deserializes, delegates and serializes - no SQL, retrieval,
citation formatting, coverage evaluation or agent reasoning here.

Interpretations flagged for review in PR-V2: HTTP route deadlines mirror
the frozen MCP deadlines from contract 09 (15s search, 5s requirement/
evidence, 30s coverage) since contract 11 lists TIMEOUT errors without
numbers; upload status is 201 when the service reports created_new_version
else 200 (same-bytes idempotency, contract 05); the gateway duck-type is
provisional until contract 10's implementation discovery lands (PR-A5).
"""

from __future__ import annotations

import re
import uuid

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from verity.errors import VerityError
from verity.http.app import API_PREFIX, _to_wire
from verity.models import IngestMode, IngestRequest
from verity.mcp.tools import (
    parse_check_coverage_args,
    parse_get_evidence_args,
    parse_get_requirement_args,
    parse_search_args,
)

#: Per-route deadlines mirroring contract 09 (see module docstring).
ROUTE_DEADLINES: dict[str, float] = {
    "search": 15.0,
    "get_requirement": 5.0,
    "get_evidence": 5.0,
    "coverage": 30.0,
}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


async def _with_deadline(route: str, deadline: float, call):
    with anyio.move_on_after(deadline):
        return await call()
    raise VerityError("TIMEOUT", f"{route} exceeded its {deadline:g} s deadline", {"route": route})


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise VerityError("INVALID_REQUEST", "request body must be a JSON object") from None
    if not isinstance(body, dict):
        raise VerityError("INVALID_REQUEST", "request body must be a JSON object")
    return body


def _query_int(request: Request, name: str, default: int, low: int, high: int | None) -> int:
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise VerityError("INVALID_REQUEST", f"{name} must be an integer", {"field": name}) from None
    if value < low or (high is not None and value > high):
        raise VerityError(
            "INVALID_REQUEST",
            f"{name} must be in range {low}-{high if high is not None else 'unbounded'}",
            {"field": name},
        )
    return value


def _path_uuid(value: str, field: str) -> str:
    if not _UUID4_RE.match(value):
        raise VerityError("INVALID_REQUEST", f"{field} must be a UUIDv4", {"field": field})
    return value


def _safe_upload_name(filename: str) -> str:
    """Safe generated relative name for the upload (contract 14)."""

    stem = re.sub(r"[^A-Za-z0-9._-]", "_", filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])[:80]
    return f"uploads/{uuid.uuid4().hex}_{stem}"


def register_routes(app: FastAPI, deadlines: dict[str, float] | None = None) -> None:
    dl = dict(ROUTE_DEADLINES)
    if deadlines:
        dl.update(deadlines)

    # ------------------------------------------------------------- V6 documents

    @app.post(API_PREFIX + "/documents")
    async def upload_document(request: Request):
        service = request.app.state.service
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise VerityError("INVALID_REQUEST", "multipart field 'file' is required")
        filename = upload.filename or ""
        if not filename:
            raise VerityError("INVALID_REQUEST", "uploaded file must have a filename")
        data = await upload.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise VerityError("LIMIT_EXCEEDED", "upload exceeds the 25 MiB limit", {"size_bytes": len(data)})
        mode = str(form.get("mode", "auto"))
        if mode not in ("auto", "spec", "general"):
            raise VerityError("INVALID_REQUEST", "mode must be auto, spec or general", {"field": "mode"})
        source_id = form.get("source_id")
        if source_id is not None and not _UUID4_RE.match(str(source_id)):
            raise VerityError("INVALID_REQUEST", "source_id must be a UUIDv4", {"field": "source_id"})
        ingest_request = IngestRequest(
            source_path=_safe_upload_name(filename),
            mode=IngestMode(mode),
            source_id=str(source_id) if source_id is not None else None,
        )
        result = _to_wire(await service.ingest(ingest_request, data))
        return JSONResponse(content=result, status_code=201 if result["created_new_version"] else 200)

    @app.get(API_PREFIX + "/documents")
    async def list_documents(request: Request):
        service = request.app.state.service
        limit = _query_int(request, "limit", 50, 1, 100)
        offset = _query_int(request, "offset", 0, 0, None)
        kind = request.query_params.get("kind")
        if kind is not None and kind not in ("spec", "general"):
            raise VerityError("INVALID_REQUEST", "kind must be spec or general", {"field": "kind"})
        return _to_wire(await service.list_documents(limit, offset, kind))

    @app.get(API_PREFIX + "/documents/{document_id}")
    async def get_document(document_id: str, request: Request):
        service = request.app.state.service
        return _to_wire(await service.get_document(_path_uuid(document_id, "document_id")))

    @app.get(API_PREFIX + "/sources")
    async def list_sources(request: Request):
        service = request.app.state.service
        limit = _query_int(request, "limit", 50, 1, 100)
        offset = _query_int(request, "offset", 0, 0, None)
        return _to_wire(await service.list_sources(limit, offset))

    # ------------------------------------------------ V7 search/evidence/query

    @app.post(API_PREFIX + "/search")
    async def search(request: Request):
        service = request.app.state.service
        body = await _json_body(request)
        search_request = parse_search_args(body)
        return _to_wire(
            await _with_deadline("search", dl["search"], lambda: service.search_evidence(search_request))
        )

    @app.get(API_PREFIX + "/requirements/{requirement_id}")
    async def get_requirement(requirement_id: str, request: Request):
        service = request.app.state.service
        requirement_id = parse_get_requirement_args({"requirement_id": requirement_id})
        return _to_wire(await service.get_requirement(requirement_id))

    @app.get(API_PREFIX + "/evidence/{evidence_id}")
    async def get_evidence(evidence_id: str, request: Request):
        service = request.app.state.service
        context_chars = _query_int(request, "context_chars", 1000, 0, 4000)
        evidence_id, context_chars = parse_get_evidence_args(
            {"evidence_id": evidence_id, "context_chars": context_chars}
        )
        return _to_wire(
            await _with_deadline(
                "get_evidence", dl["get_evidence"], lambda: service.get_evidence(evidence_id, context_chars)
            )
        )

    @app.post(API_PREFIX + "/coverage")
    async def check_coverage(request: Request):
        service = request.app.state.service
        body = await _json_body(request)
        coverage_request = parse_check_coverage_args(body)
        return _to_wire(
            await _with_deadline("coverage", dl["coverage"], lambda: service.check_coverage(coverage_request))
        )

    @app.get(API_PREFIX + "/coverage/{coverage_id}")
    async def get_coverage(coverage_id: str, request: Request):
        service = request.app.state.service
        return _to_wire(await service.get_coverage(_path_uuid(coverage_id, "coverage_id")))

    # ------------------------------------------------- V8 chat (SDK delegation)

    def _gateway(request: Request):
        gateway = getattr(request.app.state, "gateway", None)
        if gateway is None:
            raise VerityError(
                "SDK_UNAVAILABLE",
                "native chat requires the Cline SDK gateway (contract 10), which is not configured",
            )
        return gateway

    @app.post(API_PREFIX + "/chat/sessions")
    async def create_chat_session(request: Request):
        body = await _json_body(request)
        if body:
            raise VerityError("INVALID_REQUEST", "chat session body must be an empty object")
        gateway = _gateway(request)
        return JSONResponse(content=_to_wire(gateway.create_session()), status_code=201)

    @app.post(API_PREFIX + "/chat/sessions/{session_id}/messages")
    async def send_chat_message(session_id: str, request: Request):
        _path_uuid(session_id, "session_id")
        body = await _json_body(request)
        if set(body) - {"text"}:
            raise VerityError("INVALID_REQUEST", "unknown fields in chat message body", {"field": "text"})
        text = body.get("text")
        if not isinstance(text, str) or not 1 <= len(text) <= 8000:
            raise VerityError("INVALID_REQUEST", "text must be a string of 1-8000 characters", {"field": "text"})
        gateway = _gateway(request)
        return _to_wire(gateway.send_message(session_id, text))