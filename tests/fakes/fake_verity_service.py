"""FakeVerityService - transport-test stand-in for VerityService (contract 16).

Owned by the transport owner per Docs/roadmaps/09_VERITY_SHARED_FIXTURES_AND_MOCKS.md:
it lives in the transport owner's test directory to avoid merge conflicts and
returns the exact frozen wire fixtures (validated against
Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json), never an approximate object.

Guarantees tested by the transport suite:
  * one call per tool/route (call counting),
  * strict input validation with typed VerityError failures,
  * canonical success payloads identical in MCP structured/text outputs,
  * no SQL, retrieval logic, citation formatting or coverage evaluation here.

This is NOT a second canonical model: it only hands back JSON loaded from
tests/fixtures/v1 (which the suite validates against contract 21).
"""

from __future__ import annotations

import copy
import re
from typing import Any

_REQ_RE = re.compile(r"^req_[0-9a-f]{64}$")
_EV_RE = re.compile(r"^ev_[0-9a-f]{64}$")
_WORKSPACE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

REQUIRED_FIXTURES = (
    "search_result",
    "search_result_empty",
    "requirement",
    "evidence_lookup",
    "coverage_result",
)


class VerityError(Exception):
    """Typed public failure per contract 17.

    Core/adapters raise this; the transport adapter adds ``request_id`` and
    serializes the canonical ``Error`` object from contract 03.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.retryable = retryable


class FakeVerityService:
    """Duck-typed VerityService (contract 16) returning canonical wire fixtures.

    Args:
        fixtures: mapping of fixture name -> parsed JSON with at least the
            names in REQUIRED_FIXTURES (loaded from tests/fixtures/v1).
        no_match_query: a query that returns the empty SearchResult fixture
            (a no-match search is a success, never an error - contract 09).
    """

    def __init__(self, fixtures: dict[str, dict[str, Any]], *, no_match_query: str = "zz-no-match") -> None:
        missing = [name for name in REQUIRED_FIXTURES if name not in fixtures]
        if missing:
            raise ValueError(f"FakeVerityService: missing fixtures: {missing}")
        self._fixtures = fixtures
        self._no_match_query = no_match_query
        self.call_counts: dict[str, int] = {name: 0 for name in REQUIRED_FIXTURES}

    @staticmethod
    def _require(condition: bool, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        if not condition:
            raise VerityError(code, message, details)

    async def search_evidence(self, request: dict[str, Any]) -> dict[str, Any]:
        self.call_counts["search_result"] += 1
        self._require(isinstance(request, dict), "INVALID_REQUEST", "search request must be an object")
        query = request.get("query")
        self._require(
            isinstance(query, str) and 2 <= len(query) <= 2000,
            "INVALID_REQUEST",
            "query must be a string of 2-2000 characters",
            {"field": "query"},
        )
        limit = request.get("limit", 8)
        self._require(
            isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= 20,
            "INVALID_REQUEST",
            "limit must be an integer 1-20",
            {"field": "limit"},
        )
        if query == self._no_match_query:
            return copy.deepcopy(self._fixtures["search_result_empty"])
        return copy.deepcopy(self._fixtures["search_result"])

    async def get_requirement(self, requirement_id: str) -> dict[str, Any]:
        self.call_counts["requirement"] += 1
        self._require(
            isinstance(requirement_id, str) and bool(_REQ_RE.match(requirement_id)),
            "INVALID_REQUEST",
            "requirement_id must match req_ + 64 lowercase hex",
            {"field": "requirement_id"},
        )
        requirement = self._fixtures["requirement"]
        if requirement_id != requirement["requirement_id"]:
            raise VerityError(
                "REQUIREMENT_NOT_FOUND",
                "No active requirement matches the given requirement ID.",
                {"field": "requirement_id"},
            )
        return copy.deepcopy(requirement)

    async def get_evidence(self, evidence_id: str, context_chars: int = 1000) -> dict[str, Any]:
        self.call_counts["evidence_lookup"] += 1
        self._require(
            isinstance(evidence_id, str) and bool(_EV_RE.match(evidence_id)),
            "INVALID_REQUEST",
            "evidence_id must match ev_ + 64 lowercase hex",
            {"field": "evidence_id"},
        )
        self._require(
            isinstance(context_chars, int) and not isinstance(context_chars, bool) and 0 <= context_chars <= 4000,
            "INVALID_REQUEST",
            "context_chars must be an integer 0-4000",
            {"field": "context_chars"},
        )
        lookup = self._fixtures["evidence_lookup"]
        if evidence_id != lookup["evidence"]["evidence_id"]:
            raise VerityError(
                "EVIDENCE_NOT_FOUND",
                "No evidence matches the given evidence ID.",
                {"field": "evidence_id"},
            )
        return copy.deepcopy(lookup)

    async def check_coverage(self, request: dict[str, Any]) -> dict[str, Any]:
        self.call_counts["coverage_result"] += 1
        self._require(isinstance(request, dict), "INVALID_REQUEST", "coverage request must be an object")
        ids = request.get("requirement_ids")
        self._require(
            isinstance(ids, list)
            and 1 <= len(ids) <= 50
            and len(set(ids)) == len(ids)
            and all(isinstance(i, str) and bool(_REQ_RE.match(i)) for i in ids),
            "INVALID_REQUEST",
            "requirement_ids must be 1-50 unique req_ hashes",
            {"field": "requirement_ids"},
        )
        workspace_id = request.get("workspace_id")
        self._require(
            isinstance(workspace_id, str) and bool(_WORKSPACE_RE.match(workspace_id)),
            "INVALID_REQUEST",
            "workspace_id must match the config key pattern ^[a-z][a-z0-9_-]{0,31}$",
            {"field": "workspace_id"},
        )
        fixture = self._fixtures["coverage_result"]
        if workspace_id != fixture["workspace_id"]:
            raise VerityError(
                "WORKSPACE_NOT_FOUND",
                "No configured workspace matches the given workspace_id.",
                {"field": "workspace_id"},
            )
        by_id = {item["requirement_id"]: item for item in fixture["results"]}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise VerityError(
                "REQUIREMENT_NOT_FOUND",
                "One or more requirement IDs are not active.",
                {"field": "requirement_ids", "missing": missing},
            )
        result = copy.deepcopy(fixture)
        result["results"] = [by_id[i] for i in ids]  # preserve request order (contract 12)
        return result