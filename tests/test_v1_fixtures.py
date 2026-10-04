"""V1 acceptance (roadmap 04, step V1): success/empty/error fixtures validate
against the frozen schemas in contract 21, golden IDs match contract 03, and
FakeVerityService returns them faithfully with strict validation."""

from __future__ import annotations

import asyncio
import hashlib
import json

import pytest

from conftest import FIXTURE_DEF_MAP, validate_wire
from fakes.fake_verity_service import VerityError

REQ_ID = "req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2"
EV_ID = "ev_0a9948f2aa8b8cc5e499ef43626c5847eeab8df548ba5961e38a9a1126e4dc8e"
BAD_REQ_ID = "req_" + "0" * 64


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- golden IDs


def test_golden_ids_exact_vectors(golden_ids):
    assert golden_ids["source_id"] == "24da624f-7fd0-41ea-a49b-8449cbb179d9"
    assert golden_ids["version_id"] == "129dcd06-1ba1-4f0c-bf7e-c678f905b624"
    assert (
        golden_ids["block_id"]
        == "blk_75c2eccdd286a5d1218d15d0d80f0f65356359458fd641fa25e7e9e117f6cfff"
    )
    assert (
        golden_ids["chunk_id"]
        == "chk_71bb4eb1f7917adbd4771acd9946ee1a30994af19c4ebbf66ecd2b1e4b89b16a"
    )
    assert golden_ids["requirement_id"] == REQ_ID
    assert golden_ids["evidence_id"] == EV_ID


def test_golden_ids_recomputed_hashes(golden_ids):
    """The four hash vectors are reproducible per contract 03's canonical JSON rule."""
    def digest(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    assert "blk_" + digest(golden_ids["block"]) == golden_ids["block_id"]
    assert "chk_" + digest(golden_ids["chunk"]) == golden_ids["chunk_id"]
    assert "req_" + digest(golden_ids["requirement"]) == golden_ids["requirement_id"]
    assert "ev_" + digest(golden_ids["evidence"]) == golden_ids["evidence_id"]


# ------------------------------------------------------- schema validation


@pytest.mark.parametrize("stem", sorted(FIXTURE_DEF_MAP))
def test_wire_fixture_validates_against_contract_21(validator_for, wire_fixtures, stem):
    validator_for(FIXTURE_DEF_MAP[stem]).validate(wire_fixtures[stem])


def test_fixtures_are_cross_consistent(wire_fixtures, golden_ids):
    requirement = wire_fixtures["requirement"]
    search = wire_fixtures["search_result"]
    lookup = wire_fixtures["evidence_lookup"]
    assert requirement["requirement_id"] == golden_ids["requirement_id"]
    assert requirement["evidence_id"] == golden_ids["evidence_id"]
    item = search["items"][0]
    assert item["evidence_id"] == lookup["evidence"]["evidence_id"] == golden_ids["evidence_id"]
    assert item["chunk_id"] == lookup["evidence"]["chunk_id"] == golden_ids["chunk_id"]
    assert item["quote"] == requirement["text"]
    assert wire_fixtures["coverage_result"]["results"][0]["requirement_id"] == REQ_ID


# -------------------------------------------------------- FakeVerityService


def test_search_evidence_returns_canonical_fixture(fake_service, wire_fixtures, schemas):
    result = run(fake_service.search_evidence({"query": "refund window"}))
    validate_wire(schemas, "SearchResult", result)
    assert result == wire_fixtures["search_result"]
    assert fake_service.call_counts["search_result"] == 1


def test_no_match_search_is_success_not_error(fake_service, schemas):
    result = run(fake_service.search_evidence({"query": "zz-no-match"}))
    validate_wire(schemas, "SearchResult", result)
    assert result["items"] == []
    assert result["completeness"] == "empty"
    assert result["total_returned"] == 0


@pytest.mark.parametrize(
    "search_request",
    [{"query": "x"}, {"query": "z" * 2001}, {}, {"query": "ok", "limit": 0}, {"query": "ok", "limit": 21}],
)
def test_search_invalid_request_rejected(fake_service, search_request):
    with pytest.raises(VerityError) as excinfo:
        run(fake_service.search_evidence(search_request))
    assert excinfo.value.code == "INVALID_REQUEST"


def test_get_requirement_roundtrip(fake_service, schemas):
    result = run(fake_service.get_requirement(REQ_ID))
    validate_wire(schemas, "Requirement", result)
    assert result["local_id"] == "REQ-001"
    assert fake_service.call_counts["requirement"] == 1


def test_get_requirement_not_found(fake_service):
    with pytest.raises(VerityError) as excinfo:
        run(fake_service.get_requirement("req_" + "f" * 64))
    assert excinfo.value.code == "REQUIREMENT_NOT_FOUND"
    assert excinfo.value.retryable is False


def test_get_requirement_bad_pattern(fake_service):
    with pytest.raises(VerityError) as excinfo:
        run(fake_service.get_requirement("not-a-req-id"))
    assert excinfo.value.code == "INVALID_REQUEST"


def test_get_evidence_direct_lookup_has_null_score(fake_service, schemas):
    result = run(fake_service.get_evidence(EV_ID, context_chars=500))
    validate_wire(schemas, "EvidenceLookup", result)
    evidence = result["evidence"]
    assert evidence["score"] is None  # contract 07: direct lookup has no query score
    assert evidence["ranking"] == {
        "dense_rank": None, "lexical_rank": None, "rrf_score": None, "rerank_score": None,
    }
    assert isinstance(result["context_before"], str) and isinstance(result["context_after"], str)


def test_get_evidence_not_found_and_bad_context(fake_service):
    with pytest.raises(VerityError) as excinfo:
        run(fake_service.get_evidence("ev_" + "a" * 64))
    assert excinfo.value.code == "EVIDENCE_NOT_FOUND"
    with pytest.raises(VerityError) as excinfo:
        run(fake_service.get_evidence(EV_ID, context_chars=4001))
    assert excinfo.value.code == "INVALID_REQUEST"


def test_check_coverage_preserves_request_order(fake_service, schemas):
    result = run(fake_service.check_coverage({"requirement_ids": [REQ_ID], "workspace_id": "demo"}))
    validate_wire(schemas, "CoverageResult", result)
    assert [r["requirement_id"] for r in result["results"]] == [REQ_ID]
    assert result["results"][0]["status"] == "IMPLEMENTED"
    assert fake_service.call_counts["coverage_result"] == 1


def test_check_coverage_unknown_workspace(fake_service):
    with pytest.raises(VerityError) as excinfo:
        run(fake_service.check_coverage({"requirement_ids": [REQ_ID], "workspace_id": "nope"}))
    assert excinfo.value.code == "WORKSPACE_NOT_FOUND"


def test_check_coverage_unknown_requirement(fake_service):
    with pytest.raises(VerityError) as excinfo:
        run(fake_service.check_coverage({"requirement_ids": [BAD_REQ_ID], "workspace_id": "demo"}))
    assert excinfo.value.code == "REQUIREMENT_NOT_FOUND"


def test_service_returns_deep_copies(fake_service):
    first = run(fake_service.search_evidence({"query": "refund window"}))
    first["items"][0]["quote"] = "tampered"
    second = run(fake_service.search_evidence({"query": "refund window"}))
    assert second["items"][0]["quote"] == "Refund requests MUST be accepted only within 30 days."