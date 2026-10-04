# VERITY v1 engineering contract index

**These documents are the authoritative engineering contracts for VERITY v1.** They supersede interface suggestions in [ARCHITECTURE.md](../ARCHITECTURE.md); that file remains the rationale and source audit. Status: **FROZEN FOR INITIAL IMPLEMENTATION**. Last updated: **2026-10-04** (Asia/Kolkata). Contract-package patch 1.0.1 records the finalized native SDK UI versus external MCP architecture; all wire schemas remain 1.0.0.

| Contract | Version |
|---|---|
| Contract package documentation | 1.0.1 |
| Public schemas and canonical wire objects | 1.0.0 |
| Spec document format | 1.0.0 |
| Metadata envelope | 1.0.0 |
| HTTP API | v1 (contract 1.0.0) |
| MCP tool surface | 1.0.0 |
| Cline SDK tool surface | 1.0.0 |
| Cline SDK architecture document (`10`) | 1.0.1; no tool/wire change |
| SQLite database | `PRAGMA user_version = 1` |
| Configuration | 1.0.0 |

The real checkout is `C:/Users/athar/Desktop/VARITY/Docs`, although the brief says `Desktop/Verity/docs`. The product and Python package spelling is **VERITY/`verity`**; do not create a second `Desktop/Verity` tree. All paths here are relative to `VARITY/Docs/contracts` unless stated otherwise.

## Reading order and authority

| File | Contract |
|---|---|
| [02_VERITY_VERSIONING_POLICY.md](02_VERITY_VERSIONING_POLICY.md) | Versions, compatibility and change control |
| [03_VERITY_DATA_SCHEMAS.md](03_VERITY_DATA_SCHEMAS.md) | Sole authority for fields, types, IDs and enums |
| [04_VERITY_SPEC_SCHEMA.md](04_VERITY_SPEC_SCHEMA.md) | Strict Markdown spec format and mapping |
| [05_VERITY_DOCUMENT_INGESTION_CONTRACT.md](05_VERITY_DOCUMENT_INGESTION_CONTRACT.md) | Parser, normalized blocks and chunker |
| [06_VERITY_RETRIEVAL_CONTRACT.md](06_VERITY_RETRIEVAL_CONTRACT.md) | Search public boundary and ranking behavior |
| [07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md](07_VERITY_EVIDENCE_PROVENANCE_CONTRACT.md) | Citation and resolution |
| [08_VERITY_MULTI_DOCUMENT_QUERY_CONTRACT.md](08_VERITY_MULTI_DOCUMENT_QUERY_CONTRACT.md) | Multi-source search semantics |
| [09_VERITY_MCP_CONTRACT.md](09_VERITY_MCP_CONTRACT.md) | MCP tools and serialization |
| [10_VERITY_CLINE_SDK_CONTRACT.md](10_VERITY_CLINE_SDK_CONTRACT.md) | SDK adapter and grounding |
| [11_VERITY_API_V1_CONTRACT.md](11_VERITY_API_V1_CONTRACT.md) | UI-facing HTTP API |
| [12_VERITY_COVERAGE_CONTRACT.md](12_VERITY_COVERAGE_CONTRACT.md) | Workspace inspection and statuses |
| [13_VERITY_DATABASE_SCHEMA.md](13_VERITY_DATABASE_SCHEMA.md) | SQLite DDL contract and migration |
| [14_VERITY_CONFIGURATION_CONTRACT.md](14_VERITY_CONFIGURATION_CONTRACT.md) | Config fields and environment names |
| [15_VERITY_MODULE_BOUNDARIES.md](15_VERITY_MODULE_BOUNDARIES.md) | Dependency rules and single ownership |
| [16_VERITY_PUBLIC_INTERFACES.md](16_VERITY_PUBLIC_INTERFACES.md) | Cross-module Python signatures |
| [17_VERITY_ERROR_CONTRACT.md](17_VERITY_ERROR_CONTRACT.md) | Errors and transport mapping |
| [18_VERITY_CONTRACT_TEST_PLAN.md](18_VERITY_CONTRACT_TEST_PLAN.md) | Shared fixtures and gates |
| [19_VERITY_TEAM_OWNERSHIP.md](19_VERITY_TEAM_OWNERSHIP.md) | File ownership and Git workflow |
| [20_VERITY_IMPLEMENTATION_BASELINE.md](20_VERITY_IMPLEMENTATION_BASELINE.md) | Freeze report and build order |
| [21_VERITY_V1_JSON_SCHEMAS.json](21_VERITY_V1_JSON_SCHEMAS.json) | Machine-readable canonical wire schemas referenced by tools/API/tests |

`03` owns model shape; other documents reference those models without inventing a transport-specific Evidence type. `16` owns callable signatures. `13` owns physical storage. If prose conflicts, the owner document wins and the inconsistency must be corrected before implementation.

The original Round 1 PPTX is a historical pitch. Its Cline-path wording is reconciled in the [PPT/demo addendum](../pptx/VERITY_CLINE_INTEGRATION_DEMO_ADDENDUM.md). Contract `10` defines native Cline SDK chat; contract `09` defines MCP access for external Cline clients. This documentation patch changes neither wire surface.

## Change boundary

Developers may change private helpers, class internals, chunking heuristics within provenance guarantees, vector scan optimization, cache layout, UI presentation and log wording without team agreement. Field names/types, IDs, enums, tool names, endpoint paths, status semantics, public signatures, config names/defaults, database DDL and citation syntax require a contract change. A breaking change requires a major version or new API path/tool name; additive optional fields require a minor version; editorial clarification and internal fixes use patch. See `02` for the seven-step change process.

No application source was created by this freeze. Each document has a named owner and consumers in `19`; “frozen” means implement against these boundaries, not that future changes are forbidden.
