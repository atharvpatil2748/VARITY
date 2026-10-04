"""U1 UI fixture tests: every mock fixture validates against contract 21.

A minimal Draft-2020-12 subset validator (no external dependency) checks
the frozen fixture JSON against the $defs in
Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json so the typed API mock can
never drift from the frozen wire contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CONTRACT21 = ROOT / "Docs" / "contracts" / "21_VERITY_V1_JSON_SCHEMAS.json"
FIXTURES = ROOT / "sdk-ui" / "frontend" / "api-mock" / "fixtures"

SCHEMAS = json.loads(CONTRACT21.read_text(encoding="utf-8"))
DEFS = SCHEMAS["$defs"]

_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _check_type(value: object, expected: object) -> bool:
    types = expected if isinstance(expected, list) else [expected]
    for name in types:
        if name == "null" and value is None:
            return True
        if name == "string" and isinstance(value, str):
            return True
        if name == "boolean" and isinstance(value, bool):
            return True
        if name == "integer" and isinstance(value, int) \
                and not isinstance(value, bool):
            return True
        if name == "number" and isinstance(value, (int, float)) \
                and not isinstance(value, bool):
            return True
        if name == "array" and isinstance(value, list):
            return True
        if name == "object" and isinstance(value, dict):
            return True
    return False


def validate(value: object, schema: dict, path: str = "$") -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/$defs/"), f"unsupported ref {ref} at {path}"
        return validate(value, DEFS[ref.split("/")[-1]], path)
    if "const" in schema:
        assert value == schema["const"], f"{path} must equal {schema['const']!r}"
        return
    if "enum" in schema:
        assert value in schema["enum"], f"{path} {value!r} not in enum {schema['enum']}"
        return
    if "oneOf" in schema:
        for option in schema["oneOf"]:
            try:
                validate(value, option, path)
                return
            except AssertionError:
                continue
        raise AssertionError(f"{path} matched no oneOf option")
    if "type" in schema:
        assert _check_type(value, schema["type"]), \
            f"{path} has wrong type: {value!r} vs {schema['type']}"
    if isinstance(value, str):
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], f"{path} too short"
        if "maxLength" in schema:
            assert len(value) <= schema["maxLength"], f"{path} too long"
        if "pattern" in schema:
            assert re.search(schema["pattern"], value), \
                f"{path} {value!r} fails pattern {schema['pattern']}"
        if schema.get("format") == "date-time":
            assert _DATETIME_RE.match(value), f"{path} not RFC3339 Z: {value!r}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema:
            assert value >= schema["minimum"], f"{path} below minimum"
        if "maximum" in schema:
            assert value <= schema["maximum"], f"{path} above maximum"
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
        if "maxItems" in schema:
            assert len(value) <= schema["maxItems"], f"{path} too many items"
    if isinstance(value, dict):
        for key in schema.get("required", []):
            assert key in value, f"{path}.{key} is required"
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(props)
            assert not unknown, f"{path} has unknown fields {sorted(unknown)}"
        for key, item in value.items():
            if key in props:
                validate(item, props[key], f"{path}.{key}")


FIXTURE_TO_DEF = {
    "health.json": "Health",
    "documents.json": "ListPageDocument",
    "sources.json": "ListPageSource",
    "ingest_result.json": "IngestResult",
    "search.json": "SearchResult",
    "coverage.json": "CoverageResult",
    "evidence.json": "EvidenceLookup",
    "error_invalid_request.json": "HttpError",
}


@pytest.mark.parametrize("filename", sorted(FIXTURE_TO_DEF))
def test_fixture_validates_against_contract_21(filename: str) -> None:
    fixture = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    validate(fixture, {"$ref": f"#/$defs/{FIXTURE_TO_DEF[filename]}"})


def test_evidence_direct_lookup_has_null_score() -> None:
    """Contract 11: GET /evidence returns score=null (no query score)."""
    fixture = json.loads((FIXTURES / "evidence.json").read_text(encoding="utf-8"))
    assert fixture["evidence"]["score"] is None


def test_coverage_fixture_shows_uncertain_honestly() -> None:
    """U4 acceptance: UNCERTAIN is visible with its reason."""
    fixture = json.loads((FIXTURES / "coverage.json").read_text(encoding="utf-8"))
    statuses = [r["status"] for r in fixture["results"]]
    assert "UNCERTAIN" in statuses
    assert all(r["reason"] for r in fixture["results"])


def test_client_references_only_existing_fixtures() -> None:
    """Every fixture the typed mock client can load must exist on disk."""
    import re

    client = (ROOT / "sdk-ui" / "frontend" / "api-mock" / "client.js").read_text(
        encoding="utf-8"
    )
    referenced = set(re.findall(r"fixtures/([a-z_]+)\.json", client))
    on_disk = {p.stem for p in FIXTURES.glob("*.json")}
    assert referenced <= on_disk, (
        f"client.js references missing fixtures: {sorted(referenced - on_disk)}"
    )
    assert FIXTURE_TO_DEF.keys() <= {f"{name}.json" for name in on_disk}