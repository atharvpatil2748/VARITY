"""General document parser protocol and format dispatch.

Contract: Docs/contracts/05_VERITY_DOCUMENT_INGESTION_CONTRACT.md.
Owner Piyush (Phase 9: ``ingestion/parsers.py``).

``Parser.parse`` is pure: bytes in, ``ParsedDocument`` out, no I/O.
Built-ins for v1: PDF (per-page text), Markdown (heading-aware blocks),
TXT (paragraph blocks) and source code (file/line blocks). Image-only
or unsupported content yields warnings and ``partial`` status, never OCR
claims.
"""

from __future__ import annotations

from typing import Protocol

from ..models import ParsedDocument

#: Media types / extensions accepted by the v1 parser registry.
SUPPORTED_MEDIA_TYPES = ("application/pdf", "text/markdown", "text/plain")


class Parser(Protocol):
    """Pure parser protocol: ``parse(bytes, filename) -> ParsedDocument``."""

    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        """Parse raw bytes into canonical blocks; record warnings, never raise I/O."""
        ...


def dispatch_parser(filename: str, media_type: str) -> Parser:
    """Choose the v1 built-in parser by media type/extension (contract 05).

    Skeleton for Phase 11; raises ``UNSUPPORTED_FORMAT`` for unknown types.
    """
    from ..errors import VerityError

    raise VerityError(
        "UNSUPPORTED_FORMAT",
        f"parser registry not yet implemented for {media_type!r} (Phase 11)",
    )