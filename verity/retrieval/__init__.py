"""VERITY retrieval subpackage.

Phase 9 structure: lexical (FTS5), dense (BGE-M3), RRF fusion, optional
rerank and evidence building (contracts 06/07). Owner Piyush.
"""

__all__ = ["lexical_search", "dense_search", "fuse_rrf", "rerank",
           "build_evidence"]