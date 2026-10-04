# Canonical v1 data schemas and identifiers

**Owner:** Atharv. **Consumers:** Piyush, Vandit, Vanashree, SDK/UI. **Schema and metadata version:** 1.0.0. This is the single model authority. JSON property names are snake_case. UTC times are RFC 3339 with `Z`. Strings are UTF-8. `null` is explicit; omitted required properties are invalid. Unless stated, arrays default to `[]` and all other fields have no default. IDs are opaque to consumers.

## Identifier registry

| ID | Format / generation owner | Scope and stability | Example |
|---|---|---|---|
| `source_id` | UUIDv4 lowercase string; persistence creates on source registration | Global in local DB; stable across reingest and path change via explicit source update | `24da624f-7fd0-41ea-a49b-8449cbb179d9` |
| `document_id` | UUIDv4; persistence creates with first source ingestion | Global; stable across reingest of that source; v1 one source ↔ one document | `ebc2352e-ff9c-4167-b11a-1e30d550411d` |
| `version_id` | UUIDv4; ingestion creates for changed bytes | Global; unchanged hash reingest returns existing active version; changed bytes create new version | `129dcd06-1ba1-4f0c-bf7e-c678f905b624` |
| `block_id` | `blk_` + 64 lowercase hex SHA-256 of version ID, ordinal, text | Version-specific deterministic | `blk_` plus 64 hex |
| `chunk_id` | `chk_` + 64 lowercase hex SHA-256 of version ID, block span, offsets, kind, text | Version-specific deterministic; changed chunk is a new ID | `chk_` plus 64 hex |
| `requirement_id` | `req_` + 64 lowercase hex SHA-256 of source ID and `local_id` | Stable across spec revisions for same source/local ID; unique across sources | `req_` plus 64 hex |
| `local_id` | `REQ-[0-9]{3,}`; parser reads author text | Unique within one spec version; never generated | `REQ-003` |
| `evidence_id` | `ev_` + 64 lowercase hex SHA-256 of version ID and chunk ID | Stable for that immutable chunk; resolver checks original version | `ev_` plus 64 hex |
| `session_id` | UUIDv4; SDK bridge creates | In-memory chat session; restart invalidates unless later persistence is contracted | `d48e07b1-2850-414c-9a37-65c900e463a8` |
| `coverage_id` | UUIDv4; coverage service creates per scan | Immutable run identity | `c3ddf6fc-feba-4489-a8c1-129d97312b6b` |
| `request_id` | UUIDv4; each transport adapter creates if absent | One request, for tracing; optional client supplied HTTP `X-Request-ID` only if valid UUIDv4 | `b4031e7a-9294-4a46-802f-43a738fdb713` |

`source_key` is an optional human slug (`[a-z0-9][a-z0-9._-]{0,63}`) from spec metadata; it is not an identity or a substitute for `source_id`, and need not be globally unique. `API-001` and `AC-001` are local entity IDs, not `requirement_id`; only `REQ-*` records enter coverage. `requirement_id` is the canonical API lookup key. Source ID plus local ID prevents collisions between specs. All SHA-256 inputs use UTF-8 canonical JSON with sorted keys, `ensure_ascii=false`, separators `,` and `:`, and NFC-normalized string values. Exact payloads are: block `{"version_id":uuid,"ordinal":n,"text":text}`; chunk `{"version_id":uuid,"block_start":n,"block_end":n,"start_offset":n|null,"end_offset":n|null,"kind":kind,"text":text}`; requirement `{"source_id":uuid,"local_id":local_id}`; evidence `{"version_id":uuid,"chunk_id":chunk_id}`. Hash the encoded JSON bytes, then prepend `blk_`, `chk_`, `req_` or `ev_`. No module independently invents ID hashing.

Golden ID vector (all strings exactly as shown): `version_id=129dcd06-1ba1-4f0c-bf7e-c678f905b624`, `source_id=24da624f-7fd0-41ea-a49b-8449cbb179d9`, block `(ordinal=0,text="Refund window")` yields `blk_75c2eccdd286a5d1218d15d0d80f0f65356359458fd641fa25e7e9e117f6cfff`; chunk `(block_start=0,block_end=1,start_offset=null,end_offset=null,kind="requirement",text="Refund requests MUST be accepted only within 30 days.")` yields `chk_71bb4eb1f7917adbd4771acd9946ee1a30994af19c4ebbf66ecd2b1e4b89b16a`; `local_id=REQ-001` yields `req_1d89bd403b85bcab97977f891a494c9788e5b7571e43a938c3b2d08c454ffbd2`; the version/chunk pair yields `ev_0a9948f2aa8b8cc5e499ef43626c5847eeab8df548ba5961e38a9a1126e4dc8e`.

## Shared scalar and enum rules

`schema_version` and `metadata_version` are required strings equal to `1.0.0`. `page` is **integer ≥1 or null everywhere**. Line and character offsets are integer ≥1/≥0 or null. Page/line ranges are inclusive; character offsets are half-open `[start_offset,end_offset)`. A missing location is `null`, never zero or an invented page. `heading_path` is an ordered string array. `source_path` is a path relative to the configured source root, with `/` separators; never an absolute path on public output. `content_sha256` is 64 lowercase hex.

Enums: `DocumentKind=spec|general`; `DocumentStatus=pending|ready|partial|failed`; `ChunkKind=requirement|acceptance_criterion|api_definition|general_chunk|code_chunk`; `CoverageStatus=IMPLEMENTED|PARTIAL|MISSING|UNCERTAIN`; `RetrievalMode=hybrid|lexical_only|semantic_only`; `Completeness=complete|partial|empty`; `EvidenceBasis=text_match|symbol_match|static_check|test_execution`; `TestOutcome=not_run|passed|failed|error`; `IngestMode=auto|spec|general`. Unknown enum values fail v1 parsing.

## Field notation

Every table row is `field : JSON type; required?; nullable?; default; meaning/example; introduced`. `—` means no default. Objects do not allow unspecified fields on the v1 wire unless an `extensions` map is named.

### `Source`

| Field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `schema_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `source_id` | UUIDv4 string; Y/N; — | Registered local input identity | 1.0.0 |
| `source_key` | string or null; Y/Y; null | Human slug, e.g. `payments-api` | 1.0.0 |
| `source_path` | string; Y/N; — | Relative input path, e.g. `specs/payments.md` | 1.0.0 |
| `registered_at` | UTC date-time; Y/N; — | Registration time | 1.0.0 |

### `DocumentMetadata`

| Field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `metadata_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `title` | string or null; Y/Y; null | Spec title or parsed title | 1.0.0 |
| `source_key` | string or null; Y/Y; null | Authored spec slug, never identity | 1.0.0 |
| `project` | string or null; Y/Y; null | `payment-service` for specs | 1.0.0 |
| `spec_version` | string or null; Y/Y; null | Author's spec release, e.g. `1.0`; distinct from schema version | 1.0.0 |
| `language` | string or null; Y/Y; null | BCP 47 if known; `en` | 1.0.0 |
| `page_count` | integer ≥1 or null; Y/Y; null | PDF count when known | 1.0.0 |
| `parser_name` | string; Y/N; — | `pdf_text` | 1.0.0 |
| `parser_version` | string; Y/N; — | Parser implementation revision | 1.0.0 |
| `warnings` | string[]; Y/N; `[]` | Extraction limitations | 1.0.0 |

### `Document`

| Field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `schema_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `document_id`, `source_id`, `version_id` | UUIDv4 string each; Y/N; — | Logical document, source and active immutable version | 1.0.0 |
| `name` | string; Y/N; — | `payments-api.md` | 1.0.0 |
| `media_type` | string; Y/N; — | `text/markdown`, `application/pdf`, `text/plain`, code MIME | 1.0.0 |
| `kind` | `DocumentKind`; Y/N; — | `spec` or `general` | 1.0.0 |
| `status` | `DocumentStatus`; Y/N; — | `ready`; partial extraction stays `partial` | 1.0.0 |
| `content_sha256` | hex string; Y/N; — | Hash of original bytes | 1.0.0 |
| `metadata` | `DocumentMetadata`; Y/N; — | Metadata envelope above | 1.0.0 |
| `indexed_at` | UTC date-time or null; Y/Y; null | Last active index completion | 1.0.0 |

### `Requirement`

| Field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `schema_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `requirement_id` | `req_` hash; Y/N; — | Stable identity | 1.0.0 |
| `local_id` | `REQ-` ID; Y/N; — | `REQ-003` | 1.0.0 |
| `source_id`, `document_id`, `version_id` | UUIDv4 string each; Y/N; — | Owning source/document/version | 1.0.0 |
| `title`, `text` | nonempty string each; Y/N; — | Title and normative text | 1.0.0 |
| `constraints`, `edge_cases` | string[] each; Y/N; `[]` | Ordered authored clauses | 1.0.0 |
| `acceptance_criteria` | `AcceptanceCriterion[]`; Y/N; `[]` | Linked tests of behavior | 1.0.0 |
| `api_refs`, `reference_ids` | string[] each; Y/N; `[]` | Local `API-*` or `REQ-*`/`AC-*` references | 1.0.0 |
| `chunk_id` | `chk_` hash; Y/N; — | Primary retrieval unit | 1.0.0 |
| `evidence_id` | `ev_` hash; Y/N; — | Directly citable primary chunk | 1.0.0 |
| `locator` | `Locator`; Y/N; — | Source position | 1.0.0 |

`AcceptanceCriterion = {local_id: string matching AC-[0-9]{3,}, title: nonempty string, text: nonempty string, locator: Locator}`; all four fields required, nonnull, no defaults, introduced 1.0.0. `SpecEntity = {schema_version: "1.0.0", kind: "api_definition"|"acceptance_criterion", local_id: API-*|AC-* matching kind, title: nonempty string, text: nonempty string, reference_ids: string[], chunk_id: chk-hash, evidence_id: ev-hash, locator: Locator}`; all fields required and nonnull, `reference_ids` defaults `[]`, introduced 1.0.0. They are not `Requirement` objects. The `reference_ids` of an acceptance criterion contain its parent REQ local IDs.

Before IDs exist, the spec parser emits `SpecRequirementDraft = {local_id, title, text, constraints:string[], edge_cases:string[], api_refs:string[], reference_ids:string[], acceptance_local_ids:string[], block_start:int≥0, block_end:int≥0}` and `SpecEntityDraft = {kind, local_id, title, text, reference_ids:string[], block_start:int≥0, block_end:int≥0}`. All fields are required; arrays default `[]`; the block range is inclusive and valid against `ParsedDocument.blocks`. These drafts are internal cross-module data contracts introduced 1.0.0. The central materializer converts them to `Requirement` and `SpecEntity` after source/document/version IDs and chunks are assigned.

### `Locator`

| Field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `source_id`, `document_id`, `version_id` | UUIDv4 string each; Y/N; — | Exact origin | 1.0.0 |
| `source_path` | relative string; Y/N; — | `specs/payments.md` | 1.0.0 |
| `page` | integer ≥1 or null; Y/Y; null | `10` for PDF, null for Markdown | 1.0.0 |
| `heading_path` | string[]; Y/N; `[]` | `["Requirements","REQ-003"]` | 1.0.0 |
| `start_line`, `end_line` | integer ≥1 or null each; Y/Y; null | Inclusive source lines | 1.0.0 |
| `start_offset`, `end_offset` | integer ≥0 or null each; Y/Y; null | Half-open source character span | 1.0.0 |

The start/end pair is jointly present or null and ordered. A chunk across pages is forbidden in v1. PDF `page` has priority; line numbers on extracted PDF text remain null unless verified against source representation.

### `Chunk`

| Field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `schema_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `chunk_id` | `chk_` hash; Y/N; — | Retrieval unit ID | 1.0.0 |
| `kind` | `ChunkKind`; Y/N; — | `requirement`, `general_chunk` | 1.0.0 |
| `text` | nonempty string; Y/N; — | Exact normalized source passage | 1.0.0 |
| `locator` | `Locator`; Y/N; — | Exact original span | 1.0.0 |
| `block_start`, `block_end` | integer ≥0 each; Y/N; — | Inclusive normalized block ordinals | 1.0.0 |
| `ordinal` | integer ≥0; Y/N; — | Order within version | 1.0.0 |
| `requirement_id` | `req_` hash or null; Y/Y; null | Only linked spec units | 1.0.0 |

### `Provenance`, `Citation`, `Evidence`

| Object.field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `Provenance.schema_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `.content_sha256` | hex string; Y/N; — | Exact original-byte hash | 1.0.0 |
| `.parser_name`, `.parser_version`, `.chunker_version` | string each; Y/N; — | Processing identity | 1.0.0 |
| `.embedding_model` | string or null; Y/Y; null | Pinned model revision or null | 1.0.0 |
| `.indexed_at` | UTC date-time; Y/N; — | Index timestamp | 1.0.0 |
| `Citation.evidence_id` | `ev_` hash; Y/N; — | Machine link | 1.0.0 |
| `.label` | string; Y/N; — | Canonical display string | 1.0.0 |
| `.locator` | `Locator`; Y/N; — | Exact source | 1.0.0 |
| `Evidence.schema_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `.evidence_id` | `ev_` hash; Y/N; — | Resolvable ID | 1.0.0 |
| `.chunk_id` | `chk_` hash; Y/N; — | Exact chunk | 1.0.0 |
| `.kind` | `ChunkKind`; Y/N; — | Original chunk kind | 1.0.0 |
| `.quote` | nonempty string; Y/N; — | Verbatim normalized passage | 1.0.0 |
| `.requirement_id` | `req_` hash or null; Y/Y; null | Related explicit requirement | 1.0.0 |
| `.citation` | `Citation`; Y/N; — | One canonical citation | 1.0.0 |
| `.provenance` | `Provenance`; Y/N; — | Exact processing identity | 1.0.0 |
| `.score` | number or null; Y/Y; null | Final relevance score for search; null when direct lookup | 1.0.0 |
| `.ranking` | `Ranking`; Y/N; — | Branch/fusion scores; all null on direct lookup | 1.0.0 |

`Ranking = {dense_rank: integer≥1|null, lexical_rank: integer≥1|null, rrf_score: number|null, rerank_score: number|null}`; all fields required and nullable with null defaults, introduced 1.0.0. Search fills `rrf_score`; direct lookup sets all four to null. `Evidence.score` equals rerank score when used, otherwise RRF score.

### `SearchRequest`, `SearchResult`, `RetrievalResult`

| Object.field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `SearchRequest.query` | string length 2–2000; Y/N; — | User query | 1.0.0 |
| `.document_ids` | UUIDv4 string[] or null; Y/Y; null | null = all; `[]` invalid | 1.0.0 |
| `.document_kinds` | `DocumentKind[]` or null; Y/Y; null | null = all | 1.0.0 |
| `.chunk_kinds` | `ChunkKind[]` or null; Y/Y; null | null = all | 1.0.0 |
| `.limit` | integer 1–20; Y/N; 8 | Final result count | 1.0.0 |
| `.per_document_limit` | integer 1–20 or null; Y/Y; null | Cap after ranking when set | 1.0.0 |
| `RetrievalResult.chunk` | `Chunk`; Y/N; — | Canonical chunk | 1.0.0 |
| `.score` | number; Y/N; — | Reranker score if used, else RRF score | 1.0.0 |
| `.dense_rank`, `.lexical_rank` | integer ≥1 or null; Y/Y; null | Branch ranks | 1.0.0 |
| `.rrf_score`, `.rerank_score` | number / number or null; Y/N and Y/Y; — / null | Rank provenance | 1.0.0 |
| `SearchResult.schema_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `.query` | string; Y/N; — | Echoed normalized query | 1.0.0 |
| `.items` | `Evidence[]`; Y/N; `[]` | Ordered best first | 1.0.0 |
| `.retrieval_mode` | `RetrievalMode`; Y/N; — | Actual branches used | 1.0.0 |
| `.reranker_used` | boolean; Y/N; false | Actual model run | 1.0.0 |
| `.completeness` | `Completeness`; Y/N; — | Empty/partial/complete | 1.0.0 |
| `.omissions` | string[]; Y/N; `[]` | Missing capability names | 1.0.0 |
| `.total_returned` | integer ≥0; Y/N; — | Equals `items.length` | 1.0.0 |

Search result is not paginated in v1. `score` is meaningful only within one query; callers must not compare it across queries or models. Search returns `[]` and `empty` for no matches, not an error.

### `CodeEvidence`, `TestEvidence`, `RequirementCoverage`, `CoverageResult`

| Object.field | Type; R/N; default | Meaning / example | Since |
|---|---|---|---|
| `CodeEvidence.path` | relative `/` path; Y/N; — | `src/refund.py` | 1.0.0 |
| `.start_line`, `.end_line` | integer ≥1 each; Y/N; — | Inclusive code span | 1.0.0 |
| `.excerpt` | string; Y/N; — | Bounded source excerpt | 1.0.0 |
| `.basis` | `EvidenceBasis`; Y/N; — | `static_check` | 1.0.0 |
| `TestEvidence.path`, `.start_line`, `.end_line`, `.excerpt`, `.basis` | Same types/rules as CodeEvidence; Y/N; — | Test file evidence | 1.0.0 |
| `TestEvidence.outcome` | `TestOutcome`; Y/N; `not_run` | Observed execution only | 1.0.0 |
| `RequirementCoverage.requirement_id` | `req_` hash; Y/N; — | Target | 1.0.0 |
| `.status` | `CoverageStatus`; Y/N; — | `UNCERTAIN` | 1.0.0 |
| `.implementation` | `CodeEvidence[]`; Y/N; `[]` | Code evidence | 1.0.0 |
| `.tests` | `TestEvidence[]`; Y/N; `[]` | Test evidence | 1.0.0 |
| `.reason` | nonempty string; Y/N; — | Rule explanation | 1.0.0 |
| `.limitations` | string[]; Y/N; `[]` | Analysis gaps | 1.0.0 |
| `CoverageResult.schema_version` | string; Y/N; — | `1.0.0` | 1.0.0 |
| `.coverage_id` | UUIDv4; Y/N; — | Scan run | 1.0.0 |
| `.workspace_id` | config key string; Y/N; — | `demo` | 1.0.0 |
| `.workspace_revision` | SHA-256 hex; Y/N; — | Deterministic file manifest hash | 1.0.0 |
| `.inspected_at` | UTC date-time; Y/N; — | Scan time | 1.0.0 |
| `.results` | `RequirementCoverage[]`; Y/N; `[]` | Input order preserved | 1.0.0 |
| `.limitations` | string[]; Y/N; `[]` | Run-wide gaps | 1.0.0 |

### `Error`

`Error = {schema_version, code, message, details, request_id, retryable}`. All six fields required and nonnull except `details` (object or null, default null). `schema_version=1.0.0`; `code` is the enum in `17`; `message` is safe user-facing text; `request_id` is UUIDv4; `retryable` boolean defaults false. Introduced 1.0.0. Raw tracebacks, secrets and absolute host paths are never public.
