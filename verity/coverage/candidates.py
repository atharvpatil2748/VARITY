"""Code/test candidate search for coverage.

Contract: Docs/contracts/12_VERITY_COVERAGE_CONTRACT.md. Owner Vanashree.

Searches filenames, symbols, requirement IDs, API names and keywords over
the safe workspace snapshot, then reads bounded line excerpts only.
"""

from __future__ import annotations


def find_candidates(query: str, root: object) -> list[str]:
    """Return candidate relative paths. Skeleton for Phase 11."""
    raise NotImplementedError("coverage candidates: scheduled Phase 11, contract 12")