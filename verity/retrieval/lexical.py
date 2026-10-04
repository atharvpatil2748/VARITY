"""Safe FTS5 lexical search.

Contract: Docs/contracts/06_VERITY_RETRIEVAL_CONTRACT.md. Owner Piyush.

FTS5 queries are parameterized and term-escaped (BM25); scope filters
apply before ranking. Never string-interpolate user input into MATCH.
"""

from __future__ import annotations

from typing import Any


def escape_fts_query(query: str) -> str:
    """Escape a raw query into a safe FTS5 MATCH expression (contract 06)."""
    return '"' + query.replace('"', '""') + '"'


def lexical_search(query: str, *, limit: int, filters: dict[str, Any]) -> list[str]:
    """Return ``(chunk_id, bm25_rank)`` candidates. Skeleton for Phase 11."""
    raise NotImplementedError("lexical search: scheduled Phase 11, contract 06")