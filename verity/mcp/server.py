"""MCP stdio server registration and structured replies.

Contract: Docs/contracts/09_VERITY_MCP_CONTRACT.md. Owner Vandit.

Exactly four v1 tools: ``search_evidence``, ``get_requirement``,
``get_evidence``, ``check_coverage`` (``compare_sources`` is a should-have
fifth). stdio is primary: stdout carries protocol only, diagnostics go
to stderr. Responses return ``structuredContent`` when the pinned MCP SDK
supports it, with JSON text fallback; errors stay structured, never
tracebacks.
"""

from __future__ import annotations

from typing import Any

from ..service import VerityService

#: Frozen v1 tool names (contract 09).
TOOL_NAMES = (
    "search_evidence",
    "get_requirement",
    "get_evidence",
    "check_coverage",
    "compare_sources",
)


def build_server(service: VerityService) -> Any:
    """Create the MCP stdio server bound to ``VerityService``.

    Skeleton for Phase 11 hours 1-3: register the four tools with input
    schemas from ``schemas.py``, wire structured replies and caps on
    query length, result count, output bytes and time (contract 09).
    """
    raise NotImplementedError("mcp server: scheduled Phase 11, contract 09")