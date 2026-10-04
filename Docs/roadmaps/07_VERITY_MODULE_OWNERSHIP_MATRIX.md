# Module and file ownership matrix

Paths are proposed implementation paths under `C:/Users/athar/Desktop/VARITY/` from frozen `15`, `16`, and `19`. No application files exist yet. A backup is a reviewer/emergency maintainer, **not** an additional concurrent editor. `Public` refers to the named frozen interface. Other developers consume it through imports or fixtures; they do not edit the owned module.

| Path / module | Owner; backup | Consumers and public boundary | Allowed edits / forbidden edits |
|---|---|---|---|
| `verity/models.py` | Atharv; Piyush | All; `03`/`21` canonical types | Implement validation/serialization. No transport DTOs or unilateral field changes. |
| `verity/ids.py` | Atharv; Piyush | Piyush, evidence; `16` ID functions | Implement `03` golden vectors. No new competing ID rules. |
| `verity/errors.py` | Atharv; Vandit | All; `VerityError`/`17` | Internal exception mapping. No new public codes. |
| `verity/config.py`, `verity.toml` template | Atharv; Vandit | All; frozen `VerityConfig` | Parse `14`; no module-local env reads or extra names. |
| `verity/storage/*`, `verity/storage/migrations/0001_initial.sql` | Atharv; Piyush | Ingestion/retrieval/coverage through `KnowledgeStore` | SQL, originals, FTS/vector rows, report persistence. Other modules never issue SQL. |
| `verity/evidence.py` | Atharv; Piyush | Service/adapters/UI; `EvidenceService` | Canonical Evidence/citation assembly. No adapter-specific shapes. |
| `verity/service.py` | Atharv; Vandit | MCP/HTTP/SDK; `VerityService` | Composition and delegation. No SQL or duplicate ranking/coverage logic. |
| `verity/ingestion/*` (likely `spec.py`, `parsers.py`, `chunking.py`, `pipeline.py`) | Piyush; Atharv | Service/store; `Parser`, `Chunker`, `IngestionCoordinator` | Parse/materialize/coordinate. No SQL schema changes. Exact internal filenames may vary within this owned directory. |
| `verity/retrieval/*` (likely `dense.py`, `lexical.py`, `fusion.py`, `rerank.py`) | Piyush; Atharv | Evidence/service; `EmbeddingProvider`, `Reranker`, `RetrievalService` | Ranking internals and model adapters. No citation formatter or direct SQL. |
| `verity/coverage/*` (likely `workspace.py`, `candidates.py`, `evaluator.py`) | Vanashree; Atharv | Service/MCP/API; `WorkspaceScanner`, `CodeEvidenceRetriever`, `RequirementEvaluator`, `CoverageService` | Scan/evaluate/report. No code mutation or SQL. D2 needs approved boundary before retriever wiring. |
| `verity/mcp/*` (likely `server.py`, `tools.py`) | Vandit; Atharv | External Cline clients; four `09` tools | Registration/validation/serialization only. No core business logic. |
| `verity/http/*` (likely `app.py`, `routes.py`) | Vandit; Atharv | Native UI/SDK gateway; `11` routes | HTTP validation/multipart/status mapping and chat delegation to SDK gateway. No SQL/ranking/coverage or chat reasoning. |
| `sdk-ui/gateway/*` | Atharv; Vandit | Native UI; four SDK tools, Cline agent and chat gateway | Pinned Cline SDK agent/session lifecycle and same canonical schemas. No independent retrieval or evidence store. |
| `sdk-ui/frontend/*` | Vanashree; Atharv | User; `11` REST | Document/search/evidence/coverage and SDK-agent chat presentation. No SQLite, MCP calls, private Python imports or independent agent. |

## Shared-file hotspot rules

| File or directory | Class | Owner / when edited | Contribution and merge method |
|---|---|---|---|
| `Docs/contracts/*` | **B — shared but frozen** | Contract owner only after `02` approval | Raise issue; do not edit in feature branches. |
| `Docs/roadmaps/*` | **B — shared plan** | Planning owner before sprint; controlled corrections after | Roadmap edits separate from code merges. |
| `verity/models.py`, `ids.py`, `errors.py`, `config.py` | **A — single owner** | Atharv in foundation merge | Others submit failing fixture/issue to Atharv, not competing edits. |
| `verity/service.py` | **E — integration only** | Atharv at each checkpoint | Module owners provide constructors and tests; Atharv wires them. |
| `verity/storage/migrations/*` | **A — single owner** | Atharv before store tests | No independent migration from other branches. |
| `verity/__init__.py`, package exports | **C — controlled edits** | Atharv at integration | Owners import explicit modules while developing; Atharv updates exports once. Each owned subpackage's `__init__.py` belongs to that owner. |
| `pyproject.toml`, lockfile, `package.json`/lockfile | **E — integration only** | Atharv after dependency proposals | Owners send exact dependency/version requests; one integrator edits/locks. Frontend-specific package file under `sdk-ui/frontend` is Vanashree-owned if it does not alter shared root tooling. |
| `verity/mcp/server.py` registration | **A — single owner** | Vandit | Other owners provide fake service/fixtures; no direct registration edits. |
| `verity/http/*` routing registry | **A — single owner** | Vandit | UI/SDK request changes go through frozen `11`; no route edits by consumers. |
| `tests/fixtures/contracts_v1/golden_ids.json`, `golden_wire.json` | **B — shared but frozen values** | Atharv creates; Vandit verifies schema harness | Other owners add separate focused fixture files, not rewrite golden IDs. |
| `tests/fixtures/contracts_v1/*` other fixtures | **C — controlled edits** | One named fixture owner per file in `09` | Add new named fixtures, avoid simultaneous edits to the same file. |
| `tests/test_*` or owner-specific test directories | **A — single owner per domain** | Same as module owner | Integration tests under `tests/integration/` are **E**, owned by Atharv with contributions as separate test files. |
| Generated model caches, SQLite DB, coverage reports | **D — generated** | No Git owner; ignored | Never merge generated artifacts. |

The frozen ownership baseline is preserved. Piyush owns **lexical indexing semantics** and retrieval behavior; Atharv owns the **physical FTS table, triggers and SQL**. This is a shared boundary with Atharv as persistence owner and Piyush as search consumer, not an ownership reassignment. Vanashree owns coverage computation; Atharv owns `coverage_runs` persistence and the `VerityService` call. Native UI consumes Vandit's REST adapter; its chat response comes from Atharv's Cline SDK agent. External Cline uses Vandit's MCP adapter. Both adapters reach the same `VerityService`.

## Operational task, contract, PR and review ownership

The frozen contracts are team-owned through the change process in `02_VERITY_VERSIONING_POLICY.md`; the implementation owners below own conformance and proposals, **not unilateral contract edits**. Atharv is the designated merge owner for `integration/verity-v1` after the named independent reviewer approves. PR IDs are planning labels; exact prerequisites and gates are in [08](08_VERITY_MERGE_AND_INTEGRATION_PLAN.md).

| Module / controlled path | Task owner and IDs | Frozen contract conformance owner | PR owner / PRs | Required reviewer | Merge authority |
|---|---|---|---|---|---|
| Core `models.py`, `ids.py`, `errors.py`, `config.py` | Atharv A0–A3 | Atharv for `03`, `14`, `17`, `21` implementation; team approves text changes | Atharv PR-A1 | Piyush; Vandit checks wire JSON | Atharv after approval |
| `storage/**`, migrations | Atharv A4–A5 | Atharv for `05`, `13`, `16` store side | Atharv PR-A2/PR-A3 | Piyush | Atharv after approval |
| `evidence.py`, `service.py` | Atharv A6–A7, A9 | Atharv for `07`, `16` composition side | Atharv PR-A3/PR-A4/PR-A6 | Piyush for A3; Vandit for A4/A6 | Atharv after approval |
| `sdk-ui/gateway/**` | Atharv A8 | Atharv for `10`; four-tool parity with `09` | Atharv PR-A5 optional | Vandit | Atharv after approval |
| `ingestion/**` | Piyush P0–P5 | Piyush for `04`, `05`, `16` parser/coordinator side | Piyush PR-P1/PR-P2 | Atharv | Atharv after approval |
| `retrieval/**` | Piyush P6–P10 | Piyush for `06`, `08`, `16` retrieval side | Piyush PR-P3/PR-P4 | Atharv | Atharv after approval |
| `mcp/**` | Vandit V0–V4, V9–V10 | Vandit for `09`, `17`, `21` external-client transport side | Vandit PR-V1/PR-V3/PR-V4 | Atharv | Atharv after approval |
| `http/**` | Vandit V5–V9 | Vandit for `11`, `17`, `21` transport side | Vandit PR-V2/PR-V3/PR-V5 optional | Vanashree for V2/V5; Atharv for V3 | Atharv after approval |
| `coverage/**` | Vanashree N0–N7 | Vanashree for `12`, `16`, `21` coverage side | Vanashree PR-N1/PR-N2 | Atharv | Atharv after approval |
| `sdk-ui/frontend/**` | Vanashree U1–U6 | Vanashree for `11`, `21` UI consumption | Vanashree PR-U1/PR-U2 | Vandit | Atharv after approval |
| Root dependencies, entry point, package exports, `tests/integration/**` | Atharv A9 and controlled merges | Team approval for any contract impact | Atharv PR-A6 | Vandit | Atharv after approval |

**Other-owner change request:** file an issue/request naming the exact requested edit, reason, affected frozen contract, consumer and urgency. The owner changes the file after agreeing at the next PR gate; the requesting developer supplies a fixture or failing test and does not cross-edit. A backup reviewer is not a second concurrent editor. Shared golden fixtures are frozen values; new owner-specific fixtures use separate filenames. Generated DBs, model caches and logs never enter a PR.
