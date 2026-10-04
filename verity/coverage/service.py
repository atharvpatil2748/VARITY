"""Coverage orchestration service (contract 16) and N1 fake.

Pipeline (contract 12): scanner snapshot -> retriever candidates ->
evaluator verdicts -> immutable ``CoverageResult``. The workspace
revision is checked before and after evaluation; a changed workspace
downgrades affected results to ``UNCERTAIN`` with ``workspace_changed``,
never a confident verdict.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Mapping, Protocol
from uuid import UUID, uuid4

from ..errors import VerityError
from ..models import (
    CoverageRequest,
    CoverageResult,
    CoverageStatus,
    Requirement,
    RequirementCoverage,
    TestEvidence,
    TestOutcome,
)
from .candidates import CodeEvidenceRetriever
from .evaluator import RequirementEvaluator
from .workspace import WorkspaceScanner, WorkspaceSnapshot

#: Contract 12: total coverage deadline is 30 seconds; reserve 3s slack.
COVERAGE_DEADLINE_SECONDS = 30.0
_DEADLINE_BUDGET = COVERAGE_DEADLINE_SECONDS - 3.0


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _CoverageStore(Protocol):
    """The store surface coverage needs (contract 16 KnowledgeStore)."""

    async def get_requirement(self, requirement_id: str) -> Requirement | None: ...
    async def save_coverage(self, result: CoverageResult) -> None: ...


class TestRunner(Protocol):
    """N5 surface: allowlisted run returning mapped test outcomes."""

    async def run(self, snapshot: WorkspaceSnapshot) -> tuple[TestEvidence, ...]: ...


class CoverageService:
    """Contract 16 protocol: ``check(request) -> CoverageResult``."""

    async def check(self, request: CoverageRequest) -> CoverageResult:
        raise NotImplementedError


class DefaultCoverageService(CoverageService):
    """N6 orchestration over scanner/retriever/evaluator/store (contract 12).

    ``requirement_lookup`` resolves requirement IDs (typically the real
    ``KnowledgeStore.get_requirement``); when ``store`` is provided the
    immutable ``CoverageResult`` is persisted exactly once per run
    (contract 16). ``test_runner`` runs only the allowlisted command
    (N5); its outcomes are merged into retrieved test evidence by path.
    """

    def __init__(
        self,
        scanner: WorkspaceScanner,
        retriever: CodeEvidenceRetriever,
        evaluator: RequirementEvaluator,
        requirement_lookup: Callable[[str], Awaitable[Requirement]],
        store: _CoverageStore | None = None,
        test_runner: TestRunner | None = None,
    ) -> None:
        self._scanner = scanner
        self._retriever = retriever
        self._evaluator = evaluator
        self._lookup = requirement_lookup
        self._store = store
        self._test_runner = test_runner

    async def check(self, request: CoverageRequest) -> CoverageResult:
        if request.requirement_ids is None:
            raise VerityError(
                "INVALID_REQUEST",
                "requirement_ids=null (all requirements) needs a store "
                "listing capability not in the contract-16 KnowledgeStore; "
                "pass explicit IDs (1-50)",
                {"field": "requirement_ids"},
            )
        ids = list(request.requirement_ids)
        if len(ids) != len(set(ids)):
            raise VerityError(
                "INVALID_REQUEST",
                "requirement_ids must be unique (contract 12)",
                {"field": "requirement_ids"},
            )
        if not 1 <= len(ids) <= 50:
            raise VerityError(
                "INVALID_REQUEST",
                "requirement_ids must contain 1-50 IDs (contract 12)",
                {"count": len(ids)},
            )

        started = time.monotonic()
        snapshot = await self._scanner.snapshot(request.workspace_id)
        limitations: list[str] = []
        executed: tuple[TestEvidence, ...] = ()
        if request.run_tests and self._test_runner is not None:
            try:
                executed = await self._test_runner.run(snapshot)
            except VerityError as exc:
                if exc.code == "TIMEOUT":
                    raise
                limitations.append(f"test runner unavailable: {exc.message}")

        results: list[RequirementCoverage] = []
        for requirement_id in ids:
            if time.monotonic() - started > _DEADLINE_BUDGET:
                results.append(RequirementCoverage(
                    requirement_id=requirement_id,
                    status=CoverageStatus.UNCERTAIN,
                    reason="coverage deadline exceeded before evaluation",
                    limitations=["coverage deadline exceeded"],
                ))
                limitations.append("coverage deadline exceeded")
                continue
            requirement = await self._lookup(requirement_id)
            try:
                code, tests = await self._retriever.find(requirement, snapshot)
                tests = self._merge_outcomes(tests, executed)
                results.append(
                    self._evaluator.evaluate(
                        requirement, code, tests, request.run_tests
                    )
                )
            except VerityError as exc:
                if exc.code == "COVERAGE_UNAVAILABLE":
                    results.append(RequirementCoverage(
                        requirement_id=requirement_id,
                        status=CoverageStatus.UNCERTAIN,
                        reason="workspace file changed during evaluation",
                        limitations=["workspace_changed"],
                    ))
                    limitations.append("workspace changed during evaluation")
                else:
                    raise

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

        report = CoverageResult(
            schema_version="1.0.0",
            coverage_id=str(uuid4()),
            workspace_id=request.workspace_id,
            workspace_revision=snapshot.revision,
            inspected_at=_now_utc(),
            results=results,
            limitations=limitations,
        )
        if self._store is not None:
            # One immutable report row per run (contract 12/16).
            await self._store.save_coverage(report)
        return report

    @staticmethod
    def _merge_outcomes(
        retrieved: tuple[TestEvidence, ...],
        executed: tuple[TestEvidence, ...],
    ) -> tuple[TestEvidence, ...]:
        """Apply allowlisted runner outcomes to retrieved tests by path.

        Unmapped runner evidence is dropped (never proof for an unrelated
        requirement); retrieved tests without an executed outcome stay
        ``not_run`` (contract 12).
        """
        if not executed:
            return retrieved
        by_path = {e.path: e for e in executed}
        return tuple(
            TestEvidence(
                path=e.path,
                start_line=e.start_line,
                end_line=e.end_line,
                excerpt=e.excerpt,
                basis=e.basis,
                outcome=by_path[e.path].outcome
                if e.path in by_path else e.outcome,
            )
            for e in retrieved
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