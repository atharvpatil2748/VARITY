"""VERITY ingestion subpackage.

Contract 05 (document ingestion) and Phase 9 structure: spec parser,
general parsers, chunking and the transactional ingestion pipeline.
Owner Piyush.
"""

from .chunking import Chunker
from .parsers import Parser
from .spec import validate_spec_document

__all__ = ["Parser", "Chunker", "validate_spec_document"]