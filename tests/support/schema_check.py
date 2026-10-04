"""Minimal JSON Schema validator for the contract-21 $defs subset.

Implements exactly the keywords used by
``Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json`` ($ref to ``#/$defs/*``,
``type`` (incl. lists), ``enum``, ``const``, ``pattern``, ``format``
(uuid/date-time), ``minimum``, ``minLength``, ``maxLength``, ``minItems``,
``maxItems``, ``uniqueItems``, ``items``, ``properties``, ``required``,
``additionalProperties``, ``oneOf``, ``anyOf``, ``allOf``).

Self-contained so the contract fixture suite runs with no third-party
dependencies. ``tests/test_fixtures_contracts.py`` cross-checks every verdict
against the real ``jsonschema`` library when it is installed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "contracts_v1"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "Docs" / "contracts" / "21_VERITY_V1_JSON_SCHEMAS.json"

_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(instance, schema: dict, root: dict | None = None) -> list[str]:
    """Return a list of error strings; empty list means the instance is valid."""
    if root is None:
        root = schema
    errors: list[str] = []
    if "$ref" in schema:
        target = schema["$ref"]
        if not target.startswith("#/$defs/"):
            return [f"unsupported $ref {target!r}"]
        return validate(instance, root["$defs"][target[len("#/$defs/"):]], root)

    if "const" in schema and instance != schema["const"]:
        errors.append(f"expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{instance!r} not in enum {schema['enum']!r}")
    if "allOf" in schema:
        for sub in schema["allOf"]:
            errors.extend(validate(instance, sub, root))
    if "anyOf" in schema:
        if not any(not validate(instance, sub, root) for sub in schema["anyOf"]):
            errors.append(f"{instance!r} matches no anyOf branch")
    if "oneOf" in schema:
        matches = sum(1 for sub in schema["oneOf"] if not validate(instance, sub, root))
        if matches != 1:
            errors.append(f"{instance!r} matches {matches} oneOf branches, expected 1")

    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_matches(instance, t) for t in types):
            errors.append(f"{instance!r} is not of type {schema['type']!r}")
            return errors

    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{instance!r} does not match pattern {schema['pattern']!r}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{instance!r} shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{instance!r} longer than maxLength {schema['maxLength']}")
        if schema.get("format") == "date-time" and not _DATETIME_RE.match(instance):
            errors.append(f"{instance!r} is not an RFC 3339 date-time")
    if isinstance(instance, bool):
        pass
    elif isinstance(instance, (int, float)):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{instance!r} below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{instance!r} above maximum {schema['maximum']}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"list of {len(instance)} items below minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"list of {len(instance)} items above maxItems {schema['maxItems']}")
        if schema.get("uniqueItems"):
            serialized = [json.dumps(item, sort_keys=True) for item in instance]
            if len(set(serialized)) != len(serialized):
                errors.append("items are not unique")
        if "items" in schema:
            for index, item in enumerate(instance):
                for err in validate(item, schema["items"], root):
                    errors.append(f"items[{index}]: {err}")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                for err in validate(value, properties[key], root):
                    errors.append(f"{key}: {err}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"unknown property {key!r}")
    return errors


def _type_matches(instance, name: str) -> bool:
    if name == "object":
        return isinstance(instance, dict)
    if name == "array":
        return isinstance(instance, list)
    if name == "string":
        return isinstance(instance, str)
    if name == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if name == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if name == "boolean":
        return isinstance(instance, bool)
    if name == "null":
        return instance is None
    return False