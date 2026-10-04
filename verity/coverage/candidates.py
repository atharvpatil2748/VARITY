"""Code/test evidence retriever protocol (contract 16) and N1 fake.

Real candidate search over a safe snapshot is N3 and is blocked by D2
(contract 12 restricts file reads to the scanner; contract 16's snapshot
carries no file text). Until D2 is resolved, retrievers are exercised
through fake snapshots and metadata-only mappings.
"""

from __future__ import annotations

from ..models import CodeEvidence, Requirement, TestEvidence


class CodeEvidenceRetriever:
    """Contract 16 protocol: per-requirement candidate evidence."""

    async def find(
        self, requirement: Requirement, snapshot: object
    ) -> tuple[tuple[CodeEvidence, ...], tuple[TestEvidence, ...]]:
        raise NotImplementedError


class FakeCodeEvidenceRetriever(CodeEvidenceRetriever):
    """N1 fake: canned ``(code, tests)`` tuples keyed by requirement_id."""

    def __init__(
        self,
        mapping: dict[
            str,
            tuple[tuple[CodeEvidence, ...], tuple[TestEvidence, ...]],
        ],
    ) -> None:
        self._mapping = dict(mapping)

    async def find(
        self, requirement: Requirement, snapshot: object
    ) -> tuple[tuple[CodeEvidence, ...], tuple[TestEvidence, ...]]:
        return self._mapping.get(requirement.requirement_id, ((), ()))