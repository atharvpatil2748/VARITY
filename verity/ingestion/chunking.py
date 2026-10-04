"""Deterministic chunker protocol and unit drafts.

Contract: Docs/contracts/05_VERITY_DOCUMENT_INGESTION_CONTRACT.md.
Owner Piyush (Phase 9: ``ingestion/chunking.py``).

Rules: one spec requirement is one retrieval unit; Markdown/TXT split on
headings then paragraphs targeting 300-600 tokens with ~50-token overlap;
never cross page or heading boundaries; code splits by function/class when
a safe parser exists, else bounded line windows. The central materializer
validates spans and assigns IDs (``verity.ids.make_chunk_id``) before
persistence.
"""

from __future__ import annotations

from typing import Protocol

from ..models import ChunkDraft, ParsedDocument

#: Target chunk sizes (ARCHITECTURE.md Phase 4).
TARGET_MIN_TOKENS = 300
TARGET_MAX_TOKENS = 600
OVERLAP_TOKENS = 50


class Chunker(Protocol):
    """Deterministic chunker: ``chunk(ParsedDocument) -> list[ChunkDraft]``."""

    def chunk(self, document: ParsedDocument) -> list[ChunkDraft]:
        """Emit span-validated drafts; spans never cross page/heading bounds."""
        ...


def default_chunker(document_kind: str) -> Chunker:
    """Return the v1 chunker for a document kind. Skeleton for Phase 11."""
    from ..errors import VerityError

    raise VerityError(
        "CHUNKING_ERROR",
        "chunker dispatch not yet implemented (Phase 11, contract 05)",
    )