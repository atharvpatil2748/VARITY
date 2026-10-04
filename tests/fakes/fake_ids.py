"""Fixture ID maker for pre-PR-A1 tests (Piyush-owned).

Emits deterministic pattern-shaped IDs (``blk_``/``chk_``/``req_``/``ev_`` +
64 hex) without implementing any hashing: contract 03 forbids modules from
inventing ID hashing, so real IDs come only from ``verity.ids`` (Atharv,
PR-A1). ``tests/test_ingestion_chunking.py`` additionally runs the
materializer against the real ``verity.ids`` when it is importable and
checks the four golden vectors from contract 03.
"""

from __future__ import annotations


class FakeIdMaker:
    """Deterministic counter-based IDs in call order, per prefix."""

    def __init__(self) -> None:
        self._counters = {"blk_": 0, "chk_": 0, "req_": 0, "ev_": 0}
        self.calls: list[tuple[str, tuple]] = []

    def _next(self, prefix: str) -> str:
        self._counters[prefix] += 1
        return f"{prefix}{self._counters[prefix]:064x}"

    def make_block_id(self, version_id, ordinal, text) -> str:
        self.calls.append(("block", (str(version_id), ordinal, text)))
        return self._next("blk_")

    def make_chunk_id(self, version_id, draft) -> str:
        self.calls.append(("chunk", (str(version_id), draft)))
        return self._next("chk_")

    def make_requirement_id(self, source_id, local_id) -> str:
        self.calls.append(("requirement", (str(source_id), local_id)))
        return self._next("req_")

    def make_evidence_id(self, version_id, chunk_id) -> str:
        self.calls.append(("evidence", (str(version_id), chunk_id)))
        return self._next("ev_")