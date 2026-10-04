"""Frozen MCP tool input/output schemas (contract 09 / 21).

Owner Vandit. Schemas are JSON Schema Draft 2020-12. In implementation
each tool publishes one bundled schema (no external ``$ref`` resolution)
for clients that cannot resolve references. The machine-readable source
of truth is ``Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json``; this
module loads and validates against it at startup rather than duplicating
definitions.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Repository path to the frozen machine schemas (contract 21).
CONTRACT_21_PATH = Path("Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json")


def load_tool_schemas(contracts_root: Path | None = None) -> dict[str, object]:
    """Load and return the frozen v1 tool schemas. Skeleton for Phase 11."""
    path = contracts_root / CONTRACT_21_PATH if contracts_root else CONTRACT_21_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"contract 21 schemas not found at {path}; they are the source of truth"
        )
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)