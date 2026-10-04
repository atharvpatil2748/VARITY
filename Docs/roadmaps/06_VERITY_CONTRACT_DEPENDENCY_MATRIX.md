# Contract dependency matrix

**Planning input:** [frozen index](../contracts/01_VERITY_CONTRACT_INDEX.md). **R** = required to implement an owned interface; **C** = consumer/reference, read the relevant section or use its fixture; **–** = not required for that developer's work. This matrix assigns reading effort, not authority. All owners use the same v1 objects and change process.

| Frozen contract | Atharv | Piyush | Vandit | Vanashree | Reason for assignment |
|---|:---:|:---:|:---:|:---:|---|
| `01` Index | R | R | R | R | Establishes precedence and freeze status. |
| `02` Versioning | R | C | C | C | Atharv implements versions; all follow change control. |
| `03` Data schemas | R | R | C | R | Atharv owns models; Piyush emits parsed/chunk/retrieval objects; Vanashree emits coverage objects; Vandit serializes them. |
| `04` Spec schema | C | R | – | C | Piyush parses it; Atharv persists its entities; Vanashree evaluates its acceptance criteria. |
| `05` Ingestion | R | R | C | – | Atharv supplies store/IDs; Piyush owns pipeline; Vandit accepts uploads only. |
| `06` Retrieval | C | R | C | C | Piyush owns ranking; Atharv assembles evidence; transport/UI need only mode and limits. |
| `07` Evidence/provenance | R | C | C | C | Atharv constructs; others preserve/consume. |
| `08` Multi-document | C | R | C | C | Piyush implements filters/rank; other consumers pass filters and display source identity. |
| `09` MCP | C | – | R | – | Vandit exposes VERITY to external Cline; Atharv uses the same four-tool shapes for native SDK parity. |
| `10` Cline SDK | R | – | C | C | Atharv owns the Cline agent powering native chat; Vandit delegates chat routes and Vanashree renders its response. |
| `11` HTTP API | C | – | R | R | Vandit implements routes; Vanashree builds native UI against them; Atharv's SDK gateway handles chat behind the route. |
| `12` Coverage | C | – | C | R | Vanashree implements core; Atharv wires/persists; Vandit adapts tool/route. |
| `13` Database | R | C | – | C | Atharv owns SQL; Piyush needs store behavior; Vanashree needs report persistence interface only. |
| `14` Configuration | R | C | C | C | Atharv parses; others consume frozen config fields, not env directly. |
| `15` Module boundaries | R | R | R | R | Import and ownership rules apply to every branch. |
| `16` Public interfaces | R | R | R | R | Cross-owner signatures and service boundary. |
| `17` Errors | R | C | R | C | Atharv owns codes; Vandit maps transports; producers/coverage raise typed errors. |
| `18` Contract tests | R | R | R | R | Each owner supplies focused tests and common fixture checks. |
| `19` Team ownership | R | R | R | R | File-level edit boundary. |
| `20` Baseline | R | C | C | C | Atharv integrates; others use priority and conflict decisions. |
| `21` JSON schemas | R | R | R | R | One wire schema; no owner creates a parallel Evidence type. |

Read `C` at the moment the consuming boundary is implemented. `–` means no prerequisite reading, not permission to contradict that document. The individual roadmaps list their smallest initial reading sets. The PPTX and `ARCHITECTURE.md` explain product intent; for implementation fields/signatures the frozen package wins. The earlier architecture suggests `compare_sources` while frozen MCP v1 excludes it; no branch implements that extra tool.

## Boundary discrepancy register (contracts unchanged)

| ID | Frozen texts | Minimum proposed resolution, **team approval required** | Affected owners |
|---|---|---|---|
| D1 | `06` says `RetrievalService.search -> tuple[RetrievalResult,...]`; `16` says `-> RetrievalRun`, and `03` requires retrieval mode/omissions in `SearchResult`. | **RESOLVED 2026-10-04 (issue #2, change log 1.0.2):** `06`'s signature corrected to `RetrievalRun`, search semantics untouched. Piyush (P9/PR-P3) and Atharv (A6/PR-A3) unblocked. | Piyush producer, Atharv consumer; Vandit/Vanashree fixture consumers. |
| D2 | `12` says only `WorkspaceScanner` opens workspace files; `16`'s `WorkspaceSnapshot` exposes file paths/hashes/sizes but no text or read method for `CodeEvidenceRetriever` to produce excerpts. | Add a scanner-owned bounded read method or a scanner-produced immutable text view to `16`/`12`; choose one, update tests and minor/major version per `02`. Do not let the retriever bypass the scanner. | Vanashree producer, Atharv service consumer. |
| D3 | `03` defines public `Document.version_id` as the active version; `16`'s `get_evidence_origin` returns `Document` for any evidence ID; `07` requires historical evidence after reingest. | **RESOLVED 2026-10-04 (issue #7 Option B, change log 1.0.3):** `get_evidence_origin` only returns a version-bound `Document` describing the evidence's (possibly historical) version; all other surfaces report the active version. Atharv (A5/A6/PR-A3) unblocked. | Atharv producer; Vandit and Vanashree consume resolved evidence. |

D1–D3 are documentation inconsistencies or missing interfaces, not invitations to silently redesign. They are tracked as handoff gates in the master and merge plan. No frozen file was edited during this roadmap pass.

## Task-level contract crosswalk

This is the direct lookup for every implementation task. `R` = required while implementing; `C` = reference only at the stated boundary; omitted contracts are not required for that task. `$defs` names are from `21_VERITY_V1_JSON_SCHEMAS.json`. The individual roadmap gives consumed/produced interfaces, wait state and PR action.

| Task | Owner | Exact contract dependency and schema definitions |
|---|---|---|
| A0 | Atharv | R: `01_VERITY_CONTRACT_INDEX.md`, `02_VERITY_VERSIONING_POLICY.md`, `15_VERITY_MODULE_BOUNDARIES.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `20_VERITY_IMPLEMENTATION_BASELINE.md` |
| A1 | Atharv | R: `03_VERITY_DATA_SCHEMAS.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/Document, Source, Requirement, Chunk, Evidence, Error); C: `02_VERITY_VERSIONING_POLICY.md` |
| A2 | Atharv | R: `03_VERITY_DATA_SCHEMAS.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/uuid, sha256, chunk_id, requirement_id, evidence_id) |
| A3 | Atharv | R: `14_VERITY_CONFIGURATION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md` |
| A4 | Atharv | R: `05_VERITY_DOCUMENT_INGESTION_CONTRACT.md`, `13_VERITY_DATABASE_SCHEMA.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/IngestRequest, IngestResult, Document, Chunk) |
| A5 | Atharv | R: `13_VERITY_DATABASE_SCHEMA.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/Document, Requirement, Chunk, EvidenceLookup, CoverageResult); C: `07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md` |
| A6 | Atharv | R: `03_VERITY_DATA_SCHEMAS.md`, `07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/RetrievalResult, Evidence, Provenance, Citation, SearchResult, EvidenceLookup); C: `06_VERITY_RETRIEVAL_CONTRACT.md` |
| A7 | Atharv | R: `15_VERITY_MODULE_BOUNDARIES.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/IngestResult, SearchResult, CoverageResult, Error) |
| A8 | Atharv | R: `09_VERITY_MCP_CONTRACT.md`, `10_VERITY_CLINE_SDK_CONTRACT.md`, `11_VERITY_API_V1_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/SearchRequest, SearchResult, EvidenceLookup, CoverageRequest, CoverageResult, ChatSession, ChatResponse) |
| A9 | Atharv | R: `18_VERITY_CONTRACT_TEST_PLAN.md`, `20_VERITY_IMPLEMENTATION_BASELINE.md`; C: `09_VERITY_MCP_CONTRACT.md`, `10_VERITY_CLINE_SDK_CONTRACT.md`, `11_VERITY_API_V1_CONTRACT.md`, `12_VERITY_COVERAGE_CONTRACT.md` |
| P0 | Piyush | R: `01_VERITY_CONTRACT_INDEX.md`, `06_VERITY_RETRIEVAL_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `20_VERITY_IMPLEMENTATION_BASELINE.md` |
| P1 | Piyush | R: `03_VERITY_DATA_SCHEMAS.md`, `05_VERITY_DOCUMENT_INGESTION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/ParsedDocument, ChunkDraft, SearchRequest) |
| P2 | Piyush | R: `04_VERITY_SPEC_SCHEMA.md`, `05_VERITY_DOCUMENT_INGESTION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/ParsedDocument, ParsedBlock, SpecRequirementDraft, SpecEntityDraft) |
| P3 | Piyush | R: `05_VERITY_DOCUMENT_INGESTION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/ParsedDocument, ParsedBlock, DocumentMetadata, Locator) |
| P4 | Piyush | R: `03_VERITY_DATA_SCHEMAS.md`, `05_VERITY_DOCUMENT_INGESTION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/ChunkDraft, Chunk, Requirement, SpecEntity) |
| P5 | Piyush | R: `05_VERITY_DOCUMENT_INGESTION_CONTRACT.md`, `13_VERITY_DATABASE_SCHEMA.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/IngestRequest, IngestResult, Document) |
| P6 | Piyush | R: `06_VERITY_RETRIEVAL_CONTRACT.md`, `13_VERITY_DATABASE_SCHEMA.md`, `14_VERITY_CONFIGURATION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/SearchRequest, RetrievalResult) |
| P7 | Piyush | R: `06_VERITY_RETRIEVAL_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/RetrievalResult) |
| P8 | Piyush | R: `06_VERITY_RETRIEVAL_CONTRACT.md`, `14_VERITY_CONFIGURATION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/Ranking, RetrievalResult) |
| P9 | Piyush | R: `06_VERITY_RETRIEVAL_CONTRACT.md`, `08_VERITY_MULTI_DOCUMENT_QUERY_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/SearchRequest, RetrievalResult, Ranking); C: `07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md` |
| P10 | Piyush | R: `18_VERITY_CONTRACT_TEST_PLAN.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/ParsedDocument, Chunk, Requirement, RetrievalResult); C: `05_VERITY_DOCUMENT_INGESTION_CONTRACT.md`, `06_VERITY_RETRIEVAL_CONTRACT.md`, `08_VERITY_MULTI_DOCUMENT_QUERY_CONTRACT.md` |
| V0 | Vandit | R: `09_VERITY_MCP_CONTRACT.md`, `11_VERITY_API_V1_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` |
| V1 | Vandit | R: `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/SearchResult, EvidenceLookup, CoverageResult, Error) |
| V2 | Vandit | R: `09_VERITY_MCP_CONTRACT.md`, `14_VERITY_CONFIGURATION_CONTRACT.md`, `17_VERITY_ERROR_CONTRACT.md` |
| V3 | Vandit | R: `09_VERITY_MCP_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/SearchRequest, CoverageRequest, requirement_id, evidence_id) |
| V4 | Vandit | R: `09_VERITY_MCP_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/SearchResult, Requirement, EvidenceLookup, CoverageResult, Error); C: `07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md` |
| V5 | Vandit | R: `11_VERITY_API_V1_CONTRACT.md`, `14_VERITY_CONFIGURATION_CONTRACT.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/Health, HttpError) |
| V6 | Vandit | R: `05_VERITY_DOCUMENT_INGESTION_CONTRACT.md`, `11_VERITY_API_V1_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/IngestRequest, IngestResult, ListPageDocument, ListPageSource, Document, Source) |
| V7 | Vandit | R: `11_VERITY_API_V1_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/SearchRequest, SearchResult, EvidenceLookup, CoverageRequest, CoverageResult, HttpError); C: `07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md` |
| V8 | Vandit | R: `10_VERITY_CLINE_SDK_CONTRACT.md`, `11_VERITY_API_V1_CONTRACT.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/ChatInput, ChatSession, ChatResponse, HttpError) |
| V9 | Vandit | R: `09_VERITY_MCP_CONTRACT.md`, `11_VERITY_API_V1_CONTRACT.md`, `17_VERITY_ERROR_CONTRACT.md`, `18_VERITY_CONTRACT_TEST_PLAN.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/Error, HttpError plus each response) |
| V10 | Vandit | R: `09_VERITY_MCP_CONTRACT.md`, `18_VERITY_CONTRACT_TEST_PLAN.md`, `20_VERITY_IMPLEMENTATION_BASELINE.md` |
| N0 | Vanashree | R: `12_VERITY_COVERAGE_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `20_VERITY_IMPLEMENTATION_BASELINE.md` |
| N1 | Vanashree | R: `03_VERITY_DATA_SCHEMAS.md`, `12_VERITY_COVERAGE_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/Requirement, CodeEvidence, TestEvidence, RequirementCoverage) |
| N2 | Vanashree | R: `12_VERITY_COVERAGE_CONTRACT.md`, `14_VERITY_CONFIGURATION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `17_VERITY_ERROR_CONTRACT.md` |
| N3 | Vanashree | R: `12_VERITY_COVERAGE_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/CodeEvidence, TestEvidence, Locator) |
| N4 | Vanashree | R: `03_VERITY_DATA_SCHEMAS.md`, `12_VERITY_COVERAGE_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/Requirement, AcceptanceCriterion, CodeEvidence, TestEvidence, RequirementCoverage, CoverageStatus) |
| N5 | Vanashree | R: `12_VERITY_COVERAGE_CONTRACT.md`, `14_VERITY_CONFIGURATION_CONTRACT.md`, `16_VERITY_PUBLIC_INTERFACES.md` |
| N6 | Vanashree | R: `12_VERITY_COVERAGE_CONTRACT.md`, `13_VERITY_DATABASE_SCHEMA.md`, `16_VERITY_PUBLIC_INTERFACES.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/CoverageRequest, CoverageResult, RequirementCoverage, coverage_id) |
| N7 | Vanashree | R: `12_VERITY_COVERAGE_CONTRACT.md`, `18_VERITY_CONTRACT_TEST_PLAN.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/CoverageResult, RequirementCoverage, Error) |
| U1 | Vanashree | R: `11_VERITY_API_V1_CONTRACT.md`, `17_VERITY_ERROR_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/HttpError, Document, SearchResult, CoverageResult) |
| U2 | Vanashree | R: `11_VERITY_API_V1_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/ListPageDocument, ListPageSource, IngestResult, Document, Source) |
| U3 | Vanashree | R: `03_VERITY_DATA_SCHEMAS.md`, `07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md`, `11_VERITY_API_V1_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/SearchResult, Evidence, Citation, EvidenceLookup) |
| U4 | Vanashree | R: `11_VERITY_API_V1_CONTRACT.md`, `12_VERITY_COVERAGE_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/CoverageResult, RequirementCoverage, CodeEvidence, TestEvidence) |
| U5 | Vanashree | R: `10_VERITY_CLINE_SDK_CONTRACT.md`, `11_VERITY_API_V1_CONTRACT.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/ChatResponse, ChatSession, Evidence, Citation, HttpError) |
| U6 | Vanashree | R: `11_VERITY_API_V1_CONTRACT.md`, `18_VERITY_CONTRACT_TEST_PLAN.md`, `21_VERITY_V1_JSON_SCHEMAS.json` ($defs/HttpError, SearchResult, CoverageResult, ChatResponse) |

## Blocker-to-task/PR gate

| Blocker | Tasks | PR hard stop | Mock work that continues |
|---|---|---|---|
| D1 | A6, P9 | PR-A3, PR-P3 | Fake retrieval output, candidate/fusion/rerank tests |
| D2 | N3, N6, N7 | PR-N2 | Fake snapshot/store evaluator and UI mock |
| D3 | A5, A6 | PR-A3 | Active-version readers and evidence fixtures |
