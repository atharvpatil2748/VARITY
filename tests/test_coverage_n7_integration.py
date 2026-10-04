"""N7 integration tests: real scanner + retriever + evaluator + service.

Contract 12 acceptance: four statuses against real fixture files, path
denial, changed snapshot, missing root, test unavailable, allowlisted
test runner outcomes and one immutable persisted report.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from verity.config import VerityConfig, WorkspaceConfig
from verity.coverage import (
    AllowlistedTestRunner,
    DefaultCoverageService,
    DefaultRequirementEvaluator,
    RealCodeEvidenceRetriever,
    RealWorkspaceScanner,
)
from verity.errors import VerityError
from verity.ids import make_requirement_id
from verity.models import CoverageRequest, CoverageStatus, Requirement

from test_coverage_evaluator import (
    DOCUMENT_ID,
    FIXTURE_ROOT,
    LOCATOR,
    SOURCE_ID,
    VERSION_ID,
)
from test_coverage_scanner import config_with

run = asyncio.run


def make_req(local_id: str, text: str) -> Requirement:
    return Requirement.from_dict({
        "schema_version": "1.0.0",
        "requirement_id": make_requirement_id(SOURCE_ID, local_id),
        "local_id": local_id,
        "source_id": str(SOURCE_ID),
        "document_id": DOCUMENT_ID,
        "version_id": VERSION_ID,
        "title": f"{local_id} fixture requirement",
        "text": text,
        "chunk_id": "chk_" + "1" * 64,
        "evidence_id": "ev_" + "2" * 64,
        "locator": LOCATOR.to_dict(),
    })


# Four-case fixture requirements (contract 12): identifiers in the text
# are the only terms that may justify candidate spans.
REQS = {
    "REQ-001": make_req(
        "REQ-001", "Refund requests MUST be accepted only within 30 days."),
    "REQ-002": make_req(
        "REQ-002",
        "Duplicate refund requests MUST be rejected by reject_duplicate_refund()."),
    "REQ-003": make_req(
        "REQ-003",
        "The refund_window_days() helper MUST return the 30-day window."),
    "REQ-004": make_req(
        "REQ-004",
        "Legacy assets MUST be migrated via legacy_asset_pipeline()."),
}


class RecordingStore:
    """Minimal _CoverageStore recording save_coverage calls."""

    def __init__(self, requirements: dict[str, Requirement]) -> None:
        self._requirements = requirements
        self.saved: list = []

    async def get_requirement(self, requirement_id: str):
        return self._requirements.get(requirement_id)

    async def save_coverage(self, result) -> None:
        self.saved.append(result)


def build_service(root: Path, test_command: tuple = (), store=None):
    config = config_with(root)
    if test_command:
        workspace = WorkspaceConfig(
            workspace_id="demo", root=root, test_command=test_command,
            exclude=(".git", ".venv", "node_modules", "dist"),
        )
        config = VerityConfig(
            config_dir=Path("."), workspaces={"demo": workspace}
        )
    scanner = RealWorkspaceScanner(config)
    retriever = RealCodeEvidenceRetriever(scanner)

    async def lookup(requirement_id: str):
        return REQS[
            next(k for k, v in REQS.items() if v.requirement_id == requirement_id)
        ]

    runner = AllowlistedTestRunner(config.workspace("demo")) if test_command else None
    return DefaultCoverageService(
        scanner=scanner, retriever=retriever,
        evaluator=DefaultRequirementEvaluator(), requirement_lookup=lookup,
        store=store, test_runner=runner,
    )


def request(ids: list[str], run_tests: bool = False) -> CoverageRequest:
    return CoverageRequest.from_dict({
        "requirement_ids": ids,
        "workspace_id": "demo",
        "run_tests": run_tests,
    })


def test_four_case_statuses_end_to_end() -> None:
    store = RecordingStore(REQS)
    service = build_service(FIXTURE_ROOT, store=store)
    ids = [REQS[k].requirement_id for k in
           ("REQ-001", "REQ-002", "REQ-003", "REQ-004")]
    result = run(service.check(request(ids)))
    statuses = [r.status for r in result.results]
    assert statuses == [
        CoverageStatus.MISSING,      # REQ-001: comment-only mentions
        CoverageStatus.PARTIAL,      # REQ-002: real code, no tests
        CoverageStatus.IMPLEMENTED,  # REQ-003: real code + test evidence
        CoverageStatus.UNCERTAIN,    # REQ-004: unsupported, unanalyzable
    ]
    assert [r.requirement_id for r in result.results] == ids  # order kept
    assert store.saved and store.saved[0].coverage_id == result.coverage_id
    assert result.workspace_revision != "0" * 64


def test_read_lines_rejects_non_member_and_traversal_paths() -> None:
    scanner = RealWorkspaceScanner(config_with(FIXTURE_ROOT))

    async def call():
        snapshot = await scanner.snapshot("demo")
        for bad in ("unknown.py", "src/../window_policy.py", "src"):
            with pytest.raises(VerityError) as exc_info:
                await scanner.read_lines(snapshot, bad, 1, 3)
            assert exc_info.value.code == "INVALID_REQUEST"
        text = await scanner.read_lines(snapshot, "src/window_policy.py", 1, 3)
        assert "refund_window_days" in text

    run(call())


def test_read_lines_hash_mismatch_is_coverage_unavailable(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    shutil.copytree(FIXTURE_ROOT, workspace)
    scanner = RealWorkspaceScanner(config_with(workspace))

    async def call():
        snapshot = await scanner.snapshot("demo")
        (workspace / "src" / "window_policy.py").write_text(
            "def refund_window_days():\n    return 31\n", encoding="utf-8"
        )
        with pytest.raises(VerityError) as exc_info:
            await scanner.read_lines(snapshot, "src/window_policy.py", 1, 3)
        assert exc_info.value.code == "COVERAGE_UNAVAILABLE"

    run(call())


def test_service_maps_mid_read_change_to_uncertain() -> None:
    class DriftingRetriever:
        async def find(self, requirement, snapshot):
            raise VerityError("COVERAGE_UNAVAILABLE", "file changed")

    scanner = RealWorkspaceScanner(config_with(FIXTURE_ROOT))

    async def lookup(requirement_id: str):
        return REQS["REQ-003"]

    service = DefaultCoverageService(
        scanner=scanner, retriever=DriftingRetriever(),
        evaluator=DefaultRequirementEvaluator(), requirement_lookup=lookup,
    )
    result = run(service.check(request([REQS["REQ-003"].requirement_id])))
    assert result.results[0].status is CoverageStatus.UNCERTAIN
    assert "workspace_changed" in result.results[0].limitations


def test_missing_root_is_workspace_not_found() -> None:
    service = build_service(Path("does/not/exist"))
    with pytest.raises(VerityError) as exc_info:
        run(service.check(request([REQS["REQ-003"].requirement_id])))
    assert exc_info.value.code == "WORKSPACE_NOT_FOUND"


def test_run_tests_without_command_never_implemented() -> None:
    """Contract 12: requested-but-unavailable tests cannot yield
    IMPLEMENTED; the limitation is recorded honestly."""
    service = build_service(FIXTURE_ROOT)  # no test_command -> no runner
    result = run(service.check(
        request([REQS["REQ-003"].requirement_id], run_tests=True)))
    assert result.results[0].status is not CoverageStatus.IMPLEMENTED


def test_run_tests_allowlisted_pass_can_implement() -> None:
    import sys

    command = (
        sys.executable, "-c",
        "print('tests/check_window_policy.py:1 passed')",
    )
    service = build_service(FIXTURE_ROOT, test_command=command)
    result = run(service.check(
        request([REQS["REQ-003"].requirement_id], run_tests=True)))
    coverage = result.results[0]
    assert coverage.status is CoverageStatus.IMPLEMENTED
    assert any(t.outcome.value == "passed" for t in coverage.tests)


def test_run_tests_failing_command_never_implemented() -> None:
    import sys

    command = (
        sys.executable, "-c",
        "import sys; print('tests/check_window_policy.py:1 failed'); sys.exit(1)",
    )
    service = build_service(FIXTURE_ROOT, test_command=command)
    result = run(service.check(
        request([REQS["REQ-003"].requirement_id], run_tests=True)))
    coverage = result.results[0]
    assert coverage.status is not CoverageStatus.IMPLEMENTED
    assert any(t.outcome.value == "failed" for t in coverage.tests)


def test_runner_output_unmappable_is_not_proof() -> None:
    """Contract 12: unmappable output never proves an unrelated test."""
    import sys

    command = (sys.executable, "-c", "print('all good somewhere else')")
    service = build_service(FIXTURE_ROOT, test_command=command)
    result = run(service.check(
        request([REQS["REQ-003"].requirement_id], run_tests=True)))
    coverage = result.results[0]
    assert coverage.status is CoverageStatus.UNCERTAIN
    assert all(t.outcome.value == "not_run" for t in coverage.tests)


def test_request_validation_ids_unique_and_bounded() -> None:
    service = build_service(FIXTURE_ROOT)
    rid = REQS["REQ-003"].requirement_id
    with pytest.raises(VerityError) as exc_info:
        run(service.check(request([rid, rid])))
    assert exc_info.value.code == "INVALID_REQUEST"
    with pytest.raises(VerityError) as exc_info:
        run(service.check(request([f"req_{i:064d}" for i in range(51)])))
    assert exc_info.value.code == "INVALID_REQUEST"