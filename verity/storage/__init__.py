"""VERITY storage subpackage.

Phase 9 structure: one writable SQLite database holding canonical rows,
FTS5 index and embedding records (contract 13, owner Atharv).
"""

from .sqlite import KnowledgeStore

__all__ = ["KnowledgeStore"]