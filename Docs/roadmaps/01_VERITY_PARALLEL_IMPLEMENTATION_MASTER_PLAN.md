# VERITY parallel implementation master plan

**Status:** implementation roadmap, no application code. **Inputs:** original [PPTX](../pptx/VERITY_Cline_Hackathon_Round1_v2.pptx), current [PPT/demo addendum](../pptx/VERITY_CLINE_INTEGRATION_DEMO_ADDENDUM.md), [architecture](../ARCHITECTURE.md), [frozen contract index](../contracts/01_VERITY_CONTRACT_INDEX.md), [machine schemas](../contracts/21_VERITY_V1_JSON_SCHEMAS.json). **Authority:** documentation patch 1.0.1; wire schemas/tools/API remain 1.0.0. **Sprint:** eight-hour offline hackathon. The backend and external Cline MCP demo are the first delivery baseline. **Cline SDK powers native VERITY chat UI; MCP exposes VERITY to external Cline clients.** Native SDK chat may be implemented later in the sprint, without changing that architecture.

**Start condition:** all four can read their assigned contracts and prepare fixtures at C0 now. This local workspace currently has only `Docs/` and no `.git`; before W1 branch work, the team must connect/initialize the repository and create `integration/verity-v1`. D1–D3 are hard stops only at their named real-integration PRs, not for W1 mock-based work. No repository initialization or code work is performed by this planning pass.

## Open the correct roadmap

| Developer | Owned vertical slice | Individual plan |
|---|---|---|
| Atharv Patil | canonical foundation → SQLite → Evidence → service → SDK gateway | [02](02_VERITY_ROADMAP_ATHARV_PATIL.md) |
| Piyush Ghayal | spec/general bytes → normalized chunks → embedding/FTS candidates → `RetrievalRun` | [03](03_VERITY_ROADMAP_PIYUSH_GHAYAL.md) |
| Vandit Gupta | `VerityService` → MCP/HTTP wire → external Cline call proof; native chat routing to SDK | [04](04_VERITY_ROADMAP_VANDIT_GUPTA.md) |
| Vanashree | configured workspace → code/test evidence → coverage; `/api/v1` → native UI, including SDK chat presentation | [05](05_VERITY_ROADMAP_VANASHREE.md) |

The full [dependency matrix](06_VERITY_CONTRACT_DEPENDENCY_MATRIX.md), [file ownership](07_VERITY_MODULE_OWNERSHIP_MATRIX.md), [merge plan](08_VERITY_MERGE_AND_INTEGRATION_PLAN.md), and [fixture/mock plan](09_VERITY_SHARED_FIXTURES_AND_MOCKS.md) are companion roadmaps. Developers read their own required contracts, not the entire package before starting.

## Reconciled boundary and actual dependency graph

Core backend: canonical models → storage → ingestion → retrieval → Evidence → coverage → `VerityService` composition. Coverage is a separate core service composed at the same boundary, not an alternate retrieval engine. Two client paths converge there: external Cline → MCP → `VerityService`; native VERITY UI → `/api/v1/chat` → Cline SDK gateway/agent → canonical SDK tools → `VerityService`. Non-chat UI data views use `/api/v1` directly. The SDK agent reasons and writes the native chat answer; VERITY supplies the same canonical facts and Evidence to both paths.

```text
Core:    models → storage → ingestion → retrieval → Evidence → VerityService
         workspace scanner → coverage ────────────────────→ VerityService

External client:  External Cline → MCP adapter ──────────→ VerityService

Native chat:      User → VERITY UI → /api/v1/chat → SDK gateway
                 → Cline SDK Agent → canonical SDK tools → VerityService
                 ← Cline SDK answer + canonical Evidence ←──────────────┘

Native data views: VERITY UI → /api/v1 → VerityService
```

The work is parallel until real interfaces join. Atharv's **types/IDs** are needed for real imports; `21` wire fixtures bridge them for early adapter/UI skeletons. Store and retrieval meet through `KnowledgeStore`, not SQL edits by Piyush. Coverage and transport meet through `VerityService`, not scanner imports in Vandit's handlers. UI meets transport through `/api/v1`, not MCP. Native chat uses the SDK gateway behind that API and never has an independent retrieval/agent implementation. One canonical Evidence object crosses both Cline integrations and UI display. The physical FTS table belongs to Atharv; lexical query behavior belongs to Piyush. No ownership correction is proposed.

## Global parallelism and exact task gates

These are dependency windows, not synchronized waiting periods. A row may overlap the next when its own prerequisites are satisfied. [08](08_VERITY_MERGE_AND_INTEGRATION_PLAN.md) is the exact PR ledger.

| Window | Atharv | Piyush | Vandit | Vanashree | Blocked by / merge gate |
|---|---|---|---|---|---|
| W0 contract prep | A0 | P0 | V0 | N0 | All parallel; record D1–D3, no code PR |
| W1 independent/fake | A1–A3 → PR-A1 | P1–P4 → PR-P1; P6–P8 fake | V1–V4 → PR-V1; V5–V7 fake | N1/N2 safe metadata/N4 → PR-N1; U1–U4 → PR-U1 | Real imports wait PR-A1; all can use `21`/fakes |
| W2 persistence/ingestion | A4 → PR-A2; A5/A6 fixture work | P5 fake then PR-P2 after A2; P6–P8 continue | V5–V7/V9 fake → PR-V2 | N3/N5/N6 fake; U6 mock | Real P5/N6 wait PR-A2; A5/A6 PR-A3 waits D1/D3 |
| W3 producer seams | A5–A6 → PR-A3 after D1/D3; A7 fake | P9 → PR-P3 after A3/D1; P10 → PR-P4 | V9 real-test preparation; V8 unavailable path | N3/N5–N7 → PR-N2 after D2/A2; U1–U4 can merge | D1/D2/D3 contract approvals are hard PR stops |
| W4 service/transport | A7 real → PR-A4 after P2/P3/N2/A3 | P10 regressions/owned defects | V4/V7 real + V9 → PR-V3 after A4; fake PR-V2 can merge earlier | U6 real after V3; N7 regressions | Real service waits producer PRs; transport waits A4 |
| W5 external proof / native chat | A9 → PR-A6; A8 → PR-A5 if sprint capacity | Support owned retrieval defects | V10 → PR-V4; V8 → PR-V5 if SDK ready | U6 → PR-U2; U5 after SDK/chat merge | External proof waits V3; native chat waits A5/V5, never switches to another agent |

### Dependency DAG: soft versus hard

```text
Frozen 03/05/06/07/09/11/12/16/21 → fixtures/fakes (SOFT: all four start W0/W1)
A1–A3 / PR-A1 → canonical imports for P4,V3,N1 (HARD only for real imports)
A4 / PR-A2 → P5 real write / PR-P2 and N6 real persistence / PR-N2 (HARD)
D1+D3 approved → A5–A6 / PR-A3 → P9 real candidates / PR-P3 (HARD)
D2 approved + PR-A2 → N3+N6+N7 / PR-N2 (HARD)
PR-P2 + PR-P3 + PR-N2 + PR-A3 → A7 / PR-A4 (HARD)
PR-A4 + fake transport PR-V1/PR-V2 → V9 real / PR-V3 (HARD)
PR-V3 → V10 / PR-V4 and U6 / PR-U2 (HARD)
PR-A4 → A8 / PR-A5 → V8 / PR-V5 → U5 real native SDK chat (HARD; scheduled after backend/MCP baseline)
```

Every soft edge has a fixture: `FakeKnowledgeStore` for P5/P6/N6, frozen retrieval output for A6, `FakeVerityService` for V1–V9, fake snapshot for N3/N4, and mock HTTP JSON for U1–U6. No developer waits idle on a soft edge. A hard edge means **do not open the dependent real-integration PR** until the named upstream PR is merged or the contract amendment approved.

## Contract discrepancy gates — do not edit frozen docs automatically

The current frozen package has three genuine boundary issues recorded in [06](06_VERITY_CONTRACT_DEPENDENCY_MATRIX.md): **D1** `06` says `RetrievalService.search` returns a tuple while `16` says `RetrievalRun`; **D2** scanner-only file access lacks a text/read handoff to the code retriever; **D3** historical evidence lookup returns a `Document` whose model describes the active version. `01` makes `16` authoritative for callable signatures, so interface stubs use `RetrievalRun` while D1 awaits team approval. D2 must be settled before real coverage candidate extraction; D3 before historical evidence resolution. Minimum amendments and affected owners are in `06`; the roadmap changes no contract. The older architecture's `compare_sources` suggestion is already superseded by the frozen four-tool list and is not a new discrepancy.

## Interface-first checkpoints

| Checkpoint | Must work; participants | Tests and freeze/merge result |
|---|---|---|
| C0 contract verification | All owners identify R documents, output models, D1–D3 and local model availability | `21` parse, golden ID vector understood; any approved contract amendment precedes dependent code. |
| C1 models/IDs + skeletons | Atharv foundation importable; Piyush parsed drafts; Vandit fake service tools/routes; Vanashree evaluator/UI mock | Schema/ID tests, parser fixture, fake transport/coverage tests; merge small owner commits. Types/IDs fixed after merge. |
| C2 producer seams | PR-A2, PR-P2, PR-A3, PR-P3, PR-P4 and PR-N2 | D1/D3 before A3/P3; D2 before N2. Store, parser, retrieval, Evidence and real coverage tests pass. A3 uses frozen fake retrieval output before P3, avoiding a cycle. |
| C3 core service and transports | PR-A4 then PR-V3; PR-V1/V2 fake adapters may already be merged | Real service delegation, four MCP tool schemas, HTTP routes/statuses, structured/text parity. |
| C4 real workspace coverage via service | PR-N2 is merged before A4; Vandit rechecks V7 after V3 | Four statuses, exact code/test lines, report persistence and MCP/HTTP parity. |
| C5 external Cline proof | PR-V4; all support owned defects | Observe actual MCP calls, cited evidence markers and fresh coverage; freeze backend/external-client demo. |
| C6 native SDK chat and UI | PR-U1 can merge early; PR-U2 after V3. PR-A5/PR-V5 implement native chat when capacity permits. | UI/REST contract and same Evidence; SDK smoke or `SDK_UNAVAILABLE`. An unavailable SDK means native chat is incomplete, not replaced by another native agent. |
| C7 clean-start rehearsal | All | Offline restart, both flagship spec/code and general multi-doc query; paired evaluation only with measured results. |

Mocks remove most waiting: Piyush uses `FakeKnowledgeStore`; Atharv uses `FakeRetrievalService`/`FakeCoverageService`; Vandit uses `FakeVerityService`; Vanashree uses a fake store and `MockHttpApi`. [09](09_VERITY_SHARED_FIXTURES_AND_MOCKS.md) names exact fixture contents and handoff packets. The unmockable gates for the backend/external-client demo are local model availability (or truthful lexical fallback), actual MCP connection to external Cline, workspace read safety after D2, and a working service composition. A complete native chat UI additionally requires the real Cline SDK agent, gateway, chat route and UI response rendering.

## Master module table

| Module | Owner | Inputs | Outputs | Required contracts | Consumers | Merge stage |
|---|---|---|---|---|---|---|
| `models.py`, `ids.py`, `errors.py`, `config.py` | Atharv | `03`/`14`/`17`/`21` | Canonical objects, IDs, config, typed errors | 03, 14, 16, 17, 21 | All | C1 |
| `storage/*` | Atharv | Canonical ingestion batch, queries, coverage report | `KnowledgeStore` and DB v1 | 03, 05, 13, 16 | Piyush, Vanashree, service | C2/C4 |
| `ingestion/*` | Piyush | File bytes, `IngestRequest`, store | `ParsedDocument`, drafts, chunks/requirements, `IngestResult` | 03, 04, 05, 16, 21 | Atharv service/store, Vandit upload | C1/C2 |
| `retrieval/*` | Piyush | `SearchRequest`, store candidates, models | `RetrievalRun` | 03, 06, 08, 16 | Atharv evidence | C2 |
| `evidence.py`, `service.py` | Atharv | Retrieval run, origin, coverage | `Evidence`, `SearchResult`, `VerityService` | 03, 07, 16 | Vandit, SDK, UI via REST | C2/C3 |
| `coverage/*` | Vanashree | Requirement, workspace config/snapshot | `CoverageResult` | 03, 12, 16, 21 | Atharv, Vandit, UI | C4 |
| `mcp/*`, `http/*` | Vandit | Typed service results/requests; SDK gateway for chat route | Four MCP tools, `/api/v1` | 09, 10, 11, 16, 17, 21 | External Cline, native UI | C3/C4; chat at C6 |
| `sdk-ui/gateway/*` | Atharv | Same four tool schemas, `VerityService` capability boundary | Cline SDK agent execution, session/chat response | 09, 10, 11, 21 | Native UI via chat API | C6 after core baseline |
| `sdk-ui/frontend/*` | Vanashree | `/api/v1` JSON, SDK chat response | Evidence/coverage display and native SDK chat presentation | 03, 07, 10, 11, 12, 21 | User/demo | Mock early; real chat C6 |

## Contract reading matrix

R = required, C = consumer/reference at boundary, – = not required. See [06](06_VERITY_CONTRACT_DEPENDENCY_MATRIX.md) for why.

| Contract | Atharv | Piyush | Vandit | Vanashree |
|---|:---:|:---:|:---:|:---:|
| 01 Index | R | R | R | R |
| 02 Versioning | R | C | C | C |
| 03 Data | R | R | C | R |
| 04 Spec | C | R | – | C |
| 05 Ingestion | R | R | C | – |
| 06 Retrieval | C | R | C | C |
| 07 Evidence | R | C | C | C |
| 08 Multi-document | C | R | C | C |
| 09 MCP | C | – | R | – |
| 10 SDK | R | – | C | C |
| 11 API | C | – | R | R |
| 12 Coverage | C | – | C | R |
| 13 Database | R | C | – | C |
| 14 Config | R | C | C | C |
| 15 Boundaries | R | R | R | R |
| 16 Interfaces | R | R | R | R |
| 17 Errors | R | C | R | C |
| 18 Tests | R | R | R | R |
| 19 Ownership | R | R | R | R |
| 20 Baseline | R | C | C | C |
| 21 JSON schemas | R | R | R | R |

## Directory edit matrix

| Directory/file | Owner | Other developers may modify? |
|---|---|---|
| `verity/models.py`, `ids.py`, `errors.py`, `config.py`, `storage/*`, `evidence.py`, `service.py` | Atharv | No; service/root edits at integration only. |
| `verity/ingestion/*`, `retrieval/*` | Piyush | No. |
| `verity/mcp/*`, `http/*` | Vandit | No. |
| `verity/coverage/*`, `sdk-ui/frontend/*` | Vanashree | No. |
| `sdk-ui/gateway/*` | Atharv | No. |
| `Docs/contracts/*` | Frozen contract owner through `02` | No unilateral edits. |
| `tests/fixtures/contracts_v1/golden_*` | Atharv creates; Vandit validates | Controlled edits only after fixture review. |
| Root dependency/lock files, `verity/__init__.py`, `tests/integration/*` | Atharv integrator | Submit request/test, not parallel edit. |

## Final parallel execution model

| Hour | Parallel work → contract/module → test → checkpoint/merge |
|---|---|
| 0–1 | All A0/P0/V0/N0 read exact owned contracts; record D1–D3. Begin A1–A3, P1–P4, V1–V4 and N1/N4/U1 with fixtures. **C0**; no PR waits. |
| 1–2 | Open PR-A1/P1/V1/N1/U1 as each exact last step finishes; Piyush P6–P8, Vandit V5–V7, Vanashree mock UI continue during review. Merge each after its reviewer/gate. **C1**. |
| 2–4 | A4→PR-A2; P5 fake→PR-P2 after A2; A5/A6 fixture work→PR-A3 only after D1/D3; N3/N6 fake→PR-N2 only after D2/A2; V5–V7/V9 fake→PR-V2. **C2**. |
| 4–5 | P9/P10→PR-P3/P4 after A3; N2 coverage PR merges when D2 approved; A7 real composition→PR-A4 after P2/P3/N2. Vandit prepares V9 real while waiting. **C2/C3**. |
| 5–6 | V4/V7/V9 real→PR-V3 after A4; Vanashree U6 switches to real API after V3; Atharv A9 clean-start preparation. Run four-status/line-span and MCP/HTTP parity. **C3/C4**. |
| 6–7 | Vandit V10 actual external Cline MCP proof→PR-V4; Vanashree U6→PR-U2; Atharv A9→PR-A6. Others fix only owned defects. **C5** backend/external-client demo. |
| 7–8 | If baseline remains green: Atharv A8→PR-A5, Vandit V8→PR-V5, Vanashree U5 native SDK chat. Rehearse offline restart. **C6/C7**. Times are estimates; native chat is complete only after real SDK integration and tests. |

Each merge is gated by owner-focused tests, `21` schema validation and the previous checkpoint's smoke test. No giant final merge, duplicate Evidence representation, contract rewrite, or application implementation is part of this planning deliverable.
