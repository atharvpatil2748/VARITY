"""N1 evaluator tests: contract-12 status rules + four-case fixture.

Fixture cases (contract 12 / roadmap N1):
  REQ-001 comment-only match      -> MISSING (comment is never implementation)
  REQ-002 implemented, no tests   -> PARTIAL
  REQ-003 implemented + test      -> IMPLEMENTED
  REQ-004 unsupported .bin file   -> UNCERTAIN
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

import pytest

from verity.coverage.evaluator import credible_implementation
from verity.coverage import DefaultRequirementEvaluator
from verity.errors import VerityError
from verity.ids import make_requirement_id
from verity.models import (
    CodeEvidence,
    CoverageStatus,
    Locator,
    Requirement,
    TestEvidence,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "coverage_workspace"

SOURCE_ID = UUID("24da624f-7fd0-41ea-a49b-8449cbb179d9")
DOCUMENT_ID = "ebc2352e-ff9c-4167-b11a-1e30d550411d"
VERSION_ID = "129dcd06-1ba1-4f0c-bf7e-c678f905b624"

LOCATOR = Locator.from_dict(
    {
        "source_id": str(SOURCE_ID),
        "document_id": DOCUMENT_ID,
        "version_id": VERSION_ID,
        "source_path": "specs/payments.md",
        "page": None,
        "start_line": 10,
        "end_line": 12,
        "start_offset": None,
        "end_offset": None,
        "heading_path": ["Requirements"],
    }
)


def make_requirement(local_id: str) -> Requirement:
    return Requirement.from_dict(
        {
            "schema_version": "1.0.0",
            "requirement_id": make_requirement_id(SOURCE_ID, local_id),
            "local_id": local_id,
            "source_id": str(SOURCE_ID),
            "document_id": DOCUMENT_ID,
            "version_id": VERSION_ID,
            "title": f"Fixture requirement {local_id}",
            "text": f"Fixture normative text for {local_id}.",
            "chunk_id": "chk_" + "1" * 64,
            "evidence_id": "ev_" + "2" * 64,
            "locator": LOCATOR.to_dict(),
        }
    )


def code_evidence(path: str, start: int, end: int, excerpt: str,
                  basis: str = "text_match") -> CodeEvidence:
    return CodeEvidence.from_dict(
        {"path": path, "start_line": start, "end_line": end,
         "excerpt": excerpt, "basis": basis}
    )


def make_test_evidence(path: str, excerpt: str, outcome: str = "not_run") -> TestEvidence:
    return TestEvidence.from_dict(
        {"path": path, "start_line": 1, "end_line": 4,
         "excerpt": excerpt, "basis": "text_match", "outcome": outcome}
    )


def read(relative: str) -> str:
    return (FIXTURE_ROOT / relative).read_text(encoding="utf-8")


def test_comment_only_excerpt_is_not_credible() -> None:
    evidence = code_evidence("src/refund_window.py", 1, 3,
                             read("src/refund_window.py"))
    assert not credible_implementation(evidence)


def test_real_code_excerpt_is_credible() -> None:
    evidence = code_evidence("src/duplicate_guard.py", 1, 6,
                             read("src/duplicate_guard.py"))
    assert credible_implementation(evidence)


@pytest.mark.parametrize(
    ("local_id", "expected"),
    [
        ("REQ-001", CoverageStatus.MISSING),
        ("REQ-002", CoverageStatus.PARTIAL),
        ("REQ-003", CoverageStatus.IMPLEMENTED),
        ("REQ-004", CoverageStatus.UNCERTAIN),
    ],
)
def test_four_case_fixture_statuses(local_id: str, expected: CoverageStatus) -> None:
    evaluator = DefaultRequirementEvaluator()
    requirement = make_requirement(local_id)

    if local_id == "REQ-001":
        code = (code_evidence("src/refund_window.py", 1, 3,
                              read("src/refund_window.py")),)
        tests: tuple = ()
    elif local_id == "REQ-002":
        code = (code_evidence("src/duplicate_guard.py", 1, 6,
                              read("src/duplicate_guard.py")),)
        tests = ()
    elif local_id == "REQ-003":
        code = (code_evidence("src/window_policy.py", 1, 3,
                              read("src/window_policy.py"), "symbol_match"),)
        tests = (make_test_evidence("tests/check_window_policy.py",
                               read("tests/check_window_policy.py")),)
    else:  # REQ-004: unsupported .bin, no analyzable evidence
        code = ()
        tests = ()

    coverage = evaluator.evaluate(requirement, code, tests, run_tests=False)
    assert coverage.status is expected
    assert coverage.reason
    if local_id == "REQ-001":
        assert coverage.implementation == []


def test_failing_test_never_yields_implemented() -> None:
    evaluator = DefaultRequirementEvaluator()
    requirement = make_requirement("REQ-005")
    code = (code_evidence("src/refund_api.py", 5, 9,
                           "def refund():\n    return 30\n"),)
    tests = (make_test_evidence("tests/check_refund.py",
                           "def test_refund():\n    assert refund() == 31\n",
                           outcome="failed"),)
    coverage = evaluator.evaluate(requirement, code, tests, run_tests=True)
    assert coverage.status is CoverageStatus.PARTIAL


def test_static_proof_without_tests_can_be_implemented() -> None:
    evaluator = DefaultRequirementEvaluator()
    requirement = make_requirement("REQ-006")
    code = (code_evidence("src/config.py", 1, 2,
                          "REFUND_WINDOW_DAYS = 30\n", "static_check"),)
    coverage = evaluator.evaluate(requirement, code, (), run_tests=False)
    assert coverage.status is CoverageStatus.IMPLEMENTED


def test_unsafe_relative_path_rejected() -> None:
    from verity.coverage import WorkspaceFile

    with pytest.raises(VerityError) as exc_info:
        WorkspaceFile(relative_path="../escape.py", content_sha256="0" * 64, size=10)
    assert exc_info.value.code == "INVALID_REQUEST"
