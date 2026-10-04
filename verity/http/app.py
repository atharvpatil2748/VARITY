"""VERITY HTTP API v1 bootstrap (roadmap 04, step V5).

Contracts: 11 (routes/headers/Health), 14 (loopback api_host/api_port,
mcp_transport stays stdio in v1 - this module is the /api/v1 UI app, NOT
MCP-over-HTTP), 17 (code->status table, canonical Error bodies), 21
($defs Health, HttpError, Error). The router only validates/deserializes,
delegates to VerityService and serializes: no SQL, retrieval, chat
reasoning or coverage evaluation happens here.

Success responses are canonical model JSON with Content-Type
application/json, X-Request-ID and X-VERITY-Contract-Version: 1.0.0 and
no wrapper. Every error body is {"error": Error} (HttpError $def) at the
contract-17 status for its code. Unmatched routes/methods are client
errors and use the canonical INVALID_REQUEST code at its table status.
Health when the database is unavailable returns 503 (contract 11) with
CONFIG_INVALID, the only frozen code tied to "health 503" in contract 17.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from verity.errors import SCHEMA_VERSION, VerityError

log = logging.getLogger("verity.http")

API_PREFIX = "/api/v1"
CONTRACT_VERSION_HEADER = "X-VERITY-Contract-Version"
REQUEST_ID_HEADER = "X-Request-ID"

#: Canonical HTTP status per frozen error code (contract 17 table).
STATUS_BY_CODE: dict[str, int] = {
    "INVALID_REQUEST": 400,
    "CONFIG_INVALID": 500,
    "VERSION_UNSUPPORTED": 409,
    "UNSUPPORTED_FORMAT": 415,
    "SPEC_VALIDATION_ERROR": 422,
    "PARSER_ERROR": 422,
    "CHUNKING_ERROR": 500,
    "LIMIT_EXCEEDED": 413,
    "SOURCE_NOT_FOUND": 404,
    "DOCUMENT_NOT_FOUND": 404,
    "REQUIREMENT_NOT_FOUND": 404,
    "EVIDENCE_NOT_FOUND": 404,
    "EVIDENCE_GONE": 410,
    "COVERAGE_NOT_FOUND": 404,
    "WORKSPACE_NOT_FOUND": 404,
    "WORKSPACE_DENIED": 403,
    "MODEL_UNAVAILABLE": 503,
    "RETRIEVAL_UNAVAILABLE": 503,
    "COVERAGE_UNAVAILABLE": 503,
    "SDK_UNAVAILABLE": 503,
    "SESSION_NOT_FOUND": 404,
    "TIMEOUT": 504,
    "INTERNAL_ERROR": 500,
}

_SERVICE_METHODS = ("search_evidence", "get_requirement", "get_evidence", "check_coverage")


@dataclass(frozen=True)
class HealthState:
    """Truthful runtime health inputs feeding the contract-11 Health object."""

    database_ready: bool = True
    retrieval_mode: str | None = "hybrid"
    sdk_available: bool = False

    @property
    def status(self) -> str:
        return "ok" if self.database_ready and self.retrieval_mode is not None else "degraded"


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) and rid else str(uuid.uuid4())


def _error_body(err: VerityError, request_id: str) -> dict[str, object]:
    return {"error": err.to_dict(request_id)}


def _error_response(err: VerityError, request_id: str, status: int | None = None) -> JSONResponse:
    return JSONResponse(
        content=_error_body(err, request_id),
        status_code=status if status is not None else STATUS_BY_CODE[err.code],
    )


# ---------------------------------------------------------- exception handlers


async def _verity_error_handler(request: Request, exc: VerityError) -> JSONResponse:
    rid = _request_id(request)
    log.info("http error code=%s path=%s request_id=%s", exc.code, request.url.path, rid)
    return _error_response(exc, rid)


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    err = VerityError(
        "INVALID_REQUEST",
        f"no {request.method} route for {request.url.path}",
        {"transport_status": exc.status_code},
    )
    return _error_response(err, _request_id(request))


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = {
        "errors": [
            {"field": ".".join(str(loc) for loc in item.get("loc", ())), "type": item.get("type")}
            for item in exc.errors()
        ]
    }
    err = VerityError("INVALID_REQUEST", "request body or parameters failed validation", details)
    return _error_response(err, _request_id(request))


async def _crash_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("http crash path=%s request_id=%s", request.url.path, _request_id(request))
    return _error_response(VerityError("INTERNAL_ERROR", "internal server error"), _request_id(request))


def create_app(service: object, health: HealthState | None = None) -> FastAPI:
    """Build the loopback /api/v1 app bound to a VerityService-like object.

    ``service`` must expose the contract-16 surface (same rule as the MCP
    server); route handlers (V6/V7) delegate to it exactly once per request.
    ``health`` carries the truthful HealthState; the fake service default is
    fine for transport tests, real deployments pass runtime probes.
    """

    if not all(callable(getattr(service, name, None)) for name in _SERVICE_METHODS):
        raise VerityError("INVALID_REQUEST", "service does not expose the contract-16 VerityService surface")

    app = FastAPI(
        title="verity",
        version=SCHEMA_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.service = service
    app.state.health = health if health is not None else HealthState()

    @app.middleware("http")
    async def _canonical_headers(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers[CONTRACT_VERSION_HEADER] = SCHEMA_VERSION
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    @app.get(API_PREFIX + "/health")
    async def get_health(request: Request):
        state: HealthState = request.app.state.health
        rid = _request_id(request)
        if not state.database_ready:
            log.warning("health degraded: database unavailable request_id=%s", rid)
            err = VerityError("CONFIG_INVALID", "database is unavailable", {"component": "database"})
            return _error_response(err, rid, status=503)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": state.status,
            "database": "ready",
            "retrieval_mode": state.retrieval_mode,
            "sdk_available": state.sdk_available,
        }

    app.add_exception_handler(VerityError, _verity_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _crash_handler)
    return app


def serve(service: object, health: HealthState | None = None, config: object | None = None) -> None:
    """Serve /api/v1 on loopback per contract 14 (real service only).

    Refuses non-loopback hosts (v1 serves 127.0.0.1 only, contract 14) and
    never substitutes a fake service; the caller passes the real
    VerityService from ``verity.service`` (PR-A4) or a test fake explicitly.
    """

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - dev env guard
        raise SystemExit(
            "uvicorn is required to serve the HTTP API: pip install 'verity[http]'"
        ) from exc

    api_host = getattr(config, "api_host", "127.0.0.1")
    if api_host != "127.0.0.1":
        raise VerityError("CONFIG_INVALID", "api_host must be 127.0.0.1 in v1 (contract 14)")
    app = create_app(service, health)
    log.info("verity http api 1.0.0 starting on %s (loopback, contract 14)", api_host)
    uvicorn.run(app, host=api_host, port=getattr(config, "api_port", 8765), log_level="warning")
