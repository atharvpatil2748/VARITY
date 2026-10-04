"""Transactional ingestion pipeline.

Contract: Docs/contracts/05_VERITY_DOCUMENT_INGESTION_CONTRACT.md.
Owner Piyush (Phase 9: ``ingestion/pipeline.py``).

One transaction per document version: hash originals into
``data/originals/<sha256>``, create the version row, persist blocks,
requirements and retrieval units atomically, then embed in batches
(``pending`` / ``ready`` / ``failed``). A failed run leaves no partial
ingestion; lexical search stays usable when embeddings are unavailable.
"""

from __future__ import annotations

from ..config import VerityConfig
from ..models import IngestRequest, IngestResult


class IngestionPipeline:
    """Hash, version, parse, chunk, materialize and index one document."""

    def __init__(self, config: VerityConfig) -> None:
        self.config = config

    def run(self, request: IngestRequest) -> IngestResult:
        """Execute one transactional ingestion. Skeleton for Phase 11."""
        raise NotImplementedError("ingestion pipeline: scheduled Phase 11, contract 05")