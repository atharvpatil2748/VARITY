"""Evidence-backed coverage status rules (contract 12, N1/N4).

Statuses are derived only from inspectable evidence spans, never from a
caller's or agent's claim:

* ``IMPLEMENTED`` - credible implementation plus test evidence (none
  failing) or a documented static proof for every essential clause.
* ``PARTIAL`` - credible implementation exists but test support or a
  clause is missing, or a relevant test failed.
* ``MISSING`` - the scan produced candidate matches but none were
  credible implementation (e.g. only comments naming the requirement).
* ``UNCERTAIN`` - no analyzable evidence at all, tests without
  implementation, failed test runner, or changed workspace: honest
  uncertainty, never invented coverage.

A comment containing ``REQ-001`` alone is never implementation
evidence (contract 12).
"""

from __future__ import annotations

from ..models import (
    CodeEvidence,
    CoverageStatus,
    Requirement,
    RequirementCoverage,
    TestEvidence,
    TestOutcome,
)

#: Line-level comment prefixes for languages supported in v1.
_COMMENT_PREFIXES = ("#", "//", "--", ";", "/*", "*")


def is_credential_excerpt(excerpt: str) -> bool:
    """True when the excerpt contains at least one non-comment line."""
    for line in excerpt.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith(_COMMENT_PREFIXES):
            return True
    return False


def credible_implementation(evidence: CodeEvidence) -> bool:
    """Contract 12 false-positive rule: comment-only matches never count."""
    return is_credential_excerpt(evidence.excerpt)


class RequirementEvaluator:
    """Contract 16 protocol: one verdict from evidence only."""

    def evaluate(
        self,
        requirement: Requirement,
        code: tuple[CodeEvidence, ...],
        tests: tuple[TestEvidence, ...],
        run_tests: bool,
    ) -> RequirementCoverage:
        raise NotImplementedError


class DefaultRequirementEvaluator(RequirementEvaluator):
    """Deterministic N1 evaluator implementing the contract-12 rule table."""

    def evaluate(
        self,
        requirement: Requirement,
        code: tuple[CodeEvidence, ...],
        tests: tuple[TestEvidence, ...],
        run_tests: bool,
    ) -> RequirementCoverage:
        credible = tuple(e for e in code if credible_implementation(e))
        failed = tuple(
            t for t in tests if t.outcome in (TestOutcome.FAILED, TestOutcome.ERROR)
        )
        limitations: list[str] = []
        if not credible:
            if code:
                # Candidates existed but all were comment-only matches:
                # the scan completed; this is a true miss, not uncertainty.
                status = CoverageStatus.MISSING
                reason = (
                    "scan completed; only comment matches name this "
                    "requirement, no credible implementation span"
                )
            elif tests:
                status = CoverageStatus.UNCERTAIN
                reason = "test evidence found without implementation evidence"
            else:
                status = CoverageStatus.UNCERTAIN
                reason = (
                    "no analyzable implementation or test evidence; cannot "
                    "distinguish missing from hidden"
                )
        else:
            static_proof = any(
                e.basis.value == "static_check" for e in credible
            )
            if failed:
                status = CoverageStatus.PARTIAL
                reason = (
                    f"credible implementation exists but {len(failed)} "
                    "relevant test(s) failed or errored"
                )
            elif tests:
                status = CoverageStatus.IMPLEMENTED
                reason = "credible implementation with non-failing test evidence"
            elif static_proof:
                status = CoverageStatus.IMPLEMENTED
                reason = "credible implementation with documented static proof"
            else:
                status = CoverageStatus.PARTIAL
                reason = "credible implementation without test support"
            if tests and run_tests and all(
                t.outcome is TestOutcome.NOT_RUN for t in tests
            ):
                limitations.append("tests were requested but not executed")
        if not tests and credible:
            limitations.append("no test evidence found for this requirement")
        return RequirementCoverage(
            requirement_id=requirement.requirement_id,
            status=status,
            reason=reason,
            implementation=list(credible),
            tests=list(tests),
            limitations=limitations,
        )