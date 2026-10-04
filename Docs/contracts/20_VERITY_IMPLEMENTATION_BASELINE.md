# VERITY pre-implementation freeze

**Status:** FROZEN FOR INITIAL IMPLEMENTATION, 2026-10-04; documentation patch 1.0.1 for the native SDK UI architecture. **Owners/consumers:** `19`. This document is the concise handoff; detailed authority remains in `01`–`19` and the machine-readable schema companion. No VERITY application code was created in this pass.

| Freeze area | Decision |
|---|---|
| Versions | Contract documentation patch `1.0.1`; schema/spec/metadata/MCP/SDK tool/config wire versions `1.0.0`; HTTP `/api/v1`; SQLite `user_version=1`. |
| IDs | UUIDv4 source/document/version/session/coverage/request; deterministic SHA-256 block/chunk/requirement/evidence prefixes; local `REQ-*` only within spec. |
| Models | One `Document`, `Requirement`, `Chunk`, `Evidence`, `Citation`, `Provenance`, `SearchResult`, `CoverageResult`, `Error` family in `03`. `page: integer≥1|null` throughout. |
| Search | One `SearchRequest`; multi-document selection via `document_ids`; bounded hybrid FTS5+BGE-M3, RRF 60, optional reranker; no v1 search pagination. |
| MCP/SDK | Same four tool names and canonical input/output. Cline SDK powers the native VERITY chat agent; MCP exposes VERITY to external Cline clients. Both invoke the same `VerityService`; neither owns retrieval or Evidence logic. |
| HTTP | `/api/v1` routes in `11`; native UI calls REST. Chat routes delegate to the SDK gateway, or return `SDK_UNAVAILABLE` when it is not running. |
| DB | Tables/FTS/vector BLOB and migration 1 in `13`; only storage owns SQL. |
| Coverage | Real workspace snapshot, code/test evidence separately, four statuses; no manually editable status. |
| Errors/config | One code list in `17`, one `verity.toml` and env registry in `14`. |
| Modules/public functions | `15` and `16`; ownership in `19`. |

## Contradictions resolved from `ARCHITECTURE.md`

1. The earlier plan used a human `source_id@spec_version#REQ-003` key and also UUID source/document IDs. V1 uses opaque stable `requirement_id=req_<hash(source UUID, local REQ ID)>`; `source_key` and `spec_version` are metadata.
2. It called retrieval units “chunks” and also used a separate requirement object; v1 has one `Chunk` for retrieval and one `Requirement` for normative structure, linked by IDs. API and acceptance entities are separate spec entities.
3. It suggested `search_multi_document`, `search_knowledge`, `compare_sources` and `trace_provenance` as possible tools. V1 has four tools; multi-document filters live in `search_evidence`, provenance in `get_evidence`, comparison is performed by Cline over cited evidence.
4. It proposed the same evidence object but did not freeze citation marker or direct lookup score. V1 freezes `[[ev_<64hex>]]`, one label formatter and `score=null` on direct lookup.
5. It left UI/SDK transport ambiguous. V1 native UI calls REST; its chat routes delegate to the Cline SDK agent. Node SDK tools may use loopback REST to the Python service, with no second retrieval implementation. When the SDK is unavailable, chat returns a truthful unavailable error rather than switching to another native agent.
6. The presentation calls for BGE reranking as must-have while the earlier plan made it optional. V1 contract exposes actual `reranker_used`; the team should provision the model before the offline sprint, but fallback is explicit rather than a false hybrid claim.
7. The request path says `Desktop/Verity/docs`; the existing project is `Desktop/VARITY/Docs`. Contracts live in the existing project. Product/package spelling is VERITY/`verity`.

## Intentionally flexible or deferred

Chunk size/overlap, vector scan optimization, cache and internal class structure remain flexible behind the frozen interfaces. **DEFERRED — IMPLEMENTATION DISCOVERY:** exact installed Cline SDK package version/event types and the Node–Python loopback process lifecycle; the official docs show version drift, and no SDK dependency is installed in this empty VERITY checkout. This does not permit changing tool schemas or UI chat response. The exact local BGE model revision path must be filled in `verity.toml` after inspecting offline assets; model ID is config, not a schema change. If a local model cannot run, the documented fallback is lexical-only with omission metadata. These are operational discoveries, not open field/ID decisions.

Items that must not change casually: ID hashing inputs, source/document/version semantics, nullable page rule, Evidence/Citation shape, `Requirement` structure, tool names, endpoint paths, error/status codes, database tables, public signatures and config env names. Use `02` change control for any such edit.

## Start order

At hour 0, Atharv creates shared model/ID/error/config types and `VerityService` stubs from `03`/`16`; all four validate the same golden fixture. Piyush then implements ingestion and retrieval behind those interfaces. Vandit implements MCP/API adapters against the same canonical schemas in parallel. Vanashree implements coverage scanning/evaluation and UI display against `CoverageResult`. Atharv wires storage/evidence, then implements the Cline SDK gateway for the native VERITY chat UI after the backend/MCP baseline is stable. That sprint ordering protects the core evidence pipeline; it does not change which agent runtime powers native chat. External Cline integration remains the MCP path. Merge at the roadmap PR gates and run `18` contract tests.
