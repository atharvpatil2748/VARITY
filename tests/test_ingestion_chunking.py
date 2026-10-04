"""Chunker and central materializer tests (contract 05/03, P4 acceptance).

Covers: exact chunk drafts for ``payments.md``, contiguous valid block spans,
no page/heading crossing, chunkers never assign IDs, ``ChunkDraft`` schema
validation, ``CHUNKING_ERROR`` on invalid spans, and the central materializer
assigning locators/ordinals/IDs. The materializer runs against the real
``verity.ids`` (PR-A1) when importable, where the four golden vectors of
contract 03 must match exactly; otherwise the fixture ID maker is used.
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

from fakes.fake_ids import FakeIdMaker
from support import schema_check

from verity.errors import VerityError
from verity.ingestion.chunking import CentralMaterializer, GeneralChunker
from verity.ingestion.parsers import ParserRouter
from verity.ingestion.spec import SpecParser

FIXTURES = TESTS_DIR / "fixtures" / "contracts_v1"
SCHEMA = schema_check.load_schema()
VERSION_ID = "129dcd06-1ba1-4f0c-bf7e-c678f905b624"

router = ParserRouter()


def parse_fixture(name: str, media: str) -> dict:
    return router.parse((FIXTURES / name).read_bytes(), name, media)


def test_chunk_drafts_match_expected_fixture() -> None:
    parsed = SpecParser().parse(
        (FIXTURES / "payments.md").read_bytes(), "payments.md", "text/markdown"
    )
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    expected = json.loads((FIXTURES / "expected_payments_chunks.json").read_text("utf-8"))
    assert list(drafts) == expected


def test_requirement_chunk_contains_title_text_constraints_edge_cases() -> None:
    parsed = SpecParser().parse(
        (FIXTURES / "payments.md").read_bytes(), "payments.md", "text/markdown"
    )
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    requirement = next(d for d in drafts if d["kind"] == "requirement")
    assert requirement["text"].startswith("Refund window\nRefund requests MUST")
    assert "Constraints:" in requirement["text"]
    assert "- A later request MUST return REFUND_WINDOW_EXPIRED." in requirement["text"]
    assert "Edge cases:" in requirement["text"]
    assert "- A request at exactly 30 days is accepted." in requirement["text"]


def test_chunk_drafts_validate_against_schema21() -> None:
    parsed = SpecParser().parse(
        (FIXTURES / "payments.md").read_bytes(), "payments.md", "text/markdown"
    )
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    for draft in drafts:
        assert schema_check.validate(draft, SCHEMA["$defs"]["ChunkDraft"], SCHEMA) == []


def test_chunker_never_assigns_ids() -> None:
    parsed = SpecParser().parse(
        (FIXTURES / "payments.md").read_bytes(), "payments.md", "text/markdown"
    )
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    for draft in drafts:
        assert "chunk_id" not in draft
        assert draft["requirement_id"] is None
        assert draft["start_offset"] is None and draft["end_offset"] is None


def test_chunker_carries_explicit_requirement_ids_when_provided() -> None:
    parsed = SpecParser().parse(
        (FIXTURES / "payments.md").read_bytes(), "payments.md", "text/markdown"
    )
    chunker = GeneralChunker(requirement_ids={"REQ-001": "req_" + "0" * 64})
    drafts = chunker.chunk(parsed, VERSION_ID)
    first = next(d for d in drafts if d["kind"] == "requirement")
    assert first["requirement_id"] == "req_" + "0" * 64
    others = [d for d in drafts if d["kind"] == "requirement"][1:]
    assert all(d["requirement_id"] is None for d in others)


def test_draft_spans_are_contiguous_valid_and_bounded() -> None:
    for name, media in [("payments.md", "text/markdown"),
                        ("architecture.md", "text/markdown"),
                        ("security.txt", "text/plain"),
                        ("payments.pdf", "application/pdf")]:
        parsed = parse_fixture(name, media)
        drafts = GeneralChunker().chunk(parsed, VERSION_ID)
        assert drafts, name
        blocks = parsed["blocks"]
        covered: list[int] = []
        for draft in drafts:
            start, end = draft["block_start"], draft["block_end"]
            assert 0 <= start <= end < len(blocks), (name, draft)
            pages = {blocks[i]["page"] for i in range(start, end + 1)}
            assert len(pages) == 1, f"{name}: chunk crosses pages"
            covered.extend(range(start, end + 1))
        assert covered == sorted(covered)
        assert len(set(covered)) == len(covered), f"{name}: overlapping drafts"


def test_general_chunks_stay_within_one_heading_path() -> None:
    parsed = parse_fixture("architecture.md", "text/markdown")
    blocks = parsed["blocks"]
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    for draft in drafts:
        paths = {
            tuple(blocks[i]["heading_path"])
            for i in range(draft["block_start"], draft["block_end"] + 1)
        }
        assert len(paths) == 1, f"chunk crosses headings: {draft['text'][:40]!r}"


def test_code_chunks_use_code_chunk_kind() -> None:
    code = b"def a():\n    pass\n\n\ndef b():\n    pass\n"
    parsed = router.parse(code, "mod.py", "text/x-code")
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    assert drafts
    assert all(d["kind"] == "code_chunk" for d in drafts)


def test_pdf_chunks_do_not_cross_pages() -> None:
    parsed = parse_fixture("payments.pdf", "application/pdf")
    blocks = parsed["blocks"]
    for draft in GeneralChunker().chunk(parsed, VERSION_ID):
        pages = {blocks[i]["page"] for i in range(draft["block_start"], draft["block_end"] + 1)}
        assert len(pages) == 1


def test_invalid_span_raises_chunking_error() -> None:
    parsed = parse_fixture("payments.md", "text/markdown")
    parsed["spec_requirements"][0]["block_end"] = 999
    with pytest.raises(VerityError) as excinfo:
        GeneralChunker().chunk(parsed, VERSION_ID)
    assert excinfo.value.code == "CHUNKING_ERROR"


GOLDEN = {
    "version_id": "129dcd06-1ba1-4f0c-bf7e-c678f905b624",
    "source_id": "24da624f-7fd0-41ea-a49b-8449cbb179d9",
    "blk": "blk_75c2eccdd286a5d1218d15d0d80f0f65356359458fd641fa25e7e9e117f6cfff",
    "chk": "chk_71bb4eb1f7917adbd4771acd9946ee1a30994af19c4ebbf66ecd2b1e4b89b16a",
    "req": "req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2",
    "ev": "ev_0a9948f2aa8b8cc5e499ef43626c5847eeab8df548ba5961e38a9a1126e4dc8e",
}
DOCUMENT_ID = "ebc2352e-ff9c-4167-b11a-1e30d550411d"


def golden_parsed() -> dict:
    block = {
        "block_type": "heading", "page": None,
        "heading_path": ["Requirements", "REQ-001: Refund window"],
        "start_line": 1, "end_line": 1,
        "start_offset": None, "end_offset": None,
    }
    return {
        "metadata": {
            "metadata_version": "1.0.0", "title": "Golden", "source_key": "payments-api",
            "project": "payment-service", "spec_version": "1.0", "language": "en",
            "page_count": None, "parser_name": "verity_spec",
            "parser_version": "1.0.0", "warnings": [],
        },
        "blocks": [
            dict(block, ordinal=0, text="Refund window"),
            dict(block, ordinal=1, block_type="paragraph",
                 text="Refund requests MUST be accepted only within 30 days."),
        ],
        "media_type": "text/markdown",
        "kind": "spec",
        "spec_requirements": [{
            "local_id": "REQ-001", "title": "Refund window",
            "text": "Refund requests MUST be accepted only within 30 days.",
            "constraints": [], "edge_cases": [], "api_refs": [],
            "reference_ids": [], "acceptance_local_ids": [],
            "block_start": 0, "block_end": 1,
        }],
        "spec_entities": [],
    }


def golden_drafts() -> tuple[dict, ...]:
    return ({
        "kind": "requirement",
        "text": "Refund requests MUST be accepted only within 30 days.",
        "block_start": 0, "block_end": 1,
        "start_offset": None, "end_offset": None,
        "requirement_id": None,
    },)


def test_materializer_assigns_ids_ordinals_and_locators() -> None:
    parsed = parse_fixture("payments.md", "text/markdown")
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    ids = FakeIdMaker()
    out = CentralMaterializer(ids).materialize(
        parsed, drafts, GOLDEN["source_id"], DOCUMENT_ID, VERSION_ID, "specs/payments.md"
    )
    assert [c["ordinal"] for c in out["chunks"]] == list(range(len(drafts)))
    for chunk in out["chunks"]:
        assert chunk["schema_version"] == "1.0.0"
        assert chunk["chunk_id"].startswith("chk_")
        locator = chunk["locator"]
        assert locator["source_path"] == "specs/payments.md"
        assert locator["page"] is None
        assert locator["start_offset"] is None and locator["end_offset"] is None
    requirement_chunks = [c for c in out["chunks"] if c["kind"] == "requirement"]
    assert all(c["requirement_id"] is not None for c in requirement_chunks)
    assert all(c["requirement_id"].startswith("req_") for c in requirement_chunks)
    for block in out["blocks"]:
        assert block["block_id"].startswith("blk_")


def test_materializer_chunk_payload_matches_contract03() -> None:
    parsed = parse_fixture("payments.md", "text/markdown")
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    ids = FakeIdMaker()
    CentralMaterializer(ids).materialize(
        parsed, drafts, GOLDEN["source_id"], DOCUMENT_ID, VERSION_ID, "specs/payments.md"
    )
    chunk_calls = [c for c in ids.calls if c[0] == "chunk"]
    assert len(chunk_calls) == len(drafts)
    for (kind, (version_arg, draft)), original in zip(chunk_calls, drafts):
        assert kind == "chunk"
        assert version_arg == VERSION_ID
        # Contract 03 chunk payload fields, exactly, passed to make_chunk_id.
        assert draft.block_start == original["block_start"]
        assert draft.block_end == original["block_end"]
        assert draft.start_offset == original["start_offset"]
        assert draft.end_offset == original["end_offset"]
        assert draft.kind == original["kind"]
        assert draft.text == original["text"]


def test_materializer_embeds_acceptance_criteria_in_authored_order() -> None:
    parsed = parse_fixture("payments.md", "text/markdown")
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    out = CentralMaterializer(FakeIdMaker()).materialize(
        parsed, drafts, GOLDEN["source_id"], DOCUMENT_ID, VERSION_ID, "specs/payments.md"
    )
    req = next(r for r in out["requirements"] if r["local_id"] == "REQ-001")
    assert [c["local_id"] for c in req["acceptance_criteria"]] == ["AC-001"]
    assert req["acceptance_criteria"][0]["text"].startswith("A payment older")
    assert req["api_refs"] == ["API-001"]
    assert req["chunk_id"].startswith("chk_")
    assert req["evidence_id"].startswith("ev_")
    entities = {e["local_id"]: e for e in out["spec_entities"]}
    assert entities["AC-001"]["reference_ids"] == ["REQ-001"]
    assert entities["AC-001"]["evidence_id"].startswith("ev_")


def test_materializer_records_validate_against_schema21() -> None:
    parsed = parse_fixture("payments.md", "text/markdown")
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    out = CentralMaterializer(FakeIdMaker()).materialize(
        parsed, drafts, GOLDEN["source_id"], DOCUMENT_ID, VERSION_ID, "specs/payments.md"
    )
    for chunk in out["chunks"]:
        assert schema_check.validate(chunk, SCHEMA["$defs"]["Chunk"], SCHEMA) == []
    for req in out["requirements"]:
        assert schema_check.validate(req, SCHEMA["$defs"]["Requirement"], SCHEMA) == []
    for ent in out["spec_entities"]:
        assert schema_check.validate(ent, SCHEMA["$defs"]["SpecEntity"], SCHEMA) == []
    for block in out["blocks"]:
        bare = {k: v for k, v in block.items() if k != "block_id"}
        assert schema_check.validate(bare, SCHEMA["$defs"]["ParsedBlock"], SCHEMA) == []


def test_materializer_rejects_dangling_acceptance_reference() -> None:
    parsed = parse_fixture("payments.md", "text/markdown")
    parsed["spec_requirements"][0]["acceptance_local_ids"] = ["AC-999"]
    drafts = GeneralChunker().chunk(parsed, VERSION_ID)
    with pytest.raises(VerityError) as excinfo:
        CentralMaterializer(FakeIdMaker()).materialize(
            parsed, drafts, GOLDEN["source_id"], DOCUMENT_ID, VERSION_ID, "specs/payments.md"
        )
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"


try:  # pragma: no cover - depends on PR-A1 merge state
    import verity.ids as real_ids
except ImportError:  # pragma: no cover
    real_ids = None


@pytest.mark.skipif(real_ids is None, reason="verity.ids (PR-A1) not merged yet")
def test_materializer_golden_vectors_with_real_ids() -> None:
    """All four contract-03 golden vectors must flow through the materializer."""
    out = CentralMaterializer(real_ids).materialize(
        golden_parsed(), golden_drafts(),
        GOLDEN["source_id"], DOCUMENT_ID, GOLDEN["version_id"], "specs/payments.md",
    )
    assert out["blocks"][0]["block_id"] == GOLDEN["blk"]
    assert out["chunks"][0]["chunk_id"] == GOLDEN["chk"]
    assert out["requirements"][0]["requirement_id"] == GOLDEN["req"]
    assert out["requirements"][0]["evidence_id"] == GOLDEN["ev"]