"""VERITY transport test harness.

Schema authority: ``Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json`` is loaded
directly from Docs/ and NEVER copied into tests/ (roadmap 09 rule). All wire
fixtures are validated against the frozen $defs with Draft202012Validator,
fully offline against FakeVerityService.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
for _p in (str(ROOT), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMAS_PATH = ROOT / "Docs" / "contracts" / "21_VERITY_V1_JSON_SCHEMAS.json"
FIXTURES_DIR = TESTS_DIR / "fixtures" / "v1"

# fixture file stem -> $defs name in contract 21
FIXTURE_DEF_MAP: dict[str, str] = {
    "requirement": "Requirement",
    "search_result": "SearchResult",
    "search_result_empty": "SearchResult",
    "evidence_lookup": "EvidenceLookup",
    "coverage_result": "CoverageResult",
    "error_requirement_not_found": "Error",
    "document": "Document",
    "source": "Source",
    "ingest_result": "IngestResult",
    "list_page_documents": "ListPageDocument",
    "list_page_sources": "ListPageSource",
    "chat_session": "ChatSession",
    "chat_response": "ChatResponse",
}


def validate_wire(schemas: dict[str, Any], def_name: str, instance: Any) -> None:
    """Validate a wire object against one $def of contract 21.

    Raises jsonschema.ValidationError on the first violation.
    """
    doc = {
        "$schema": schemas["$schema"],
        "$ref": f"#/$defs/{def_name}",
        "$defs": schemas["$defs"],
    }
    Draft202012Validator.check_schema(doc)
    Draft202012Validator(doc).validate(instance)


@pytest.fixture(scope="session")
def schemas() -> dict[str, Any]:
    return json.loads(SCHEMAS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def validator_for(schemas: dict[str, Any]):
    """Return a factory building a validator for a given $defs name."""

    def _make(def_name: str) -> Draft202012Validator:
        doc = {
            "$schema": schemas["$schema"],
            "$ref": f"#/$defs/{def_name}",
            "$defs": schemas["$defs"],
        }
        Draft202012Validator.check_schema(doc)
        return Draft202012Validator(doc)

    return _make


@pytest.fixture(scope="session")
def golden_ids() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "golden_ids.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def wire_fixtures() -> dict[str, Any]:
    """Load every schema-checked wire fixture by stem (e.g. ``search_result``)."""
    return {
        stem: json.loads((FIXTURES_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        for stem in FIXTURE_DEF_MAP
    }


@pytest.fixture
def fake_service(wire_fixtures: dict[str, Any]):
    from fakes.fake_verity_service import FakeVerityService

    return FakeVerityService(wire_fixtures)