"""Spec parser contract tests (contract 04, P2 acceptance).

Covers: exact parsed drafts for the shared ``payments.md`` fixture,
duplicate/dangling identifiers with line-numbered ``SPEC_VALIDATION_ERROR``,
front matter strictness, ``VERSION_UNSUPPORTED``, heading grammar, empty
text, nested bullets and unrecognized child headings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from verity.ingestion._compat import VerityError
from verity.ingestion.spec import SpecParser, looks_like_spec

FIXTURES = TESTS_DIR / "fixtures" / "contracts_v1"

FRONT = (
    "---\n"
    'verity_spec: "1.0.0"\n'
    "source_key: payments-api\n"
    "project: payment-service\n"
    "title: Test Spec\n"
    'spec_version: "1.0"\n'
    "---\n"
)


def make_spec(body: str, front: str = FRONT) -> bytes:
    return (front + "\n" + body).encode("utf-8")


def parse(data: bytes, filename: str = "test.md") -> dict:
    return SpecParser().parse(data, filename, "text/markdown")


def test_payments_fixture_parses_to_expected_drafts() -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    expected = json.loads((FIXTURES / "expected_payments_parsed.json").read_text("utf-8"))
    assert parse(data, "payments.md") == expected


def test_payments_fixture_requirement_drafts() -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    doc = parse(data, "payments.md")
    reqs = {r["local_id"]: r for r in doc["spec_requirements"]}
    assert set(reqs) == {"REQ-001", "REQ-002", "REQ-003"}
    assert reqs["REQ-001"]["title"] == "Refund window"
    assert reqs["REQ-001"]["text"] == (
        "Refund requests MUST be accepted only within 30 days."
    )
    assert reqs["REQ-001"]["constraints"] == [
        "A later request MUST return REFUND_WINDOW_EXPIRED."
    ]
    assert reqs["REQ-001"]["edge_cases"] == [
        "A request at exactly 30 days is accepted."
    ]
    assert reqs["REQ-001"]["api_refs"] == ["API-001"]
    assert reqs["REQ-001"]["acceptance_local_ids"] == ["AC-001"]
    assert reqs["REQ-001"]["block_start"] < reqs["REQ-001"]["block_end"]
    entities = {e["local_id"]: e for e in doc["spec_entities"]}
    assert entities["API-001"]["kind"] == "api_definition"
    assert entities["API-001"]["reference_ids"] == []
    assert entities["AC-001"]["kind"] == "acceptance_criterion"
    assert entities["AC-001"]["reference_ids"] == ["REQ-001"]


def test_blocks_contiguous_ordinals_and_line_spans() -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    doc = parse(data, "payments.md")
    for index, block in enumerate(doc["blocks"]):
        assert block["ordinal"] == index
        assert block["page"] is None
        assert block["start_line"] >= 1
        assert block["start_line"] <= block["end_line"]


def test_invalid_fixtures_raise_line_numbered_errors() -> None:
    expected = json.loads((FIXTURES / "expected_invalid_specs_errors.json").read_text("utf-8"))
    for entry in expected:
        data = (FIXTURES / entry["fixture"]).read_bytes()
        with pytest.raises(VerityError) as excinfo:
            parse(data, entry["fixture"])
        error = excinfo.value
        assert error.code == entry["code"]
        assert error.details["line"] == entry["line"]
        assert entry["message_contains"] in error.message


def test_unsupported_spec_version() -> None:
    front = FRONT.replace('verity_spec: "1.0.0"', 'verity_spec: "2.0.0"')
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec("# Requirements\n## REQ-001: A\nText.\n", front))
    assert excinfo.value.code == "VERSION_UNSUPPORTED"
    assert excinfo.value.details["line"] == 2


def test_unknown_front_matter_key_rejected() -> None:
    front = FRONT.replace("\n---\n", "\nowner: someone\n---\n")
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec("# Requirements\n## REQ-001: A\nText.\n", front))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert excinfo.value.details["line"] == 7


def test_missing_front_matter_key_rejected() -> None:
    front = FRONT.replace("project: payment-service\n", "")
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec("# Requirements\n## REQ-001: A\nText.\n", front))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert "missing project" in excinfo.value.message


def test_malformed_requirement_heading_rejected() -> None:
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec("# Requirements\n## REQ-01: Too short\nText.\n"))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert excinfo.value.details["line"] == 10


def test_empty_requirement_text_rejected() -> None:
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec("# Requirements\n## REQ-001: Nothing\n\n## REQ-002: Ok\nText.\n"))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert "nonempty normative paragraph" in excinfo.value.message


def test_nested_bullets_rejected() -> None:
    body = (
        "# Requirements\n## REQ-001: A\nText.\n\n### Constraints\n"
        "- top level\n  - nested\n"
    )
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec(body))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert "nested bullets" in excinfo.value.message


def test_unrecognized_child_heading_rejected() -> None:
    body = "# Requirements\n## REQ-001: A\nText.\n\n### Notes\n- x\n"
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec(body))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert "unrecognized structured child heading" in excinfo.value.message


def test_subsection_order_enforced() -> None:
    body = (
        "# Requirements\n## REQ-001: A\nText.\n\n### Edge cases\n- x\n\n"
        "### Constraints\n- y\n"
    )
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec(body))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert "out of order" in excinfo.value.message


def test_ac_missing_references_line_rejected() -> None:
    body = (
        "# Requirements\n## REQ-001: A\nText.\n\n"
        "# Acceptance criteria\n## AC-001: B\nSome text.\n"
    )
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec(body))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert "References: REQ-..." in excinfo.value.message


def test_ac_malformed_references_line_rejected() -> None:
    body = (
        "# Requirements\n## REQ-001: A\nText.\n\n"
        "# Acceptance criteria\n## AC-001: B\nSome text.\nReferences: nonsense\n"
    )
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec(body))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert "malformed references line" in excinfo.value.message


def test_dangling_api_reference_rejected() -> None:
    body = (
        "# Requirements\n## REQ-001: A\nText.\n\n### References\n- API-002\n"
    )
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec(body))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"
    assert "dangling reference" in excinfo.value.message
    assert excinfo.value.details["line"] == 14


def test_missing_requirements_section_rejected() -> None:
    with pytest.raises(VerityError) as excinfo:
        parse(make_spec("# References\n- some link\n"))
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"


def test_looks_like_spec_detection() -> None:
    assert looks_like_spec((FIXTURES / "payments.md").read_bytes()) is True
    assert looks_like_spec((FIXTURES / "architecture.md").read_bytes()) is False
    assert looks_like_spec(b"---\nbroken\n---\n") is False