"""Contract-21 fixture validation tests (P1 acceptance).

Every ``schema_valid_*.json`` fixture must validate against its
``Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json`` $def and every
``schema_invalid_*.json`` must fail it. The expected parsed drafts for
``payments.md`` must also validate as ``$defs/ParsedDocument``. All verdicts
are cross-checked against the real ``jsonschema`` library when installed.
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

from support import schema_check

FIXTURES = TESTS_DIR / "fixtures" / "contracts_v1"
SCHEMA = schema_check.load_schema()

DEF_FOR_FIXTURE = {
    "parsed_document": "ParsedDocument",
    "parsed_block": "ParsedBlock",
    "chunk_draft": "ChunkDraft",
    "spec_requirement_draft": "SpecRequirementDraft",
    "spec_entity_draft": "SpecEntityDraft",
    "search_request": "SearchRequest",
}

try:  # cross-check harness (optional)
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


def _def_name(fixture_name: str) -> str:
    stem = fixture_name.replace("schema_valid_", "").replace("schema_invalid_", "")
    return DEF_FOR_FIXTURE[stem.replace(".json", "")]


def _as_root_schema(def_name: str) -> dict:
    """Wrap one $def so ``#/$defs/...`` refs inside it resolve for jsonschema."""
    return {"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{def_name}"}


@pytest.mark.parametrize(
    "fixture_name",
    sorted(p.name for p in FIXTURES.glob("schema_valid_*.json")),
)
def test_valid_fixtures_validate_against_contract21(fixture_name: str) -> None:
    instance = json.loads((FIXTURES / fixture_name).read_text("utf-8"))
    def_name = _def_name(fixture_name)
    assert schema_check.validate(instance, SCHEMA["$defs"][def_name], SCHEMA) == []
    if jsonschema is not None:
        jsonschema.validate(instance, _as_root_schema(def_name))  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "fixture_name",
    sorted(p.name for p in FIXTURES.glob("schema_invalid_*.json")),
)
def test_invalid_fixtures_fail_contract21(fixture_name: str) -> None:
    instance = json.loads((FIXTURES / fixture_name).read_text("utf-8"))
    def_name = _def_name(fixture_name)
    assert schema_check.validate(instance, SCHEMA["$defs"][def_name], SCHEMA) != []
    if jsonschema is not None:
        with pytest.raises(jsonschema.ValidationError):  # type: ignore[union-attr]
            jsonschema.validate(instance, _as_root_schema(def_name))  # type: ignore[union-attr]


def test_expected_payments_parsed_validates_as_parsed_document() -> None:
    instance = json.loads((FIXTURES / "expected_payments_parsed.json").read_text("utf-8"))
    assert schema_check.validate(instance, SCHEMA["$defs"]["ParsedDocument"], SCHEMA) == []
    for draft in instance["spec_requirements"]:
        assert schema_check.validate(draft, SCHEMA["$defs"]["SpecRequirementDraft"], SCHEMA) == []
    for draft in instance["spec_entities"]:
        assert schema_check.validate(draft, SCHEMA["$defs"]["SpecEntityDraft"], SCHEMA) == []
    if jsonschema is not None:
        jsonschema.validate(instance, _as_root_schema("ParsedDocument"))  # type: ignore[union-attr]


def test_expected_payments_chunks_validate_as_chunk_drafts() -> None:
    drafts = json.loads((FIXTURES / "expected_payments_chunks.json").read_text("utf-8"))
    assert drafts
    for draft in drafts:
        assert schema_check.validate(draft, SCHEMA["$defs"]["ChunkDraft"], SCHEMA) == []


def test_golden_ids_fixture_matches_contract03_vectors() -> None:
    # golden_ids.json is Atharv's PR-A1 fixture; skip until the foundation merges.
    golden_path = FIXTURES / "golden_ids.json"
    if not golden_path.exists():
        pytest.skip("golden_ids.json (Atharv, PR-A1) not merged yet")
    golden = json.loads(golden_path.read_text("utf-8"))
    assert golden["version_id"] == "129dcd06-1ba1-4f0c-bf7e-c678f905b624"
    assert golden["source_id"] == "24da624f-7fd0-41ea-a49b-8449cbb179d9"
    assert golden["block"]["expected"] == (
        "blk_75c2eccdd286a5d1218d15d0d80f0f65356359458fd641fa25e7e9e117f6cfff"
    )
    assert golden["chunk"]["expected"] == (
        "chk_71bb4eb1f7917adbd4771acd9946ee1a30994af19c4ebbf66ecd2b1e4b89b16a"
    )
    assert golden["requirement"]["expected"] == (
        "req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2"
    )
    assert golden["evidence"]["expected"] == (
        "ev_0a9948f2aa8b8cc5e499ef43626c5847eeab8df548ba5961e38a9a1126e4dc8e"
    )