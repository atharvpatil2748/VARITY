"""MCP tool input validation (roadmap V3).

Each parser enforces the exact frozen input schemas from
Docs/contracts/09_VERITY_MCP_CONTRACT.md - ``additionalProperties: false``,
required fields, ID patterns, ranges, ``uniqueItems`` and contract defaults -
and produces the typed canonical request objects the ``VerityService`` surface
expects (Docs/contracts/16). Validation failures raise
``verity.errors.VerityError("INVALID_REQUEST", ...)`` with safe messages.

No SQL, retrieval, citation formatting or coverage logic lives here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from verity.errors import VerityError
from verity.models import CoverageRequest, SearchRequest

#: The four canonical MCP tools (contract 09). No aliases exist in v1.
TOOL_NAMES: tuple[str, ...] = (
    "search_evidence",
    "get_requirement",
    "get_evidence",
    "check_coverage",
)

_REQ_ID_RE = re.compile(r"^req_[0-9a-f]{64}$")
_EV_ID_RE = re.compile(r"^ev_[0-9a-f]{64}$")
_WORKSPACE_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

_DOCUMENT_KINDS = ("spec", "general")
_CHUNK_KINDS = (
    "requirement",
    "acceptance_criterion",
    "api_definition",
    "general_chunk",
    "code_chunk",
)

#: Exact frozen input schemas (contract 09), advertised verbatim in tools/list.
TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_evidence": {
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 2000},
            "document_ids": {
                "type": ["array", "null"],
                "minItems": 1,
                "maxItems": 100,
                "uniqueItems": True,
                "items": {"type": "string", "format": "uuid"},
                "default": None,
            },
            "document_kinds": {
                "type": ["array", "null"],
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "enum": ["spec", "general"]},
                "default": None,
            },
            "chunk_kinds": {
                "type": ["array", "null"],
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "enum": ["requirement", "acceptance_criterion", "api_definition", "general_chunk", "code_chunk"]},
                "default": None,
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
            "per_document_limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 20, "default": None},
        },
    },
    "get_requirement": {
        "type": "object",
        "additionalProperties": False,
        "required": ["requirement_id"],
        "properties": {"requirement_id": {"type": "string", "pattern": "^req_[0-9a-f]{64}$"}},
    },
    "get_evidence": {
        "type": "object",
        "additionalProperties": False,
        "required": ["evidence_id"],
        "properties": {
            "evidence_id": {"type": "string", "pattern": "^ev_[0-9a-f]{64}$"},
            "context_chars": {"type": "integer", "minimum": 0, "maximum": 4000, "default": 1000},
        },
    },
    "check_coverage": {
        "type": "object",
        "additionalProperties": False,
        "required": ["requirement_ids", "workspace_id"],
        "properties": {
            "requirement_ids": {
                "type": "array",
                "minItems": 1,
                "maxItems": 50,
                "uniqueItems": True,
                "items": {"type": "string", "pattern": "^req_[0-9a-f]{64}$"},
            },
            "workspace_id": {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,31}$"},
            "run_tests": {"type": "boolean", "default": False},
        },
    },
}

#: Tool descriptions guiding Cline (contract 09); guidance, not enforcement.
TOOL_DESCRIPTIONS: dict[str, str] = {
    "search_evidence": (
        "Search the indexed workspace for evidence-backed answers before writing code. "
        "Returns a canonical SearchResult whose Evidence items carry ev_ markers to cite."
    ),
    "get_requirement": (
        "Resolve one requirement by its req_ ID to the exact clause text, filters "
        "and acceptance criteria before implementing it."
    ),
    "get_evidence": (
        "Fetch one cited Evidence marker by its ev_ ID, with provenance and surrounding "
        "source context, to verify a citation."
    ),
    "check_coverage": (
        "After making changes, check which requirements are IMPLEMENTED, PARTIAL or "
        "MISSING in a workspace. Writes an immutable coverage report; never changes code."
    ),
}


def _object(tool: str, args: Any) -> dict[str, Any]:
    if not isinstance(args, Mapping):
        raise VerityError("INVALID_REQUEST", f"{tool} arguments must be a JSON object", {"tool": tool})
    return dict(args)


def _reject_unknown(tool: str, data: dict[str, Any], allowed: frozenset[str]) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise VerityError("INVALID_REQUEST", f"{tool} has unknown fields", {"unknown_fields": sorted(unknown)})


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _string_array(
    tool: str,
    field: str,
    items: Any,
    *,
    min_items: int,
    max_items: int | None = None,
    pattern: re.Pattern[str] | None = None,
    enum: tuple[str, ...] | None = None,
) -> None:
    if not isinstance(items, list):
        raise VerityError("INVALID_REQUEST", f"{field} must be an array", {"field": field})
    if len(items) < min_items or (max_items is not None and len(items) > max_items):
        raise VerityError("INVALID_REQUEST", f"{field} has an invalid length", {"field": field})
    if len(set(items)) != len(items):
        raise VerityError("INVALID_REQUEST", f"{field} must have unique items", {"field": field})
    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise VerityError("INVALID_REQUEST", f"{field}[{index}] must be a string", {"field": field})
        if pattern is not None and not pattern.fullmatch(item):
            raise VerityError("INVALID_REQUEST", f"{field}[{index}] does not match the required pattern", {"field": field})
        if enum is not None and item not in enum:
            raise VerityError("INVALID_REQUEST", f"{field}[{index}] is not an allowed value", {"field": field})


def parse_search_args(args: Any) -> SearchRequest:
    """Validate search_evidence input and build the typed SearchRequest."""
    data = _object("search_evidence", args)
    _reject_unknown(
        "search_evidence",
        data,
        frozenset({"query", "document_ids", "document_kinds", "chunk_kinds", "limit", "per_document_limit"}),
    )
    query = data.get("query")
    if not isinstance(query, str) or not 2 <= len(query) <= 2000:
        raise VerityError("INVALID_REQUEST", "query must be a string of 2-2000 characters", {"field": "query"})
    for field in ("document_ids", "document_kinds", "chunk_kinds", "per_document_limit"):
        data.setdefault(field, None)
    data.setdefault("limit", 8)
    if data["document_ids"] is not None:
        _string_array("search_evidence", "document_ids", data["document_ids"], min_items=1, max_items=100, pattern=_UUID4_RE)
    if data["document_kinds"] is not None:
        _string_array("search_evidence", "document_kinds", data["document_kinds"], min_items=1, enum=_DOCUMENT_KINDS)
    if data["chunk_kinds"] is not None:
        _string_array("search_evidence", "chunk_kinds", data["chunk_kinds"], min_items=1, enum=_CHUNK_KINDS)
    if not _is_int(data["limit"]) or not 1 <= data["limit"] <= 20:
        raise VerityError("INVALID_REQUEST", "limit must be an integer 1-20", {"field": "limit"})
    per_document_limit = data["per_document_limit"]
    if per_document_limit is not None and (not _is_int(per_document_limit) or not 1 <= per_document_limit <= 20):
        raise VerityError("INVALID_REQUEST", "per_document_limit must be an integer 1-20 or null", {"field": "per_document_limit"})
    return SearchRequest.from_dict(data)


def parse_get_requirement_args(args: Any) -> str:
    """Validate get_requirement input and return the requirement_id."""
    data = _object("get_requirement", args)
    _reject_unknown("get_requirement", data, frozenset({"requirement_id"}))
    requirement_id = data.get("requirement_id")
    if not isinstance(requirement_id, str) or not _REQ_ID_RE.fullmatch(requirement_id):
        raise VerityError("INVALID_REQUEST", "requirement_id must match req_ + 64 lowercase hex", {"field": "requirement_id"})
    return requirement_id


def parse_get_evidence_args(args: Any) -> tuple[str, int]:
    """Validate get_evidence input; return (evidence_id, context_chars)."""
    data = _object("get_evidence", args)
    _reject_unknown("get_evidence", data, frozenset({"evidence_id", "context_chars"}))
    evidence_id = data.get("evidence_id")
    if not isinstance(evidence_id, str) or not _EV_ID_RE.fullmatch(evidence_id):
        raise VerityError("INVALID_REQUEST", "evidence_id must match ev_ + 64 lowercase hex", {"field": "evidence_id"})
    context_chars = data.get("context_chars", 1000)
    if not _is_int(context_chars) or not 0 <= context_chars <= 4000:
        raise VerityError("INVALID_REQUEST", "context_chars must be an integer 0-4000", {"field": "context_chars"})
    return evidence_id, context_chars


def parse_check_coverage_args(args: Any) -> CoverageRequest:
    """Validate check_coverage input and build the typed CoverageRequest."""
    data = _object("check_coverage", args)
    _reject_unknown("check_coverage", data, frozenset({"requirement_ids", "workspace_id", "run_tests"}))
    requirement_ids = data.get("requirement_ids")
    if not isinstance(requirement_ids, list):
        raise VerityError("INVALID_REQUEST", "requirement_ids is required and must be an array", {"field": "requirement_ids"})
    _string_array("check_coverage", "requirement_ids", requirement_ids, min_items=1, max_items=50, pattern=_REQ_ID_RE)
    workspace_id = data.get("workspace_id")
    if not isinstance(workspace_id, str) or not _WORKSPACE_ID_RE.fullmatch(workspace_id):
        raise VerityError("INVALID_REQUEST", "workspace_id must match ^[a-z][a-z0-9_-]{0,31}$", {"field": "workspace_id"})
    data.setdefault("run_tests", False)
    if not isinstance(data["run_tests"], bool):
        raise VerityError("INVALID_REQUEST", "run_tests must be a boolean", {"field": "run_tests"})
    return CoverageRequest.from_dict(data)