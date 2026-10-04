"""Canonical SDK tools (contract 10; owner Atharv).

Tool names and input schemas are IDENTICAL to contract 09's MCP tools; a
parity test pins this module's schemas to ``verity.mcp.tools.TOOL_SCHEMAS``
and to the contract-09 JSON block parsed live. ``execute`` delegates to the
single ``VerityService`` — no SDK-specific DTO, no independent retrieval,
citation or coverage logic. Expected failures return structured ``Error``
data instead of throwing into the agent loop (contracts 10/17).
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from verity.errors import VerityError
from verity.models import CoverageRequest, IngestMode, IngestRequest, SearchRequest

#: The four canonical tool names (contract 09/10). No aliases in v1.
TOOL_NAMES = (
    "search_evidence",
    "get_requirement",
    "get_evidence",
    "check_coverage",
)

_REQ_ID_RE = re.compile(r"^req_[0-9a-f]{64}$")
_EV_ID_RE = re.compile(r"^ev_[0-9a-f]{64}$")
_WORKSPACE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

_DOCUMENT_KINDS = ("spec", "general")
_CHUNK_KINDS = (
    "requirement", "acceptance_criterion", "api_definition",
    "general_chunk", "code_chunk",
)

#: Exact frozen input schemas (contract 09) — verbatim, for parity tests.
TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_evidence": {
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 2000},
            "document_ids": {
                "type": ["array", "null"], "minItems": 1, "maxItems": 100,
                "uniqueItems": True,
                "items": {"type": "string", "format": "uuid"}, "default": None,
            },
            "document_kinds": {
                "type": ["array", "null"], "minItems": 1, "uniqueItems": True,
                "items": {"type": "string", "enum": ["spec", "general"]},
                "default": None,
            },
            "chunk_kinds": {
                "type": ["array", "null"], "minItems": 1, "uniqueItems": True,
                "items": {"type": "string", "enum": [
                    "requirement", "acceptance_criterion", "api_definition",
                    "general_chunk", "code_chunk"]},
                "default": None,
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
            "per_document_limit": {
                "type": ["integer", "null"], "minimum": 1, "maximum": 20,
                "default": None,
            },
        },
    },
    "get_requirement": {
        "type": "object",
        "additionalProperties": False,
        "required": ["requirement_id"],
        "properties": {
            "requirement_id": {"type": "string", "pattern": "^req_[0-9a-f]{64}$"},
        },
    },
    "get_evidence": {
        "type": "object",
        "additionalProperties": False,
        "required": ["evidence_id"],
        "properties": {
            "evidence_id": {"type": "string", "pattern": "^ev_[0-9a-f]{64}$"},
            "context_chars": {
                "type": "integer", "minimum": 0, "maximum": 4000, "default": 1000},
        },
    },
    "check_coverage": {
        "type": "object",
        "additionalProperties": False,
        "required": ["requirement_ids", "workspace_id"],
        "properties": {
            "requirement_ids": {
                "type": "array", "minItems": 1, "maxItems": 50, "uniqueItems": True,
                "items": {"type": "string", "pattern": "^req_[0-9a-f]{64}$"}},
            "workspace_id": {
                "type": "string", "pattern": "^[a-z][a-z0-9_-]{0,31}$"},
            "run_tests": {"type": "boolean", "default": False},
        },
    },
}


def _invalid(message: str, field: str) -> VerityError:
    return VerityError("INVALID_REQUEST", message, {"field": field})


def _parse_search(args: dict[str, Any]) -> SearchRequest:
    query = args.get("query")
    if not isinstance(query, str) or not 2 <= len(query) <= 2000:
        raise _invalid("query must be a string of 2-2000 characters", "query")
    document_ids = args.get("document_ids")
    if document_ids is not None:
        if not isinstance(document_ids, list) or not document_ids:
            raise _invalid("document_ids must be a nonempty array or null",
                           "document_ids")
        for item in document_ids:
            if not isinstance(item, str) or not _UUID4_RE.fullmatch(item):
                raise _invalid("document_ids items must be UUIDv4 strings",
                               "document_ids")
    limit = args.get("limit", 8)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise _invalid("limit must be an integer 1-20", "limit")
    per_document_limit = args.get("per_document_limit")
    if per_document_limit is not None and (
        not isinstance(per_document_limit, int)
        or isinstance(per_document_limit, bool)
        or not 1 <= per_document_limit <= 20
    ):
        raise _invalid("per_document_limit must be an integer 1-20 or null",
                       "per_document_limit")
    return SearchRequest(
        query=query,
        document_ids=document_ids,
        document_kinds=None,
        chunk_kinds=None,
        limit=limit,
        per_document_limit=per_document_limit,
    )


def _error_data(err: VerityError) -> dict[str, Any]:
    """Structured Error data for expected failures (contract 10/17)."""
    return err.to_dict(str(uuid4()))


async def execute_tool(service, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one canonical tool against the single VerityService.

    Returns the canonical success object or structured ``Error`` data; never
    raises into the agent loop for expected failures (contract 10).
    """
    try:
        if name == "search_evidence":
            result = await service.search_evidence(_parse_search(args))
        elif name == "get_requirement":
            requirement_id = args.get("requirement_id")
            if not isinstance(requirement_id, str) or not _REQ_ID_RE.fullmatch(
                requirement_id
            ):
                raise _invalid(
                    "requirement_id must match req_ + 64 lowercase hex",
                    "requirement_id",
                )
            result = await service.get_requirement(requirement_id)
        elif name == "get_evidence":
            evidence_id = args.get("evidence_id")
            if not isinstance(evidence_id, str) or not _EV_ID_RE.fullmatch(evidence_id):
                raise _invalid(
                    "evidence_id must match ev_ + 64 lowercase hex", "evidence_id")
            context_chars = args.get("context_chars", 1000)
            if not isinstance(context_chars, int) or isinstance(context_chars, bool) \
                    or not 0 <= context_chars <= 4000:
                raise _invalid("context_chars must be an integer 0-4000",
                               "context_chars")
            result = await service.get_evidence(evidence_id, context_chars)
        elif name == "check_coverage":
            requirement_ids = args.get("requirement_ids")
            if not isinstance(requirement_ids, list) or not requirement_ids:
                raise _invalid("requirement_ids must be a nonempty array",
                               "requirement_ids")
            for item in requirement_ids:
                if not isinstance(item, str) or not _REQ_ID_RE.fullmatch(item):
                    raise _invalid(
                        "requirement_ids items must match req_ + 64 lowercase hex",
                        "requirement_ids")
            workspace_id = args.get("workspace_id")
            if not isinstance(workspace_id, str) or not _WORKSPACE_ID_RE.fullmatch(
                workspace_id
            ):
                raise _invalid(
                    "workspace_id must match ^[a-z][a-z0-9_-]{0,31}$", "workspace_id")
            run_tests = args.get("run_tests", False)
            if not isinstance(run_tests, bool):
                raise _invalid("run_tests must be a boolean", "run_tests")
            result = await service.check_coverage(CoverageRequest(
                requirement_ids=requirement_ids,
                workspace_id=workspace_id,
                run_tests=run_tests,
            ))
        else:
            return _error_data(VerityError(
                "INVALID_REQUEST", f"unknown tool: {name}", {"tool": name}))
        return result.to_dict()
    except VerityError as err:
        return _error_data(err)
    except Exception:
        return _error_data(VerityError(
            "INTERNAL_ERROR", "internal tool failure"))