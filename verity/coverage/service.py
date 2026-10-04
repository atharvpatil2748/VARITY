"""Coverage orchestration service (contract 16) and N1 fake.

Pipeline (contract 12): scanner snapshot -> retriever candidates ->
evaluator verdicts -> immutable ``CoverageResult``. The workspace
revision is checked before and after evaluation; a changed workspace
downgrades affected results to ``UNCERTAIN`` with ``workspace_changed``,
never a confident verdict.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable, Mapping
from uuid import uuid4

from ..errors import VerityError
from ..models import (
    CoverageRequest,
    CoverageResult,
    CoverageStatus,
    Requirement,
    RequirementCoverage,
)
from .candidates import CodeEvidenceRetriever
from .evaluator import RequirementEvaluator
from .workspace import WorkspaceScanner, manifest_revision


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CoverageService:
    """Contract 16 protocol: ``check(request) -> CoverageResult``."""

    async def check(self, request: CoverageRequest) -> CoverageResult:
        raise NotImplementedError


class DefaultCoverageService(CoverageService):
    """N1 orchestration over injected scanner/retriever/evaluator.

    ``requirement_lookup`` is an async callable ``requirement_id ->
    Requirement``; the real store-backed lookup arrives with N6 (PR-A2).
    """

    def __init__(
        self,
        scanner: WorkspaceScanner,
        retriever: CodeEvidenceRetriever,
        evaluator: RequirementEvaluator,
        requirement_lookup: Callable[[str], Awaitable[Requirement]],
    ) -> None:
        self._scanner = scanner
        self._retriever = retriever
        self._evaluator = evaluator
        self._lookup = requirement_lookup

    async def check(self, request: CoverageRequest) -> CoverageResult:
        if request.requirement_ids is None:
            raise VerityError(
                "INVALID_REQUEST",
                "requirement_ids=null (all requirements) requires the real "
                "store and is scheduled for N6",
                {"field": "requirement_ids"},
            )
        ids = list(dict.fromkeys(request.requirement_ids))  # unique, order kept
        if len(ids) > 50:
            raise VerityError(
                "INVALID_REQUEST",
                "at most 50 requirement_ids per coverage request (contract 12)",
                {"count": len(ids)},
            )

        snapshot = await self._scanner.snapshot(request.workspace_id)
        results: list[RequirementCoverage] = []
        for requirement_id in ids:
            requirement = await self._lookup(requirement_id)
            code, tests = await self._retriever.find(requirement, snapshot)
            results.append(
                self._evaluator.evaluate(requirement, code, tests, request.run_tests)
            )

        limitations: list[str] = []
        after = await self._scanner.snapshot(request.workspace_id)
        if after.revision != snapshot.revision:
            results = [
                RequirementCoverage(
                    requirement_id=r.requirement_id,
                    status=CoverageStatus.UNCERTAIN,
                    reason=r.reason,
                    implementation=r.implementation,
                    tests=r.tests,
                    limitations=r.limitations + ["workspace_changed"],
                )
                for r in results
            ]
            limitations.append("workspace changed during evaluation")

        return CoverageResult(
            schema_version="1.0.0",
            coverage_id=str(uuid4()),
            workspace_id=request.workspace_id,
            workspace_revision=snapshot.revision,
            inspected_at=_now_utc(),
            results=results,
            limitations=limitations,
        )


class FakeCoverageService(CoverageService):
    """N1 fake for Atharv/Vandit: canned per-requirement coverage.

    No workspace is scanned; every requested ID maps to the provided
    ``RequirementCoverage`` (default ``UNCERTAIN`` when absent). Use only
    in tests and mocked demos - never in the production route.
    """

    def __init__(
        self,
        workspace_id: str = "fake",
        outcomes: Mapping[str, RequirementCoverage] | None = None,
        revision: str = "0" * 64,
    ) -> None:
        self._workspace_id = workspace_id
        self._outcomes = dict(outcomes or {})
        self._revision = revision

    def add(self, requirement_id: str, coverage: RequirementCoverage) -> None:
        self._outcomes[requirement_id] = coverage

    async def check(self, request: CoverageRequest) -> CoverageResult:
        if request.requirement_ids is None:
            raise VerityError(
                "INVALID_REQUEST",
                "FakeCoverageService requires explicit requirement_ids",
                {"field": "requirement_ids"},
            )
        results = [
            self._outcomes.get(
                rid,
                RequirementCoverage(
                    requirement_id=rid,
                    status=CoverageStatus.UNCERTAIN,
                    reason="fake coverage service has no canned outcome",
                ),
            )
            for rid in dict.fromkeys(request.requirement_ids)
        ]
        return CoverageResult(
            schema_version="1.0.0",
            coverage_id=str(uuid4()),
            workspace_id=request.workspace_id,
            workspace_revision=self._revision,
            inspected_at=_now_utc(),
            results=results,
            limitations=["fake coverage service: no workspace was scanned"],
        )