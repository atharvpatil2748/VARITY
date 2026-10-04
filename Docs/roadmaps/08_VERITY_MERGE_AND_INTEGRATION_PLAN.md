# VERITY GitHub PR and integration plan

**Client architecture:** Cline SDK powers native VERITY chat UI through the frozen chat API and canonical SDK tools; MCP exposes the same `VerityService` to external Cline clients. The sprint may complete the backend/external MCP baseline before native chat. An unavailable SDK leaves native chat unavailable; it does not authorize another UI agent or retrieval path. This is documentation patch 1.0.1, with unchanged v1.0.0 wire contracts.

**Target branch:** `integration/verity-v1`. Branches: Atharv `feature/atharv-core-evidence-sdk`; Piyush `feature/piyush-ingestion-retrieval`; Vandit `feature/vandit-mcp-http`; Vanashree `feature/vanashree-coverage-ui`. Each owner creates their branch after C0. PR IDs below are planning labels; GitHub assigns actual numbers. All PRs target the integration branch. Atharv is designated merge owner and merges **after independent reviewer approval**, including his own PRs. If Atharv is unavailable, the team explicitly designates a substitute; no implied merge authority transfers.

**Repository prerequisite:** on 2026-10-04 this workspace contains `Docs/` only and is not a Git repository (`git status` reports no `.git`). The schedule is ready to execute, but branch creation, pushes and GitHub PRs require the team to initialize/connect the repository and create `integration/verity-v1` first. This documentation pass does not perform that setup or create application code. All four can begin C0 contract preparation immediately; they can begin their W1 fixture/interface tasks once that Git prerequisite is completed. D1–D3 do not block W1 mock work.

## Global gate and commit rule

Every PR: (1) only owned files or an explicitly approved integration file; (2) focused unit and frozen-contract tests green; (3) applicable `21_VERITY_V1_JSON_SCHEMAS.json` definitions validate success/error fixtures; (4) public signatures match `16_VERITY_PUBLIC_INTERFACES.md`; (5) no `Docs/contracts/**` changes; (6) named reviewer approval. Prefer one implementation commit plus one tests commit; one atomic commit is fine. Real-integration PRs additionally require merged upstream PRs and a clean-start test. After each merge, Atharv checks the common schema/ID fixture suite and the merged module suite. A producer defect is fixed on its owner branch, never hidden in an adapter.

## Exact PR sequence and merge ledger

Rows in the same **window** may be opened and reviewed in parallel; the listed prerequisites, not row position, control merge order. `N` denotes Vanashree coverage and `U` UI.

| Window / PR | Author; exact steps | Reviewer | Merge owner | Prerequisites and before-merge proof | Merge unblocks; work remaining parallel |
|---|---|---|---|---|---|
| W1 PR-A1 | Atharv A1–A3 | Piyush; Vandit verifies wire JSON | Atharv | Model/ID/config tests; golden vectors; schema round trip | Real canonical imports P1/P4/V3/N1; mock work continues already |
| W1 PR-P1 | Piyush P1–P4 | Atharv | Atharv | Spec/general parser, chunker, draft/ID fixture tests; can use fake IDs | P5 and A4 record compatibility; V/N fake work continues |
| W1 PR-V1 | Vandit V1–V4 against fake service | Atharv | Atharv | Four MCP tool names, validation, JSON text/structured parity, error tests | External-client MCP shell; V5–V7 continue independently |
| W1 PR-N1 | Vanashree N1, N2 safe metadata, N4 fake evaluator | Atharv | Atharv | Scanner safety and four-status fixture tests; no D2-dependent text handoff | A/V coverage fixture; N3/N5/N6 fake work continues |
| W1 PR-U1 | Vanashree U1–U4 against API mock | Vandit | Atharv | API schema/render/error tests; no direct MCP/SQLite | UI ready for real API; U6 mock continues |
| W2 PR-A2 | Atharv A4 | Piyush | Atharv | PR-A1 merged; migration, FTS, rollback, idempotence tests | P5 real write and N6 real report store; A5 continues |
| W2 PR-P2 | Piyush P5 | Atharv | Atharv | PR-P1 and PR-A2 merged; real ingestion/idempotence test | A7 ingestion delegate, V6 real upload |
| W2 PR-A3 | Atharv A5–A6 | Piyush | Atharv | PR-A2 merged; **D1/D3 approved**; real origins/history and Evidence built from frozen fake retrieval output | P6/P9 real candidates, V4/V7 canonical Evidence; P6–P8 fake work preexists |
| W3 PR-P3 | Piyush P6–P9 | Atharv | Atharv | PR-A3 merged; **D1 approved**; candidate/RRF/rerank/multi-doc and real-store tests | A7 real retrieval; P10 corpus proof |
| W3 PR-P4 | Piyush P10 cross-module proof | Atharv | Atharv | PR-P2/P3 merged; three-document/empty/malformed/lexical fallback tests | A9 clean-start corpus |
| W3 PR-N2 | Vanashree N3, N5–N7 | Atharv | Atharv | PR-N1, PR-A2 merged; **D2 approved**; real scanner excerpts, report save, four statuses | A7 coverage delegate, V7 real coverage; UI remains parallel |
| W4 PR-A4 | Atharv A7 real composition | Vandit | Atharv | PR-A3, PR-P2/P3, PR-N2 merged; service delegation/typed error test | V4/V7 real binding and A8 real SDK; V fake transports already merged |
| W4 PR-V2 | Vandit V5–V7 + focused V9 against fake service | Vanashree; Atharv checks service boundary | Atharv | HTTP routes/status/schema, upload limits, fake service tests | U6 mock-to-route validation; PR-V3 awaits A4 |
| W5 PR-V3 | Vandit V4/V7 real binding + V9 real tests | Atharv | Atharv | PR-V1/V2, PR-A4, PR-P2/P3, PR-N2 merged; MCP/HTTP real parity/restart | V10 native proof, U6 real API |
| W5 PR-U2 | Vanashree U6 real UI test; U5 native chat only after SDK/chat merges | Vandit | Atharv | PR-U1/PR-V3 merged; real navigation/error tests; real SDK response if U5 included | Data UI; native chat status explicit |
| W5 PR-V4 | Vandit V10 external Cline MCP proof | Atharv | Atharv | PR-V3 merged; actual tool call trace, `ev_` citation, cold start | Backend/external-client demo |
| W6 PR-A6 | Atharv A9 clean-start integration | Vandit | Atharv | PR-A4/PR-V3/PR-N2/PR-P4 merged; external MCP + coverage end-to-end | Backend baseline; native chat tracked separately |
| W6 PR-A5 | Atharv A8 Cline SDK gateway, scheduled after baseline if capacity permits | Vandit | Atharv | PR-A4 merged; installed SDK smoke/tool parity/session tests; no duplicate retrieval | V8/U5 native chat |
| W6 PR-V5 | Vandit V8 native chat routing, after PR-A5 if capacity permits | Vanashree | Atharv | PR-A5 merged; session/503/error tests; no HTTP agent logic | U5 native SDK chat |

**Open timing:** Each developer opens the PR exactly after the last task named in its row (and any stated blocker approval). `PR-V2` and `PR-A4` are independent until real binding, so either may merge first. `PR-U1` may merge before coverage core. `PR-P3` must not wait for `PR-A4`: it is an input to A7. `PR-A3` uses a frozen fake retrieval output; it must not wait for `PR-P3`. PR-A5/V5 are sequenced after the backend/external MCP baseline and must not delay it. PR-U2 may exclude U5 if SDK chat is unavailable; in that case native chat remains incomplete.

**Push/review timing:** When the row's focused tests and prerequisites pass, the author pushes the feature branch and opens the PR immediately using the title convention in their own roadmap. The author may continue the next independent fixture task while review runs. Atharv merges only after the listed reviewer approval and gate evidence; the author then updates from `integration/verity-v1` before the next real dependent task/PR. A review delay alone never blocks unrelated mock work.

## Hard waits, mocks and branch updates

| Boundary | Develop now with | Stop point / exact wait | Pull/update trigger |
|---|---|---|---|
| Canonical types/IDs | JSON fixtures and fake IDs | Real imports after PR-A1 | Pull after PR-A1, before dependent PR |
| Ingestion write | `FakeKnowledgeStore` | P5 real store/PR-P2 after PR-A2 | Pull PR-A2 before P5 real test |
| Retrieval/read/Evidence | Fake candidates and fake retrieval output | A5/A6 final PR after D1/D3; P9 real after PR-A3 | Pull PR-A3 before PR-P3 |
| Coverage | Fake snapshot/store/evaluator | N3 real excerpts after D2; N6 real store after PR-A2; PR-N2 after both | Pull PR-A2 and approved contract update before PR-N2 |
| MCP/HTTP | `FakeVerityService` | PR-V3 real binding after PR-A4 and producer merges | Pull all upstream merges before PR-V3 |
| UI | Frozen HTTP fixture/mock | U6 real route test after PR-V3 | Pull PR-V3 before PR-U2 |
| External Cline | MCP server smoke and scripted fixtures | V10 actual proof after PR-V3 | Pull PR-V3 before PR-V4 |
| Native SDK chat | Fake gateway and `SDK_UNAVAILABLE` | Real A8 after PR-A4; V8 after PR-A5; U5 after PR-V5 | Pull when pursuing the native chat slice; no fallback agent |

No constant rebasing: fixture-only work needs no pull. Pull integration after a shared foundation merge, before a real dependent test, before opening a dependent PR, or after a controlled shared-file change. Owners continue the parallel work named in their roadmap while a PR is reviewed.

## Contract blockers and change protocol

| Blocker | Affected task/PR | Mocks allow | Hard stop |
|---|---|---|---|
| D1 `06` tuple versus `16` `RetrievalRun` | ~~A6/PR-A3, P9/PR-P3, then A7~~ **RESOLVED 2026-10-04 (issue #2, change log 1.0.2)** | Fake retrieval output and RRF work | Cleared: `06` corrected to `RetrievalRun`; pull `Docs/contracts` once before P9/PR-P3 and A6/PR-A3 |
| D2 scanner-only read lacks text handoff | ~~N3/N6/N7/PR-N2, then A7/V7~~ **RESOLVED 2026-10-04 (issue #8 Option 2, change log 1.0.4)** | Fake snapshot and evaluator/UI | Cleared: `WorkspaceScanner.read_lines` in `16`; pull `Docs/contracts` once before N3/N5/PR-N2 |
| D3 active `Document.version_id` versus historical origin | ~~A5/A6/PR-A3~~ **RESOLVED 2026-10-04 (issue #7 Option B, change log 1.0.3)** | Active-record readers and evidence fixtures | Cleared: version-bound `Document` allowed in `get_evidence_origin` only; pull `Docs/contracts` once before A5/A6/PR-A3 |

For a contract bug, raise an issue listing affected consumers, exact conflicting clauses, minimal proposed amendment, version impact and tests. The team approves; the contract owner changes docs/version/fixtures per `02_VERITY_VERSIONING_POLICY.md`; affected owners pull once and implement. An implementation bug stays in the owner module; a private library/cache choice is implementation discovery; a layer/ownership change requires separate architecture approval. No feature branch edits frozen contracts unilaterally.

## Shared-file protection

`verity/models.py`, `ids.py`, `errors.py`, `config.py`, `storage/migrations/**`, `evidence.py`, `service.py`, root dependencies/lockfiles, root package exports and `tests/integration/**` belong to Atharv. `verity/ingestion/**`/`retrieval/**` belong to Piyush; `verity/mcp/**`/`http/**` to Vandit; `verity/coverage/**` and `sdk-ui/frontend/**` to Vanashree. `Docs/contracts/**` are shared but frozen. Generated DB/model caches/logs are not merged. Other-owner changes are requested with requested edit, reason, affected contract, consumer and urgency. Atharv alone resolves controlled root conflicts at integration; each subpackage owner handles its own exports. See [ownership](07_VERITY_MODULE_OWNERSHIP_MATRIX.md).
