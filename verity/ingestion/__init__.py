"""VERITY ingestion package (owner: Piyush Ghayal).

Public cross-module interfaces (contract 16): ``Parser``, ``Chunker``,
``IngestionCoordinator``. Concrete pieces (contract 04/05): ``SpecParser``,
``ParserRouter`` and the format parsers, ``GeneralChunker`` and the central
``CentralMaterializer`` that assigns canonical IDs via the injected
``verity.ids`` maker. ``IngestionCoordinator.ingest`` is implemented in P5.
"""

from __future__ import annotations

from .chunking import CHUNKER_VERSION, CentralMaterializer, GeneralChunker
from .interfaces import Chunker, IngestionCoordinator, Materializer, Parser
from .parsers import (
    CodeParser,
    MarkdownParser,
    ParserRouter,
    PdfParser,
    TextParser,
    resolve_kind,
)
from .spec import SpecParser, looks_like_spec

__all__ = [
    "CHUNKER_VERSION",
    "CentralMaterializer",
    "Chunker",
    "CodeParser",
    "GeneralChunker",
    "IngestionCoordinator",
    "MarkdownParser",
    "Materializer",
    "Parser",
    "ParserRouter",
    "PdfParser",
    "SpecParser",
    "TextParser",
    "looks_like_spec",
    "resolve_kind",
]