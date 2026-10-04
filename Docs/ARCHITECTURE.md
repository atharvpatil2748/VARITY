# VERITY architecture and implementation specification

> Fixed implementation contracts: [Docs/contracts/01_VERITY_CONTRACT_INDEX.md](contracts/01_VERITY_CONTRACT_INDEX.md). The contract package supersedes proposed interface details below.

> **Current Cline architecture (documentation patch 1.0.1):** Cline SDK powers the native VERITY agent UI; MCP exposes VERITY to external Cline clients. Both reach the same `VerityService` and canonical retrieval, Evidence and coverage interfaces. The original PPTX below is a historical hackathon pitch that ranked the embedded SDK UI as stretch; the current product architecture specifies how native chat works whenever it is implemented. Eight-hour sequencing may still deliver the backend/external MCP demo first. See the [SDK contract](contracts/10_VERITY_CLINE_SDK_CONTRACT.md) and [PPT/demo addendum](pptx/VERITY_CLINE_INTEGRATION_DEMO_ADDENDUM.md).

**Status:** proposed, pre-implementation  
**Audience:** Atharv Patil, Piyush Ghayal, Vandit Gupta, Vanashree  
**Source baseline:** `Docs/pptx/VERITY_Cline_Hackathon_Round1_v2.pptx`, all 10 slides and speaker notes; local `Desktop/Mnemo` source and current architecture/roadmap, inspected 4 October 2026.  
**Scope:** eight-hour offline hackathon. This file is a design. No VERITY implementation was present when it was written.

The presentation uses **VERITY** while the checkout is named `VARITY`. This specification uses the product spelling **VERITY** and lives in the existing `VARITY/Docs` directory. The team should settle the package and display spelling before creating source files.

## Phase 1 — Source audit

### VERITY presentation

The deck's core claim is “Your documents. Your specs. Evidence that Cline can cite.” Slides 2–4 identify skipped clauses, invented implementation details, and missing links between code and source requirements. Its flow is documents → knowledge space → evidence → Cline → implementation and coverage. Slide 5 defines five must-haves: ingestion, BGE-M3 plus FTS5 hybrid retrieval, cited evidence, MCP tools, and coverage. Slides 6–7 originally prioritized Cline connected through MCP and placed the embedded Cline SDK agent/UI later in the hackathon schedule. The current architecture calls that MCP user an **external Cline client** and makes Cline SDK the agent runtime of the **native VERITY chat UI**. Slide 8's refund coverage output is explicitly illustrative; slide 9 calls for a measured with/without comparison on 8–10 tasks. Speaker notes confirm the original pitch priorities. The supplied brief extends the knowledge layer to general documents and makes multi-document retrieval a core feature.

### Mnemo findings from actual files

Paths below are relative to `C:/Users/athar/Desktop/Mnemo`. “Implemented” means relevant code exists and was inspected. It does not claim independent production certification. Mnemo's own certification statements are narrower than its broad architectural targets.

| Component and file | Observed responsibility and status | VERITY decision |
|---|---|---|
| `mnemo-core/mnemo/interfaces/parser.py`, `interfaces/parser_models.py`, `parsers/router.py`, `parsers/{pdf,markdown,plain_text,pptx,docx,xlsx,html,json_parser,csv_parser}.py` | **Implemented.** Pure parser protocol accepts bytes, filename, metadata; router chooses parser from MIME/extension and hashes bytes. PDF parser records page numbers. | **Adapt** small parser protocol and PDF/MD/TXT/code dispatch; defer broad format set and asset extraction. |
| `models/documents.py`, `models/blocks.py`, `ingestion/canonicalizer.py`, `ingestion/pipeline.py` | **Implemented.** Typed ordered blocks become `ParsedDocument`; document versions and content hashes separate source identity from parsed content. | **Adapt** normalized blocks, content hash, version and provenance. Keep one compact schema. |
| `interfaces/chunker.py`, `models/chunks.py`, `chunkers/dispatcher.py`, `chunkers/{markdown,code,generic}.py` | **Implemented.** Strategies emit drafts; dispatcher validates and assigns deterministic content-derived IDs. Chunks carry block span, heading path, page/offset, parent identity. | **Adapt** heading-aware and page-safe chunking; avoid all nine strategies and complex parent promotion in MVP. |
| `embeddings/{cached,sentence_transformers,ollama}.py`, `interfaces/embedding.py` | **Implemented.** Provider contract, batches and hash-based cache. | **Adapt** provider abstraction. Use pre-provisioned local BGE-M3; cache by `(model revision, text hash)`. |
| `storage/sqlite.py`, `storage/v2_runtime.py`, `storage/retrieval_projection.py` | **Implemented.** `fts_chunks`/`fts_chunk_titles` FTS5 tables; `search_sparse()` uses BM25 with escaped terms and scope filters. V1 `SQLiteStore.search_dense()` raises `NotImplementedError`; certified V2 has a separate SQLite vector path. | **Redesign smaller.** One writable SQLite DB, FTS5, and a bounded vector table with in-process cosine scan for demo scale. Do not mistake V1 facade for working dense search. |
| `retrieval/full_multilingual_v2.py`, `retrieval/fusion.py`, `retrieval/reranker.py`, `retrieval/context.py` | **Implemented.** V2 runs dense/sparse retrieval, fuses identities with `1/(60 + rank)`, bounds reranker candidates, falls back to fused order on reranker failure, and reports omissions. Context builder enforces a token budget. | **Adapt** RRF, deterministic ties, bounded rerank, completeness/omission reporting, and context limits. |
| `models/citation.py`, `retrieval/citation.py`, `models/v2_evidence_resolution.py` | **Implemented.** Citation/provenance models link quoted text to document/chunk/position. | **Adapt** quote plus resolvable locator; cite exact version. |
| `mnemo-server/mnemo_server/services/retrieval_v2.py`, `routers/retrieval_v2.py`, `mcp/{server,tools,contracts}.py` | **Implemented.** HTTP/MCP adapters invoke an application service; MCP tool route contracts exist. Some MCP handlers serialize JSON as text; do not assume all outputs are natively structured. | **Adapt** thin MCP-to-service boundary. Return MCP `structuredContent` when supported, with JSON text fallback. |
| `mnemo-server/mnemo_server/tests/test_retrieval_v2.py`, `tests/test_mcp_tools.py`, core tests and evaluation scripts | **Implemented.** Relevant tests exist for retrieval/MCP contracts and milestone verification. | **Adapt** small contract and end-to-end fixtures, not Mnemo's large governance suite. |
| `mnemo-core/mnemo/storage/qdrant.py`, `storage/surrealdb.py` | **Partially implemented / future production path.** Qdrant is optional V1 or future scale; SurrealDB graph is partial per current README/roadmap. | **Do not use** in eight-hour build. |
| `mnemo-ui/src`, current roadmap Phase 9, Phase 11 | UI scaffold **partially implemented**; production web UI and multi-hop cross-document reasoning **planned**, according to current roadmap. Cross-document retrieval exists, but graph reasoning is a different claim. | **Redesign** a minimal VERITY UI only after MCP demo works. Cline handles synthesis. |

Mnemo's current README and `docs/architecture/current/mnemo_architecture_v2.md` describe a certified 44-document V2 composition, not a generic benchmark at 100,000 documents. The roadmap still gates its production UI and calls multi-hop reasoning future work. VERITY should borrow interfaces and failure handling, not copy Mnemo's storage governance, notebook system, multimodal pipeline, or proprietary code. Reuse of actual Mnemo source requires a separate rights decision: its current tree declares all rights reserved, so this plan calls for independent implementation of the patterns.

### Gaps this project must fill

No VERITY source, schema, coverage verifier, MCP server, SDK integration, tests, or UI existed in this checkout at audit time. Mnemo has no VERITY requirement schema or requirement-to-code verifier to transplant. Exact Cline SDK package behavior must be checked against the installed version before implementing native chat; the current official SDK reference is linked in Phase 7.

## Phase 2 — Final product definition

VERITY is a persistent, local-first, inspectable knowledge and evidence service for documents. It ingests both explicit, verifiable specifications and ordinary reference material, retrieves cited passages across documents, and exposes evidence through MCP to Cline and other compatible agents. The flagship workflow uses those requirements to guide coding and then inspects the workspace for implementation and test evidence. Cline reasons, writes code and composes answers; VERITY stores sources, retrieves passages, creates citations and reports the limits of verification.

Principles: preserve original bytes and source coordinates; distinguish explicit requirements from ordinary text; make evidence resolvable and versioned; keep retrieval and tool transports separate; expose uncertainty; work offline with local models; keep expensive steps optional without silently claiming they ran. Developer/spec implementation is the first sprint priority. Cross-document technical research is a second MVP demonstration. The native VERITY chat UI is Cline-SDK-powered; its implementation may follow the backend/MCP baseline in the eight-hour schedule. UI polish is lower priority.

## Phase 3 — Final architecture

```text
spec MD                         PDF / MD / TXT / code
   |                                   |
strict spec parser                 parser registry
   |                                   |
requirements + blocks         canonical blocks + positions
   +-----------------+-----------------+
                     |
          versioned documents + retrieval units
                     |
       SQLite canonical rows + FTS5 + vector rows
                     |
       dense / lexical -> RRF -> optional reranker
                     |
          evidence service + citation resolver
                     |
          VerityService application boundary
             /                   \
      MCP stdio tools         canonical SDK tools
           |                         |
   external Cline client      Cline SDK agent
           |                         |
    code changes             native VERITY chat UI
           |                         |
    workspace inspector       renders SDK answer + Evidence
           |
    coverage report
```

The application API owns `ingest`, `search_evidence`, `get_requirement`, `get_evidence`, `compare_sources`, and `check_coverage`. CLI, MCP, optional HTTP, and SDK adapters call it. No transport writes its own SQL or ranks results. Spec documents and general documents share `retrieval_units`; each unit has a `kind` (`requirement`, `acceptance_criterion`, `general_chunk`, `code_chunk`). Requirement records additionally preserve machine-readable relations. All retrieval filters apply before ranking. Search can span all indexed documents by default or restrict document IDs. The answer composer is Cline, never an uncredited VERITY LLM answer.

## Phase 4 — Data and ingestion

### Canonical VERITY Spec Schema v1

The deterministic authoring format is Markdown with YAML front matter and mandatory headings. It is a schema for executable specifications, not for arbitrary documents. The MVP accepts UTF-8 Markdown only for structured specs; PDFs containing apparent `REQ-` strings remain general documents unless explicitly converted and reviewed. A validator rejects duplicate IDs, dangling references, empty normative text and malformed metadata. It never silently invents requirement IDs.

```markdown
---
verity_spec: 1
project: payment-service
title: Payment API Specification
version: "1.0"
source_id: payments-api
---

# Requirements
## REQ-001: Refund window
Refund requests MUST be accepted only within 30 days.

### Constraints
- A request after 30 days MUST return REFUND_WINDOW_EXPIRED.

### Edge cases
- The boundary at exactly 30 days is accepted.

## REQ-002: Partial refund
The API MUST support partial refunds.

# API definitions
## API-001: POST /refunds
Request fields: payment_id, amount, idempotency_key.

# Acceptance criteria
## AC-001: Late refund rejection
Given a payment older than 30 days, POST /refunds returns REFUND_WINDOW_EXPIRED.
References: REQ-001, API-001
```

Top-level sections allowed: `Requirements`, `API definitions`, `Acceptance criteria`, `References`. Requirement children may be `Constraints`, `Edge cases`, `References`. IDs match `^(REQ|API|AC)-[0-9]{3,}$` and are unique within `(project, source_id, version)`; stable public key is `source_id@version#REQ-001`. Metadata requires `verity_spec`, `project`, `title`, `version`, `source_id`; optional `authors`, `created`, `tags`. Each entity stores type, ID, title, normative text, child constraints/edge cases, related IDs, source span and heading. Acceptance criteria link to one or more requirements. API definitions are reference entities and do not automatically count as covered requirements. Schema evolution uses the `verity_spec` integer and rejects unsupported versions.

### Storage model

| Record | Required fields and rules |
|---|---|
| `documents` | `document_id` UUID, display name, normalized local path, media type, `kind`, SHA-256, ingestion timestamp, active version. Paths stay local and are never treated as citation identity. |
| `document_versions` | `version_id`, `document_id`, content hash, parser version, status, original-byte location. Reingest changes version and invalidates its derived index rows atomically. |
| `blocks` | `block_id`, version, ordinal, text, type, page, heading path, character and optional line offsets. Offsets refer to original text when known; otherwise null. |
| `requirements` | `requirement_key`, version, local ID, entity type, title, normative text, JSON relations, source block span. Unique per version. |
| `retrieval_units` | `unit_id`, version, `kind`, text, heading, page/line/offset range, optional requirement key, block span, ordinal. ID is SHA-256 of version ID + span + text + kind. |
| `embeddings` | unit ID, model ID/revision, dimension, normalized vector BLOB, text hash, created time. Model change triggers re-embedding, not citation change. |
| `evidence` | Search result is derived, not a mutable truth record: evidence ID resolves `(version_id, unit_id)` and quote/locator. |
| `coverage_runs` | Optional immutable report with workspace root hash/revision, requirement version, inspector version, time, status and code/test citations. Never a manually editable status table. |

SQLite foreign keys and one transaction per document version prevent partial ingestion. FTS5 indexes `retrieval_units.text`, title/heading and ID, with triggers or explicit transactional updates. Store originals in `data/originals/<sha256>`; content hash detects duplicates. Back up SQLite with its backup API. Use WAL for local concurrent reads. There is no Qdrant or graph database requirement.

### General ingestion and chunking

`Parser.parse(bytes, filename) -> ParsedDocument(blocks, metadata, warnings)` is pure. Built-ins: PDF (per-page text with page number), Markdown (heading-aware blocks), TXT (paragraph blocks), and source code (file/line blocks, language from extension). Avoid claiming OCR for scanned PDFs. Unsupported or image-only pages produce warnings and `partial` ingestion. `Chunker.chunk(ParsedDocument) -> UnitDraft[]` is deterministic. A spec requirement is one retrieval unit, with long constraints split only when needed and always linked to the parent key. Markdown/TXT split on headings then paragraphs, target 300–600 tokens with 50-token overlap; do not cross page or heading boundaries. Code splits by function/class when a safe parser exists, otherwise bounded line windows with line ranges. Overlap units share text but retain distinct spans; citation resolver uses exact original position. The central materializer validates spans and assigns IDs before persistence.

Embed in batches after the canonical transaction, marking units `pending`, `ready` or `failed`. A retry resumes failed embeddings. The lexical index is usable even if the local embedding model is unavailable; the API declares `retrieval_mode: lexical_only` and names the omission. Pre-download and test BGE-M3 and optional BGE reranker before the offline event. Embedding and reranker model revision, dimension and normalization are recorded in config and index metadata.

## Phase 5 — Retrieval and evidence

`search_evidence(query, document_ids?, kinds?, limit=8)` retrieves up to 50 lexical and 50 semantic candidates from the same authorized document set. FTS5 uses parameterized, escaped terms and BM25; semantic ranking uses normalized BGE-M3 vectors with cosine similarity. For a bounded demo corpus, scan stored vectors in-process; set a measured size ceiling and report when exceeded. Deduplicate on `unit_id`, never on text alone. Fuse each ranked list with `score(u) = Σ 1/(60 + rank_i(u))`. Tie-break by `unit_id`. Rerank the top 30 fused units with local BGE reranker if available, otherwise retain RRF order and set `reranker_used: false`. Final result count is independent of candidate pool. Filter by document first, then rank. For multi-document queries, the same call searches all documents; source grouping is presentation metadata, not a different algorithm. An optional diversity rule may reserve one result per relevant source after scoring but must disclose its use.

Every result contains a verbatim quote, document/version ID, display name, unit ID, optional requirement key, page/heading/line/offset, score provenance (dense rank, lexical rank, RRF score, rerank score), and `citation_label` such as `payments-api.pdf p.10, REQ-003`. Labels are display strings; stable references are IDs. `get_evidence` resolves an ID against the stored version, verifies the quote still matches, and returns adjacent context within a byte/token cap. Deleted/superseded versions must remain resolvable for historical citations or return `STALE_EVIDENCE`, never silently bind a new version. Cline's answer should cite returned evidence IDs; the UI validates cited IDs against tool results and renders source links. Cline is responsible for synthesis, including agreement/conflict statements; `compare_sources` supplies grouped excerpts and may label a relation `unassessed` until an evaluator exists. A provenance trace reports ingest hash, parser/chunker/model versions and source span, not fabricated confidence.

Evaluation fixtures should contain an exact requirement clause, a paraphrase, a term collision, and a three-document query. Measure recall@5 for known evidence IDs, citation resolution success, per-source coverage, reranker latency and lexical-only behavior. For the deck's with/without study, freeze the same tasks, specs, model and scoring rubric; report observed results rather than anticipated gains.

## Phase 6 — MCP and exact tool contracts

The smallest coherent MVP surface is **four tools**: `search_evidence`, `get_requirement`, `get_evidence`, `check_coverage`. `search_evidence` already searches multiple documents, so `search_knowledge` and `search_multi_document` would be aliases. `trace_provenance` is part of `get_evidence`. `compare_sources` is a fifth, should-have tool only if time permits. All tools call the same application API used by SDK tools. MCP stdio is primary; stdout carries protocol only and diagnostics go to stderr. Pin and test the installed MCP SDK's structured-result behavior; expose `structuredContent` plus JSON text compatibility if required by Cline. Cap query length, result count, output bytes and time.

The following JSON Schemas define application payloads and MCP input schemas. They use JSON Schema Draft 2020-12 syntax. `$defs` is shared across tool outputs; in implementation, publish a bundled schema per tool for clients that cannot resolve external references.

```json
{
  "$defs": {
    "Error": {"type":"object","additionalProperties":false,"required":["code","message","retryable"],"properties":{"code":{"type":"string","enum":["INVALID_ARGUMENT","NOT_FOUND","STALE_EVIDENCE","UNSUPPORTED_FORMAT","MODEL_UNAVAILABLE","INDEX_NOT_READY","WORKSPACE_DENIED","TIMEOUT","INTERNAL"]},"message":{"type":"string"},"retryable":{"type":"boolean"}}},
    "Locator": {"type":"object","additionalProperties":false,"required":["document_id","version_id","unit_id","document_name","source_path","page","heading_path","start_line","end_line","start_offset","end_offset"],"properties":{"document_id":{"type":"string","format":"uuid"},"version_id":{"type":"string","format":"uuid"},"unit_id":{"type":"string"},"document_name":{"type":"string"},"source_path":{"type":"string"},"page":{"type":["integer","null"],"minimum":1},"heading_path":{"type":"array","items":{"type":"string"}},"start_line":{"type":["integer","null"],"minimum":1},"end_line":{"type":["integer","null"],"minimum":1},"start_offset":{"type":["integer","null"],"minimum":0},"end_offset":{"type":["integer","null"],"minimum":0}}},
    "Evidence": {"type":"object","additionalProperties":false,"required":["evidence_id","kind","quote","requirement_key","citation_label","locator","scores"],"properties":{"evidence_id":{"type":"string"},"kind":{"type":"string","enum":["requirement","acceptance_criterion","general_chunk","code_chunk"]},"quote":{"type":"string"},"requirement_key":{"type":["string","null"]},"citation_label":{"type":"string"},"locator":{"$ref":"#/$defs/Locator"},"scores":{"type":"object","additionalProperties":false,"required":["dense_rank","lexical_rank","rrf","rerank"],"properties":{"dense_rank":{"type":["integer","null"]},"lexical_rank":{"type":["integer","null"]},"rrf":{"type":"number"},"rerank":{"type":["number","null"]}}}}},
    "CodeLocation": {"type":"object","additionalProperties":false,"required":["path","start_line","end_line","excerpt","basis"],"properties":{"path":{"type":"string"},"start_line":{"type":"integer","minimum":1},"end_line":{"type":"integer","minimum":1},"excerpt":{"type":"string"},"basis":{"type":"string","enum":["text_match","symbol_match","static_check","test_execution"]}}},
    "ToolFailure": {"type":"object","additionalProperties":false,"required":["ok","error"],"properties":{"ok":{"const":false},"error":{"$ref":"#/$defs/Error"}}}
  }
}
```

Each response is either its success schema or `ToolFailure` (`oneOf`). Errors remain structured; MCP protocol errors are reserved for transport failures. No tool accepts a caller-supplied absolute path to arbitrary source files except the configured, validated workspace root in coverage.

### `search_evidence` → `VerityService.search_evidence`

Purpose: hybrid search across all documents or an explicit subset. This is also the multi-document search tool.

```json
{
  "input": {"type":"object","additionalProperties":false,"required":["query"],"properties":{"query":{"type":"string","minLength":2,"maxLength":2000},"document_ids":{"type":"array","uniqueItems":true,"maxItems":100,"items":{"type":"string","format":"uuid"}},"kinds":{"type":"array","uniqueItems":true,"items":{"type":"string","enum":["requirement","acceptance_criterion","general_chunk","code_chunk"]}},"limit":{"type":"integer","minimum":1,"maximum":20,"default":8}}},
  "success": {"type":"object","additionalProperties":false,"required":["ok","query","items","retrieval_mode","reranker_used","completeness","omissions"],"properties":{"ok":{"const":true},"query":{"type":"string"},"items":{"type":"array","items":{"$ref":"#/$defs/Evidence"}},"retrieval_mode":{"type":"string","enum":["hybrid","lexical_only","semantic_only"]},"reranker_used":{"type":"boolean"},"completeness":{"type":"string","enum":["complete","partial","empty"]},"omissions":{"type":"array","items":{"type":"string"}}}}
}
```

Example input: `{"query":"duplicate refund security controls","limit":5}`. Example output excerpt: `{"ok":true,"query":"duplicate refund security controls","items":[{"evidence_id":"ev:...","kind":"requirement","quote":"Duplicate requests must be rejected.","requirement_key":"payments-api@1.0#REQ-003","citation_label":"payments-api.md § Requirements, REQ-003","locator":{"document_id":"...","version_id":"...","unit_id":"...","document_name":"payments-api.md","source_path":"...","page":null,"heading_path":["Requirements","REQ-003"],"start_line":20,"end_line":21,"start_offset":null,"end_offset":null},"scores":{"dense_rank":2,"lexical_rank":1,"rrf":0.0325,"rerank":0.88}}],"retrieval_mode":"hybrid","reranker_used":true,"completeness":"complete","omissions":[]}`. IDs shown as `...` are illustrative, not valid schema instances. Errors: `INVALID_ARGUMENT`, `INDEX_NOT_READY`, `MODEL_UNAVAILABLE` only if neither branch can run, `TIMEOUT`.

### `get_requirement` → `VerityService.get_requirement`

```json
{
  "input": {"type":"object","additionalProperties":false,"required":["requirement_key"],"properties":{"requirement_key":{"type":"string","pattern":"^[A-Za-z0-9._-]+@[^#]+#(REQ|API|AC)-[0-9]{3,}$"}}},
  "success": {"type":"object","additionalProperties":false,"required":["ok","requirement_key","entity_type","title","text","constraints","edge_cases","related_keys","evidence"],"properties":{"ok":{"const":true},"requirement_key":{"type":"string"},"entity_type":{"type":"string","enum":["requirement","api_definition","acceptance_criterion"]},"title":{"type":"string"},"text":{"type":"string"},"constraints":{"type":"array","items":{"type":"string"}},"edge_cases":{"type":"array","items":{"type":"string"}},"related_keys":{"type":"array","items":{"type":"string"}},"evidence":{"$ref":"#/$defs/Evidence"}}}
}
```

Example input: `{"requirement_key":"payments-api@1.0#REQ-003"}`. Output excerpt: `{"ok":true,"requirement_key":"payments-api@1.0#REQ-003","entity_type":"requirement","title":"Duplicate requests","text":"Duplicate refund requests must be rejected.","constraints":[],"edge_cases":[],"related_keys":[],"evidence":{...}}`. The full `evidence` value follows the shared schema. This returns exact normative text, not inferred status. Errors: `INVALID_ARGUMENT`, `NOT_FOUND`, `STALE_EVIDENCE`.

### `get_evidence` → `VerityService.get_evidence`

Purpose: resolve a citation and trace provenance, with bounded adjacent source context.

```json
{
  "input": {"type":"object","additionalProperties":false,"required":["evidence_id"],"properties":{"evidence_id":{"type":"string","minLength":8},"context_chars":{"type":"integer","minimum":0,"maximum":4000,"default":1000}}},
  "success": {"type":"object","additionalProperties":false,"required":["ok","evidence","context_before","context_after","provenance"],"properties":{"ok":{"const":true},"evidence":{"$ref":"#/$defs/Evidence"},"context_before":{"type":"string"},"context_after":{"type":"string"},"provenance":{"type":"object","additionalProperties":false,"required":["content_sha256","parser_version","chunker_version","embedding_model","indexed_at"],"properties":{"content_sha256":{"type":"string","pattern":"^[a-f0-9]{64}$"},"parser_version":{"type":"string"},"chunker_version":{"type":"string"},"embedding_model":{"type":["string","null"]},"indexed_at":{"type":"string","format":"date-time"}}}}}
}
```

Example input: `{"evidence_id":"ev:<version-id>:<unit-id>","context_chars":500}`. Output excerpt: `{"ok":true,"evidence":{...},"context_before":"...","context_after":"...","provenance":{"content_sha256":"<64 hex characters>","parser_version":"pdf-v1","chunker_version":"page-v1","embedding_model":"BAAI/bge-m3@<revision>","indexed_at":"2026-10-04T10:00:00Z"}}`. The `evidence` object follows the shared schema. Errors: `INVALID_ARGUMENT`, `NOT_FOUND`, `STALE_EVIDENCE`.

### `check_coverage` → `VerityService.check_coverage`

Purpose: inspect actual workspace code and tests against one or more structured requirements.

```json
{
  "input": {"type":"object","additionalProperties":false,"required":["requirement_keys"],"properties":{"requirement_keys":{"type":"array","minItems":1,"maxItems":50,"uniqueItems":true,"items":{"type":"string"}},"workspace_id":{"type":"string","minLength":1},"run_tests":{"type":"boolean","default":false}}},
  "success": {"type":"object","additionalProperties":false,"required":["ok","workspace_id","workspace_revision","inspected_at","results","limitations"],"properties":{"ok":{"const":true},"workspace_id":{"type":"string"},"workspace_revision":{"type":"string"},"inspected_at":{"type":"string","format":"date-time"},"results":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["requirement_key","status","implementation","tests","reason","confidence"],"properties":{"requirement_key":{"type":"string"},"status":{"type":"string","enum":["IMPLEMENTED","PARTIAL","MISSING","UNCERTAIN"]},"implementation":{"type":"array","items":{"$ref":"#/$defs/CodeLocation"}},"tests":{"type":"array","items":{"$ref":"#/$defs/CodeLocation"}},"reason":{"type":"string"},"confidence":{"type":"string","enum":["high","medium","low"]}}}},"limitations":{"type":"array","items":{"type":"string"}}}}
}
```

Example input: `{"requirement_keys":["payments-api@1.0#REQ-003"],"workspace_id":"demo","run_tests":false}`. Output excerpt: `{"ok":true,"workspace_id":"demo","workspace_revision":"<source-tree-hash>","inspected_at":"2026-10-04T10:00:00Z","results":[{"requirement_key":"payments-api@1.0#REQ-003","status":"PARTIAL","implementation":[{"path":"refund.py","start_line":42,"end_line":47,"excerpt":"...","basis":"static_check"}],"tests":[{"path":"tests/test_refund.py","start_line":87,"end_line":102,"excerpt":"...","basis":"text_match"}],"reason":"Duplicate branch found; rejection assertion unverified","confidence":"medium"}],"limitations":["Tests were not executed"]}`. `run_tests:true` requires a preconfigured allowlisted test command and timeout; arbitrary commands from MCP input are forbidden. Errors: `NOT_FOUND`, `WORKSPACE_DENIED`, `TIMEOUT`, `INVALID_ARGUMENT`.

### `compare_sources` (should have) → `VerityService.compare_sources`

Purpose: retrieve source-grouped evidence for comparison. VERITY does not assert agreement automatically in the MVP.

```json
{
  "input": {"type":"object","additionalProperties":false,"required":["query","document_ids"],"properties":{"query":{"type":"string","minLength":2,"maxLength":2000},"document_ids":{"type":"array","minItems":2,"maxItems":10,"uniqueItems":true,"items":{"type":"string","format":"uuid"}},"per_document_limit":{"type":"integer","minimum":1,"maximum":5,"default":2}}},
  "success": {"type":"object","additionalProperties":false,"required":["ok","query","groups","assessment"],"properties":{"ok":{"const":true},"query":{"type":"string"},"groups":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["document_id","items"],"properties":{"document_id":{"type":"string","format":"uuid"},"items":{"type":"array","items":{"$ref":"#/$defs/Evidence"}}}}},"assessment":{"const":"unassessed"}}}
}
```

Example input: `{"query":"duplicate refund requests","document_ids":["<api-uuid>","<security-uuid>"]}`. Output excerpt: `{"ok":true,"query":"duplicate refund requests","groups":[{"document_id":"<api-uuid>","items":[{...}]},{"document_id":"<security-uuid>","items":[{...}]}],"assessment":"unassessed"}`. Each item follows the shared `Evidence` schema. Errors: `INVALID_ARGUMENT`, `NOT_FOUND`, `TIMEOUT`. A later evaluator could add evidence-backed `agrees`, `conflicts`, `qualifies` relationships with explicit cited pairs and an `UNCERTAIN` option.

## Phase 7 — Cline SDK and native UI

External Cline integration: start VERITY MCP over stdio from an external Cline client, register it in that client's MCP configuration, ask Cline to search before coding, and have Cline cite evidence IDs/requirement keys in its final report. Include a short project rule telling Cline to invoke `search_evidence` and `get_requirement` before changes, then `check_coverage` after changes; a rule is a workflow aid, not proof of compliance. The four frozen tools are in `09_VERITY_MCP_CONTRACT.md`.

Native VERITY chat integration: a small Node 22 service creates a Cline SDK `Agent` with explicit `providerId`, `modelId`, provider credentials/local endpoint as supported by the installed package, a system prompt, and `createTool()` wrappers around the canonical VERITY capability boundary. The native UI calls the frozen `/api/v1/chat/*` routes; Vandit's HTTP adapter delegates to Atharv's SDK gateway. SDK tools reach `VerityService` through the verified local service/HTTP adapter and use the same models as MCP. The SDK agent owns reasoning and answer generation; VERITY owns retrieval, Evidence, provenance, requirements and coverage. There is no separate SDK retrieval or citation implementation. Existing SDK examples show `new Agent({providerId, modelId, systemPrompt, tools})`, `createTool({name, description, inputSchema, execute})`, `agent.run()`, `agent.continue()`, and `agent.subscribe()`; see [SDK README](https://github.com/cline/cline/blob/main/sdk/README.md) and [Agent reference](https://github.com/cline/cline/blob/main/.agents/skills/cline-sdk/references/agent/REFERENCE.md). The reference says `subscribe` events include `assistant-text-delta` and result text is `outputText`, while the top-level README has older-looking `onEvent`/`result.text` examples. Pin one installed SDK version and verify its types with a smoke test before coding this path. The exact Node–Python connection is implementation discovery behind the frozen tool/API shapes.

Tool schemas match the frozen four-tool surface; each wrapper validates input and returns a structured success/failure object. SDK errors become structured tool results where possible. The agent prompt instructs it to retrieve first, cite only evidence IDs it received, say when evidence is missing, distinguish source text from inference, and let VERITY coverage inspect code rather than trusting its own claim. A backend session map keeps one agent instance per UI conversation for `continue()`; a restart either restores a verified SDK snapshot format or starts a new session explicitly. The frozen v1 chat response is a final answer with resolved `Evidence[]`; streaming may remain internal until separately contracted. The UI renders that SDK response, citation cards, document list and coverage report. In the eight-hour sprint, the external Cline MCP demo can be completed before SDK chat; if SDK is unavailable, chat reports `SDK_UNAVAILABLE` rather than switching to an independent native agent.

## Phase 8 — Coverage verification

`check_coverage` evaluates a workspace snapshot, not a user-maintained status field. Configuration maps a `workspace_id` to a trusted canonical root. Resolve every candidate path and reject traversal, symlink escapes, ignored/vendor directories, generated binaries and files over size limits. Read code and tests separately. First retrieve likely files with FTS/`rg` over filenames, symbols, requirement IDs, API names and keywords. Then inspect bounded line excerpts and, for supported languages, optional AST symbols or static checks. Map acceptance criteria to their parent requirements. An evaluator receives the exact requirement, linked criteria, code excerpts and test excerpts. In the MVP, deterministic signals plus explicit checks for the demo domain are safer than treating an LLM verdict as fact; if an LLM evaluator is used, its conclusion remains `UNCERTAIN` without inspectable supporting spans.

Status rules: `IMPLEMENTED` requires directly relevant implementation evidence and evidence that each essential acceptance criterion is tested or statically provable; `PARTIAL` means relevant code exists but a clause or test is unsupported; `MISSING` requires a completed scan with no credible implementation match; `UNCERTAIN` covers ambiguous logic, incomplete scans, unsupported language, failed test execution or stale workspace state. Test presence and test execution are separate fields in the internal report. A passing test does not by itself prove the full requirement; a code comment containing `REQ-003` does not count as implementation. Report file paths and exact line ranges for both implementation and tests, scan timestamp, workspace revision/hash, reasons and limits. If code changes during scanning, mark the run stale and rerun. The report remains reproducible against the same source revision.

## Phase 9 — Proposed repository structure

```text
VARITY/
  Docs/
    ARCHITECTURE.md
    pptx/
  pyproject.toml
  verity/
    models.py              # document, requirement, unit, evidence, coverage types
    config.py              # paths, model revisions, limits, workspace allowlist
    service.py             # transport-independent application API
    ingestion/
      spec.py              # schema validator and deterministic requirement parser
      parsers.py           # PDF/MD/TXT/code parser protocol and dispatch
      chunking.py          # drafts, spans and materialization
      pipeline.py          # hash, version, parse, index transaction
    storage/
      sqlite.py            # canonical rows, FTS5 and embedding records
      migrations/          # schema versions
    retrieval/
      dense.py             # local BGE-M3 embed/query and bounded vector scan
      lexical.py           # safe FTS5 query
      fusion.py            # RRF and ties
      rerank.py            # optional cross encoder
      evidence.py          # result builder and resolver
    coverage/
      workspace.py         # root safety and snapshot
      candidates.py        # code/test search
      evaluator.py         # evidence-backed status rules
    mcp/
      server.py            # stdio registration and structured replies
      schemas.py           # Phase 6 contract schemas
    cli.py                 # ingest/search/serve/demo commands
  sdk-ui/                  # Cline SDK gateway and native VERITY UI; chat sequenced after core baseline
  tests/
    fixtures/              # small spec, PDF, general docs, codebase
    test_ingestion.py
    test_retrieval.py
    test_mcp_contracts.py
    test_coverage.py
    test_demo.py
  data/                    # ignored runtime originals and SQLite DB
```

Public interfaces: `ParsedDocument`, `Requirement`, `RetrievalUnit`, `Evidence`, `CoverageResult` in `models.py`; `VerityService` in `service.py`; `Parser`/`Chunker` protocols in ingestion; `KnowledgeStore` and `EmbeddingProvider` protocols at their call sites. `mcp` depends on `service`, never directly on storage. `coverage` reads requirements through the service/store and a separately configured workspace. `sdk-ui` sees the service contract, not SQLite. One Python package and one SQLite database keep integration small.

## Phase 10 — Team plan and interface handoff

| Owner | Work and deliverable | Contract to freeze at hour 1 |
|---|---|---|
| Atharv | Domain models, `VerityService`, schema/migrations and Cline SDK gateway for native chat; schedule SDK wiring after the core/MCP baseline. | Typed service signatures and shared JSON schemas; sample evidence fixture. |
| Piyush | Spec/general parsers, chunking, ingestion pipeline, dense/FTS retrieval, RRF. | `ParsedDocument -> RetrievalUnit[]`; `search(query, filters, limit) -> Evidence[]` with stable IDs. |
| Vandit | MCP stdio server for external Cline, HTTP chat routing to SDK gateway, tool/route contract tests and external-client workflow rule. | Frozen `09`/`11` input/output schemas; no business logic in handlers. |
| Vanashree | Workspace scan, requirement/code/test mapping, coverage evaluator, demo report and native UI presentation of SDK chat responses. | `check_coverage(keys, workspace_id, run_tests) -> CoverageReport`; source location format and frozen chat response. |

At hour 1, all four validate one shared fixture with `REQ-001`, a PDF passage, one code file and one test. Atharv supplies stubs/interfaces immediately so others can work in parallel. Integration merges follow interface contracts; any change to IDs or JSON shapes requires all owners to update the fixture together.

## Phase 11 — Eight-hour execution plan

| Time | Parallel work | Exit checkpoint |
|---|---|---|
| 0–1 h | Freeze schema, contracts, repo skeleton and fixture; preflight offline models, Python/MCP and external Cline connection. | All owners can import models; external Cline can start a minimal stdio tool. |
| 1–2 h | Piyush builds spec/MD/TXT parser and FTS; Atharv storage/service; Vandit tool adapter; Vanashree workspace scanner. | Ingest one spec and retrieve `REQ-001` lexically. |
| 2–3 h | PDF/page ingestion, embeddings and vector table; coverage candidate search; MCP contracts. | PDF plus spec searchable, with resolvable locators. |
| 3–4 h | RRF and rerank; coverage evidence/rules; Cline project workflow. | Three-document query and real coverage report from fixture. |
| 4–5 h | End-to-end integration and failure fixes. | External Cline retrieves evidence through MCP, edits demo code and invokes coverage. |
| 5–6 h | Citation validation, tests, lexical fallback and offline smoke test. | Clean-start demo works without network. |
| 6–7 h | Run paired with/without tasks and record rubric, timings/tokens when available; prepare short report/UI. | Results table contains only measured data and source examples. |
| 7–8 h | Rehearse live demo and reset fixture; implement native SDK chat/UI if core is stable. | External MCP slice repeated from a clean state; native chat is either SDK-powered or reports unavailable. |

**Eight-hour backend/MCP baseline:** one structured spec, PDF/MD/TXT general ingestion, multi-document hybrid retrieval with truthful fallback, citations, four MCP tools, actual workspace coverage and an external Cline demo. **Later in sprint if time allows:** BGE reranker, code parser, native VERITY chat UI powered by Cline SDK, compact report UI and paired evaluation. **Further scope:** rich UI polish, OCR, AST checks across languages, graph reasoning and persistent conversation history. The final deck's `compare_sources` suggestion is superseded by frozen `09`, which has exactly four MCP tools. If model loading consumes the schedule, keep FTS5 and mark semantic/rerank unavailable rather than presenting lexical results as hybrid. Native chat must not be presented as complete until the SDK gateway and UI actually work.

## Phase 12 — Risks and fallback plans

| Risk | Mitigation/fallback |
|---|---|
| Offline model missing, incompatible or slow | Verify model cache before event; cap candidates/batches. Continue with lexical retrieval and explicit `lexical_only` metadata. |
| PDF text extraction loses layout or page | Cite only extracted page when certain; mark page null/partial otherwise. No OCR claim. |
| Requirement schema too flexible | Keep strict Markdown v1; reject malformed IDs and references with line-numbered errors. |
| Coverage false positives | Require code/test excerpts; default ambiguous cases to `UNCERTAIN`; show reasons. |
| Cline ignores workflow rule | Demo prompt asks for tool calls and final citations; MCP calls and coverage report are observed, not assumed. |
| SDK API/version drift | Keep native SDK chat behind its frozen gateway; pin version and type-check against official reference. Return `SDK_UNAVAILABLE` if it cannot run. |
| Multiple owners change contracts | Freeze schema/fixture at hour 1 and run contract tests at integration checkpoints. |
| Scope expansion | Defer UI polish, graph, OCR and extra file types until the external Cline MCP slice is repeatable. |
| Local path/privacy leakage | Bind loopback/stdio, validate workspace roots, cap file reads and redact absolute paths in shareable reports. |
| Mnemo proprietary material | Independently implement documented patterns; do not copy code or redistribute its files without permission. |

## Phase 13 — Authoritative implementation specification

The preceding phases define the build contract. The acceptance criteria below make it executable:

1. A fresh run ingests a valid v1 spec and three ordinary documents, persists exact source bytes/hash, and retrieves them after process restart. Invalid IDs and references fail with precise errors.
2. A query spanning the spec, architecture document and security document returns one unified ranked evidence set with correct source identities and at least one resolvable citation from each relevant source. Lexical, dense, RRF and rerank use the configured model/limits; unavailable components are reported.
3. `get_requirement` returns only explicit spec entities. `get_evidence` resolves its original version and quote, including page or line/section when present. No synthetic page numbers appear.
4. An external Cline client calls VERITY's stdio MCP tools, uses returned evidence in a coding task, and presents requirement keys/citations. MCP responses validate against frozen `09`/`21` schemas. When native VERITY chat is implemented, its agent execution is through Cline SDK and its tools use the same canonical service/Evidence boundary.
5. `check_coverage` scans the configured workspace after code changes, reports code and test line evidence separately, and returns `UNCERTAIN` where support is insufficient. It never marks a requirement complete because an agent claimed it.
6. Unit/contract tests cover parser spans, IDs, FTS query escaping, RRF ordering, citation resolution, MCP serialization, workspace path bounds and coverage status rules. One end-to-end test covers the vertical slice.
7. The demo includes a coding/spec case and a general cross-document question. Any with/without comparison names its fixed task set and measured rubric; illustrative deck numbers are never reported as observed.

The eight-hour implementation sequence is: freeze contracts → ingest and persist → hybrid retrieve → resolve Evidence → expose MCP → inspect coverage → run external Cline demo → evaluate → implement native Cline SDK chat/UI if time remains. The two integration modes converge on `VerityService`; neither owns a separate retrieval or Evidence path. Frozen contracts remain authoritative for actual interfaces and acceptance gates.
