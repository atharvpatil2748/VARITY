# Versioning and change control

**Owner:** Atharv. **Consumers:** all four owners. **Documentation revision:** 1.0.2; public wire contract versions remain 1.0.0.

All public/persisted contracts use semantic `MAJOR.MINOR.PATCH`. The initial package, model, metadata, spec format, MCP and config wire versions are `1.0.0`; package documentation has a non-wire patch revision `1.0.1`. HTTP uses `/api/v1` plus response field `contract_version: "1.0.0"`. SQLite uses integer `user_version=1` because SQLite migrations are sequential; migration 1 implements data schema 1.0.0. Every persisted canonical record has `schema_version: "1.0.0"` (explicit column for primary records, or inherited from a parent with an explicit version for derived rows). Every metadata JSON has `metadata_version: "1.0.0"`.

Major: removing/renaming a field, changing its meaning/type/nullability, changing ID or citation syntax, changing error/status semantics, changing an endpoint/tool or persisted interpretation. Minor: additive optional field, new enum value only if consumers explicitly tolerate unknown values, new endpoint/tool, or optional capability. Patch: clarification or bug fix preserving wire format and meaning. Pre-1.0 policy does not apply because this freeze starts at 1.0.0; speed does not justify silent breaking changes.

Readers accept the same major and known minor. Writers emit their configured exact minor. Unknown major is `VERSION_UNSUPPORTED`. Unknown optional fields may be ignored only at transport input where `additionalProperties` is explicitly allowed; v1 request schemas set `additionalProperties: false`, so new inputs require minor version and a deployed reader. Persisted records from newer minor versions are read only when the implementation knows those fields. No in-place reinterpretation of historical evidence. Database migrations are forward-only, transactional, numbered SQL files; take a backup before migration and refuse a database with a greater `user_version`. No automatic downgrade. A new document version is created on content change; old versions and citations remain resolvable until explicit retention cleanup. A retention cleanup must report `EVIDENCE_GONE` for old references.

## Lightweight change process

1. Proposer names the owner document and consumers from `19`.
2. Owner classifies breaking/additive/editorial impact.
3. Update the owner contract and linked references, then bump the relevant version.
4. Update shared contract fixtures/tests.
5. Notify all affected owners in the team channel and record the decision in this file's change log.
6. Implement adapters/consumers before changing the producer output when possible.
7. Merge only after the contract tests pass for producer and consumers.

For the eight-hour sprint, one short team acknowledgement is enough. Private implementation changes need no process. The roadmap [dependency matrix](../roadmaps/06_VERITY_CONTRACT_DEPENDENCY_MATRIX.md) records D1–D3 as unresolved implementation boundary blockers; their affected PRs wait for approved amendments. Implementation discovery items are called out in `20` and must stay behind these interfaces.

## Change log

| Date | Version | Decision |
|---|---|---|
| 2026-10-04 | 1.0.0 | Initial pre-implementation freeze; supersedes proposed interface details in `ARCHITECTURE.md`. |
| 2026-10-04 | 1.0.1 documentation patch | User-directed clarification: Cline SDK runs the native VERITY chat agent; MCP serves external Cline clients. Updated `10` and linked planning/architecture prose. SDK/MCP tools, HTTP routes, canonical objects and schema version stay 1.0.0. Atharv owns the amendment; Vandit and Vanashree are affected consumers and must review before implementation. |
| 2026-10-04 | 1.0.2 documentation patch | **D1 resolved (issue #2).** Editorial: aligned `06`'s `RetrievalService.search` return type to `RetrievalRun` per `16` (owner document for callable signatures) and `03`'s required `SearchResult` retrieval mode/omissions provenance. Search semantics, budgets, RRF, filters and wire schemas unchanged; no `21` change. Classification: editorial/patch. Proposed by Piyush (issue #2, roadmap 06 D1 row); approved by Atharv (contract package owner) as team acknowledgement for the sprint; Vandit and Vanashree notified as fixture consumers. Affected owners pull once: Piyush (P9/PR-P3 unblocked), Atharv (A6/PR-A3 retrieval seam unblocked; D3 still gates historical origin). |
