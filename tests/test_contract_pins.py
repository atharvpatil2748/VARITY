"""Contract-16 signature pin test (commitment from the PR #3 review).

Contract 16 is load-bearing for transport (Vandit's MCP/HTTP layer binds to
it). This test parses the frozen document itself so a silent signature edit
in Docs/contracts/16 fails this suite loudly.
"""

from __future__ import annotations

from pathlib import Path

CONTRACT_16 = (
    Path(__file__).parent.parent / "Docs" / "contracts"
    / "16_VERITY_PUBLIC_INTERFACES.md"
)

#: Frozen cross-module signatures (contract 16) that must appear verbatim.
PINNED_SIGNATURES = (
    "def canonical_digest(payload: Mapping[str, JSONValue]) -> str: ...",
    "def make_block_id(version_id: UUID, ordinal: int, text: str) -> str: ...",
    "def make_chunk_id(version_id: UUID, draft: ChunkDraft) -> str: ...",
    "def make_requirement_id(source_id: UUID, local_id: str) -> str: ...",
    "def make_evidence_id(version_id: UUID, chunk_id: str) -> str: ...",
    "def parse(self, data: bytes, filename: str, media_type: str) -> ParsedDocument: ...",
    "def chunk(self, parsed: ParsedDocument, version_id: UUID) -> tuple[ChunkDraft, ...]: ...",
    "async def ingest(self, request: IngestRequest, data: bytes) -> IngestResult: ...",
    "async def prepare_ingestion(self, request: IngestRequest, content_sha256: str,",
    "async def get_evidence_origin(self, evidence_id: str) -> tuple[Chunk, Document, Provenance] | None: ...",
    "async def search(self, request: SearchRequest) -> RetrievalRun: ...",
    "async def from_retrieval(self, request: SearchRequest, run: RetrievalRun) -> SearchResult: ...",
    "async def get(self, evidence_id: str, context_chars: int = 1000) -> EvidenceLookup: ...",
    "def format_citation(self, evidence_id: str, document_name: str, locator: Locator,",
    "async def snapshot(self, workspace_id: str) -> WorkspaceSnapshot: ...",
    "async def read_lines(self, snapshot: WorkspaceSnapshot, relative_path: str,",
    "async def check(self, request: CoverageRequest) -> CoverageResult: ...",
    "async def search_evidence(self, request: SearchRequest) -> SearchResult: ...",
    "async def get_requirement(self, requirement_id: str) -> Requirement: ...",
    "async def check_coverage(self, request: CoverageRequest) -> CoverageResult: ...",
)

#: Amendment sentences that are load-bearing for consumers (change logs 1.0.2-1.0.4).
PINNED_AMENDMENTS = (
    "in `get_evidence_origin` only, the returned `Document` describes the version that contains the evidence",
    "only `WorkspaceScanner.snapshot` and `WorkspaceScanner.read_lines` perform workspace file I/O",
)


def test_contract_16_exists() -> None:
    assert CONTRACT_16.is_file()


def test_signatures_are_pinned_verbatim() -> None:
    text = CONTRACT_16.read_text(encoding="utf-8")
    for signature in PINNED_SIGNATURES:
        assert signature in text, f"contract 16 signature changed: {signature!r}"


def test_amendment_sentences_are_pinned() -> None:
    text = CONTRACT_16.read_text(encoding="utf-8")
    for sentence in PINNED_AMENDMENTS:
        assert sentence in text, f"contract 16 amendment changed: {sentence!r}"