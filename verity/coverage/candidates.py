"""Code/test evidence retriever protocol (contract 16), N1 fake and N3 real.

Contract 12/16 (D2 amendment, change log 1.0.4): the retriever never
opens workspace files; every line of text comes from the injected
``WorkspaceScanner.read_lines``. Candidates are bounded and comment-only
matches are emitted so the evaluator can report ``MISSING`` honestly.
"""

from __future__ import annotations

import re

from ..models import (
    CodeEvidence,
    EvidenceBasis,
    Requirement,
    TestEvidence,
    TestOutcome,
)
from .workspace import WorkspaceScanner, WorkspaceSnapshot

#: Candidate bounds per requirement (contract 12: bounded evidence).
MAX_CODE_SPANS = 10
MAX_TEST_SPANS = 5
#: Lines per scanner read window (D2 caps each call at 200/8000).
READ_WINDOW_LINES = 50
#: Max lines merged into one candidate span.
SPAN_MAX_LINES = 12
#: Gap (lines) tolerated inside one span.
SPAN_GAP = 2

_SYMBOL_LINE_RE = re.compile(
    r"^\s*(def|class|function|fn|func|const|let|var|type|interface|impl|struct|"
    r"async\s+def)\b"
)
_TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|__tests__)(/|$)|(^|/)test_[^/]+$|_test\.[^/]+$|"
    r"(^|/)check_[^/]+$|\.(test|spec)\.[^/]+$"
)
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_STOPWORDS = frozenset({
    "must", "shall", "should", "only", "within", "when", "where", "which",
    "that", "this", "the", "and", "for", "are", "not", "with", "from",
    "returns", "return", "request", "requests", "requirement", "case",
    "cases", "given", "then", "accept", "accepted", "support", "supported",
})


def _search_terms(requirement: Requirement) -> list[str]:
    """Deterministic terms: local_id plus distinctive identifiers.

    Plain prose words are too fuzzy for evidence claims (contract 12:
    comment-only name matches are traps, and unrelated code must not be
    credited); identifiers (snake_case / CamelCase / ACRONYMS) and the
    authored local_id are the terms that can justify a candidate span.
    """
    terms: list[str] = [requirement.local_id]
    local_id = requirement.local_id.lower()
    text = f"{requirement.title} {requirement.text}"
    for token in _WORD_RE.findall(text):
        if len(token) < 3 or token.lower() in _STOPWORDS:
            continue
        # The tokenizer splits REQ-001 into REQ/001; a bare prefix like
        # REQ or API would match every "req_" word and cross-credit
        # unrelated code (contract 12 false-positive trap).
        if token.lower() in local_id:
            continue
        is_identifier = (
            "_" in token
            or token.isupper()                       # ACRONYM
            or re.search(r"[a-z][A-Z]", token)       # camelCase / PascalCase
        )
        if is_identifier:
            terms.append(token)
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        lowered = term.lower()
        if lowered not in seen:
            seen.add(lowered)
            unique.append(term)
    return unique[:25]


def _is_test_path(relative_path: str) -> bool:
    return bool(_TEST_PATH_RE.search(relative_path.replace("\\", "/")))


def _line_matches(line: str, terms: list[str]) -> bool:
    lowered = line.lower()
    return any(term.lower() in lowered for term in terms)


def _spans_from_lines(
    matches: dict[int, str],
) -> list[tuple[int, int, str]]:
    """Merge matched line numbers into bounded contiguous spans."""
    if not matches:
        return []
    ordered = sorted(matches)
    spans: list[tuple[int, int, str]] = []
    start = prev = ordered[0]
    for number in ordered[1:]:
        if number - prev <= SPAN_GAP and number - start < SPAN_MAX_LINES:
            prev = number
            continue
        spans.append((start, prev, ""))
        start = prev = number
    spans.append((start, prev, ""))
    return spans[:MAX_CODE_SPANS + MAX_TEST_SPANS]


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


class RealCodeEvidenceRetriever(CodeEvidenceRetriever):
    """N3: real candidate search using only scanner-owned text reads.

    Contract 12: the retriever never opens files; every line of text
    comes from ``WorkspaceScanner.read_lines`` (D2, change log 1.0.4).
    Candidates are bounded; comment-only matches are still emitted so the
    evaluator can report ``MISSING`` honestly instead of ``UNCERTAIN``.
    """

    def __init__(self, scanner: WorkspaceScanner) -> None:
        self._scanner = scanner

    async def find(
        self, requirement: Requirement, snapshot: WorkspaceSnapshot
    ) -> tuple[tuple[CodeEvidence, ...], tuple[TestEvidence, ...]]:
        terms = _search_terms(requirement)
        code: list[CodeEvidence] = []
        tests: list[TestEvidence] = []
        for entry in snapshot.files:
            if len(code) >= MAX_CODE_SPANS and len(tests) >= MAX_TEST_SPANS:
                break
            lines = await self._read_all(snapshot, entry.relative_path)
            if not lines:
                continue
            matched = {
                number: line
                for number, line in lines.items()
                if _line_matches(line, terms)
            }
            if not matched:
                continue
            is_test = _is_test_path(entry.relative_path)
            for start, end, _ in _spans_from_lines(matched):
                excerpt = "".join(
                    lines[n] for n in range(start, end + 1) if n in lines
                )[:4000]
                basis = (
                    EvidenceBasis.SYMBOL_MATCH
                    if any(_SYMBOL_LINE_RE.match(lines.get(n, ""))
                           for n in range(start, end + 1))
                    else EvidenceBasis.TEXT_MATCH
                )
                if is_test and len(tests) < MAX_TEST_SPANS:
                    tests.append(TestEvidence(
                        path=entry.relative_path,
                        start_line=start,
                        end_line=end,
                        excerpt=excerpt,
                        basis=basis,
                        outcome=TestOutcome.NOT_RUN,
                    ))
                elif not is_test and len(code) < MAX_CODE_SPANS:
                    code.append(CodeEvidence(
                        path=entry.relative_path,
                        start_line=start,
                        end_line=end,
                        excerpt=excerpt,
                        basis=basis,
                    ))
        return tuple(code), tuple(tests)

    async def _read_all(
        self, snapshot: WorkspaceSnapshot, relative_path: str
    ) -> dict[int, str]:
        """Read a whole snapshot file in bounded windows via the scanner."""
        lines: dict[int, str] = {}
        cursor = 1
        window = READ_WINDOW_LINES
        while True:
            text = await self._scanner.read_lines(
                snapshot, relative_path, cursor, cursor + window - 1
            )
            got = text.splitlines(keepends=True)
            for index, line in enumerate(got):
                lines[cursor + index] = line
            if len(got) < window:
                return lines
            cursor += window