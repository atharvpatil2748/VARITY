"""Evidence-backed coverage status evaluator.

Contract: Docs/contracts/12_VERITY_COVERAGE_CONTRACT.md. Owner Vanashree.

Status rules: ``IMPLEMENTED`` needs direct implementation evidence plus
each essential acceptance criterion tested or statically provable;
``MISSING`` requires a completed scan with no credible match; ambiguous
cases default to ``UNCERTAIN``. A passing test never proves the whole
requirement and a comment naming ``REQ-003`` is not implementation.
"""

from __future__ import annotations


def evaluate(requirement: object, code: object, tests: object) -> str:
    """Return one of IMPLEMENTED/PARTIAL/MISSING/UNCERTAIN. Skeleton."""
    raise NotImplementedError("coverage evaluator: scheduled Phase 11, contract 12")