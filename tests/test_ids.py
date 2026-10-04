"""Golden ID vector tests (contract 03 identifier registry).

The four hash vectors and UUIDv4 syntax are frozen values; any change here
is a contract change, not a code change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import UUID

import pytest

from verity.errors import VerityError
from verity.ids import (
    canonical_digest,
    make_block_id,
    make_chunk_id,
    make_evidence_id,
    make_requirement_id,
    new_uuid4,
)
from verity.models import ChunkDraft, ChunkKind

FIXTURE = Path(__file__).parent / "fixtures" / "contracts_v1" / "golden_ids.json"


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_block_golden_vector(golden: dict) -> None:
    expected = golden["block"]["expected"]
    assert expected == make_block_id(
        UUID(golden["version_id"]), 0, "Refund window"
    )
    assert expected.startswith("blk_")
    assert re.fullmatch(r"blk_[0-9a-f]{64}", expected)


def test_chunk_golden_vector(golden: dict) -> None:
    draft = ChunkDraft(
        kind=ChunkKind.REQUIREMENT,
        text="Refund requests MUST be accepted only within 30 days.",
        block_start=0,
        block_end=1,
        start_offset=None,
        end_offset=None,
        requirement_id=None,
    )
    assert (
        make_chunk_id(UUID(golden["version_id"]), draft)
        == golden["chunk"]["expected"]
    )


def test_requirement_golden_vector(golden: dict) -> None:
    assert (
        make_requirement_id(UUID(golden["source_id"]), "REQ-001")
        == golden["requirement"]["expected"]
    )


def test_evidence_golden_vector(golden: dict) -> None:
    assert (
        make_evidence_id(
            UUID(golden["version_id"]), golden["chunk"]["expected"]
        )
        == golden["evidence"]["expected"]
    )


def test_new_uuid4_is_uuidv4() -> None:
    value = new_uuid4()
    assert value.version == 4
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        str(value),
    )


def test_canonical_digest_is_64_lowercase_hex(golden: dict) -> None:
    digest = canonical_digest(golden["block"]["payload"])
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest == golden["block"]["expected"].removeprefix("blk_")


def test_nfc_normalization_changes_hash() -> None:
    # Decomposed (NFD) form must hash to the same digest as composed NFC form.
    composed = {"text": "café"}
    decomposed = {"text": "cafe\u0301"}
    assert canonical_digest(composed) == canonical_digest(decomposed)