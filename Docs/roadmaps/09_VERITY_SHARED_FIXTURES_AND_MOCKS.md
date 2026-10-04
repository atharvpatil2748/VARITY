# Shared fixtures and mock plan

**Source:** frozen [contract tests](../contracts/18_VERITY_CONTRACT_TEST_PLAN.md), [schemas](../contracts/21_VERITY_V1_JSON_SCHEMAS.json), [IDs](../contracts/03_VERITY_DATA_SCHEMAS.md). These are implementation tasks, not files created by this roadmap pass. Fixtures contain no private Mnemo code.

| Fixture / fake | Creator and first delivery | Consumer; dependency removed | Required assertions |
|---|---|---|---|
| `tests/fixtures/contracts_v1/golden_ids.json` | Atharv, checkpoint 0 | Piyush materializer; Vandit/Vanashree ID shape | Exact four hash vectors from `03`; UUIDv4 syntax. |
| `golden_wire.json` containing valid `Source`, `Document`, `Requirement`, `Chunk`, `Evidence`, `SearchResult`, `EvidenceLookup`, `CoverageResult`, `Error` | Atharv creates model examples; Vandit adds schema-validation harness, checkpoint 0/1 | All owners can code before DB exists | Validate against `21`; same Evidence object in MCP/REST/SDK; nullable page and relative paths. |
| `payments.md`, `invalid_duplicate.md`, `invalid_reference.md` | Piyush, checkpoint 1 | Atharv store; Vanashree coverage; Vandit upload | Exact `04` parsed drafts, local IDs, line locators and validation errors. |
| `architecture.md`, `security.txt`, two-page `payments.pdf`, image-only PDF | Piyush, checkpoint 1/2 | Retrieval, API upload and UI | Page/heading/line provenance, cross-document query, partial/failed extraction. |
| `workspace/src/refund.py`, `workspace/tests/test_refund.py`, ignored vendor file, unsupported source | Vanashree, checkpoint 1 | Atharv coverage service; Vandit tool/API tests | Real line excerpts, comment-only false positive, implemented/partial/missing/uncertain. |
| `FakeKnowledgeStore` implementing only `16` calls used by one component | Atharv publishes protocol skeleton; each consumer may own a private fake | Piyush pipeline/retrieval and Vanashree report tests | No SQL or direct DB connection in owner modules; same-hash and missing-resource behavior. |
| `FakeRetrievalService` returning `RetrievalRun` with ranked chunks | Piyush sample object, Atharv may construct local fake earlier | Atharv EvidenceService tests | Citation, ranking metadata, omissions without model load. D1 must be approved before production wiring. |
| `FakeVerityService` returning canonical wire fixtures and typed errors | Vandit owns fake in transport tests, checkpoint 1 | MCP/HTTP can run before ingestion/coverage | One call per tool/route, strict input validation, identical JSON in MCP structured/text outputs. |
| `FakeCoverageService` returning four statuses | Vanashree, checkpoint 1 | Atharv service and Vandit transport | Input order, code/test evidence separated, immutable run ID. |
| `MockHttpApi` serving `11` JSON responses (or static response fixtures) | Vanashree owns UI mock, checkpoint 1 | Native UI presentation can build before HTTP server or Cline SDK agent | List pagination, empty search, null page, `SDK_UNAVAILABLE`, coverage display and SDK `ChatResponse` fixture. A mock chat response is not proof that native chat works. No alternate DTOs. |
| `FakeSdkTools` over `FakeVerityService`/HTTP fixtures | Atharv, native SDK gateway phase | Gateway tool tests before real service is available | Same four names and schemas as `09`, structured expected failures, citation markers. Final native chat proof still requires a real Cline SDK agent; no duplicate retrieval. |

No shared fake becomes a second canonical model. Prefer constructors from `verity.models` once foundation lands; before that, use JSON fixture validation against `21`. A fake returns the exact frozen type or JSON instance, never an approximate `MockEvidence` with different fields. Store fakes and UI mocks live in their owner's test directory, so they do not create merge conflicts.

## Cross-owner handoff packet

At each checkpoint, the producing owner hands over: (1) import/path or route, (2) one valid fixture, (3) one expected error fixture, (4) focused test command/result, (5) current limitations and model dependency, (6) exact commit hash. Consumers run their own contract test against that packet. If a fixture fails the frozen schema, the producer fixes it before merge; the consumer does not patch the model. No code or fixture should claim BGE semantic retrieval, reranking, Cline SDK or test execution ran when the local capability was absent.
