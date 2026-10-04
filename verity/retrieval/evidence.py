"""Evidence result builder and citation resolver.

Contract: Docs/contracts/07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md.
Owner Atharv/Piyush.

Every result carries a verbatim quote, locator, score provenance and a
display ``citation_label``; stable references are IDs. ``resolve``
verifies the quote still matches its stored immutable version and
returns ``STALE_EVIDENCE`` (``EVIDENCE_GONE``) for unresolvable versions.
"""

from __future__ import annotations


def build_evidence(unit_ids: list[str]) -> list[dict[str, object]]:
    """Build canonical evidence objects from ranked unit IDs. Skeleton."""
    raise NotImplementedError("evidence builder: scheduled Phase 11, contract 07")