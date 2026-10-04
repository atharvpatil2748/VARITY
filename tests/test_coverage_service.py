"""N1 coverage service tests: orchestration, revision drift, fakes."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from verity.coverage import (
    DefaultRequirementEvaluator,
    FakeCodeEvidenceRetriever,
    FakeCoverageService,
    FakeSnapshotScanner,
    WorkspaceFile,
    manifest_revision,
)
from verity.coverage.service import DefaultCoverageService
from verity.errors import VerityError
from verity.models import CoverageRequest, CoverageStatus

from test_coverage_evaluator import (
    FIXTURE_ROOT,
    code_evidence,
    make_requirement,
    make_test_evidence,
)


def workspace_file(relative: str) -> WorkspaceFile:
    data = (FIXTURE_ROOT / relative).read_bytes()
    return WorkspaceFile(relative_path=relative,
                         content_sha256=hashlib.sha256(data).hexdigest(),
                         size=len(data))


def make_request(requirement_ids: list[str], workspace_id: str) -> CoverageRequest:
    return CoverageRequest.from_dict(
        {"requirement_ids": requirement_ids,
         "workspace_id": workspace_id, "run_tests": False}
    )


def test_snapshot_revision_deterministic_and_order_independent() -> None:
    files = (workspace_file("src/refund_window.py"),
             workspace_file("src/duplicate_guard.py"))
    assert manifest_revision(files) == manifest_revision(files[::-1])
    assert manifest_revision(files) != manifest_revision(files[:1])


def run(coro):
    return asyncio.run(coro)


def test_service_orchestrates_pipeline_in_request_order() -> None:
    reqs = {
        "REQ-002": make_requirement("REQ-002"),
        "REQ-003": make_requirement("REQ-003"),
    }
    scanner = FakeSnapshotScanner(snapshots={"demo": (
        workspace_file("src/duplicate_guard.py"),
        workspace_file("src/window_policy.py"),
        workspace_file("tests/check_window_policy.py"),
    )})
    retriever = FakeCodeEvidenceRetriever({
        reqs["REQ-002"].requirement_id: (
            (code_evidence("src/duplicate_guard.py", 1, 6,
                           "def reject_duplicate_refund():\n    pass\n"),),
            ()),
        reqs["REQ-003"].requirement_id: (
            (code_evidence("src/window_policy.py", 1, 3,
                           "def refund_window_days():\n    return 30\n",
                           "symbol_match"),),
            (make_test_evidence("tests/check_window_policy.py",
                           "def check_refund_window_days():\n    pass\n"),),
        ),
    })

    async def lookup(requirement_id: str):
        for req in reqs.values():
            if req.requirement_id == requirement_id:
                return req
        raise VerityError("REQUIREMENT_NOT_FOUND",
                          f"requirement {requirement_id!r} not found")

    service = DefaultCoverageService(
        scanner=scanner, retriever=retriever,
        evaluator=DefaultRequirementEvaluator(), requirement_lookup=lookup,
    )
    request = make_request(
        [reqs["REQ-003"].requirement_id, reqs["REQ-002"].requirement_id], "demo"
    )
    result = run(service.check(request))
    assert result.schema_version == "1.0.0"
    assert [r.status for r in result.results] == [
        CoverageStatus.IMPLEMENTED,  # REQ-003: impl + test evidence
        CoverageStatus.PARTIAL,      # REQ-002: impl without tests
    ]
    assert result.results[0].requirement_id == reqs["REQ-003"].requirement_id


def test_changed_workspace_downgrades_to_uncertain() -> None:
    req = make_requirement("REQ-007")
    original = (workspace_file("src/window_policy.py"),)
    changed = (workspace_file("src/window_policy.py"),
               workspace_file("src/duplicate_guard.py"))
    scanner = FakeSnapshotScanner(
        snapshots={"demo": original}, mutate_after={"demo": changed},
    )
    retriever = FakeCodeEvidenceRetriever({
        req.requirement_id: (
            (code_evidence("src/window_policy.py", 1, 3,
                           "def refund_window_days():\n    return 30\n",
                           "symbol_match"),),
            (),
        )
    })

    async def lookup(requirement_id: str):
        return req

    service = DefaultCoverageService(
        scanner=scanner, retriever=retriever,
        evaluator=DefaultRequirementEvaluator(), requirement_lookup=lookup,
    )
    result = run(service.check(make_request([req.requirement_id], "demo")))
    assert result.results[0].status is CoverageStatus.UNCERTAIN
    assert "workspace_changed" in result.results[0].limitations
    assert "workspace changed during evaluation" in result.limitations


def test_fake_coverage_service_returns_canned_outcomes() -> None:
    req = make_requirement("REQ-008")
    canned = DefaultRequirementEvaluator().evaluate(
        req,
        (code_evidence("src/x.py", 1, 2, "def f():\n    return 1\n"),),
        (), run_tests=False,
    )
    fake = FakeCoverageService(outcomes={req.requirement_id: canned})
    result = run(fake.check(make_request([req.requirement_id], "fake")))
    assert result.results[0] == canned
    assert result.limitations == [
        "fake coverage service: no workspace was scanned"
    ]


def test_service_rejects_unknown_workspace() -> None:
    req = make_requirement("REQ-009")

    async def lookup(requirement_id: str):
        return req

    service = DefaultCoverageService(
        scanner=FakeSnapshotScanner(snapshots={"other": ()}),
        retriever=FakeCodeEvidenceRetriever({}),
        evaluator=DefaultRequirementEvaluator(),
        requirement_lookup=lookup,
    )
    try:
        run(service.check(make_request([req.requirement_id], "demo")))
        raised = None
    except VerityError as exc:
        raised = exc
    assert raised is not None and raised.code == "WORKSPACE_NOT_FOUND"
