# Shared contract test plan

**Owner:** Vandit maintains transport contract harness; each module owner supplies its own implementation fixtures. **Consumers:** all owners. These tests check contracts, not private algorithms. Test fixtures live under `tests/fixtures/contracts_v1/` when code work starts. The freeze itself creates no test code.

## Frozen fixtures

1. `payments.md`: valid spec from `04`, REQ-001/REQ-002, API-001, AC-001; a second invalid spec has duplicate REQ-001 and a dangling AC reference.
2. `architecture.md`: headings and refund retry policy.
3. `security.txt`: idempotency guidance that overlaps a spec term.
4. `payments.pdf`: two text pages, known passage on page 2; separate image-only PDF produces `PARSER_ERROR`/partial as specified.
5. `workspace/`: `src/refund.py` with one implemented boundary, an ID only in a comment, `tests/test_refund.py` with one relevant test and one irrelevant test, plus ignored/vendor file.
6. `golden_ids.json`: canonical source/version UUIDs, payloads and expected deterministic block/chunk/requirement/evidence hashes **fixed in `03`**; Atharv copies these exact values into the test fixture before code.
7. `golden_wire.json`: one valid JSON instance for each `03` model and each MCP/API success and error response.

| Interface | Happy path | Invalid / empty / missing / malformed / version mismatch |
|---|---|---|
| Spec parser | Valid front matter and relations map to exact Requirement and line locators | Duplicate/missing ID, dangling ref, empty text, malformed YAML, unknown `verity_spec` |
| General parser | PDF page 2, MD heading, TXT paragraph, code lines | Unsupported MIME, empty bytes, image-only PDF, invalid UTF-8, unknown parser version |
| Chunker | Deterministic ordered drafts, no page crossing, reproducible IDs | Invalid block span, empty parsed doc, missing page, changed version ID |
| Store | Atomic reingest, same-hash idempotence, historical evidence | Missing source/document, malformed metadata JSON, greater DB `user_version`, FTS rebuild/delete |
| Retrieval | Three-document query, deterministic RRF tie, filter before ranking, rerank fallback | Blank query, unknown doc, no matches, one/both branch failures, unsupported model revision |
| Evidence | Search/direct lookup share schema, exact quote, canonical label, historical resolution | Unknown ID, removed version, quote mismatch, null page, malformed marker |
| MCP | Four registered names, strict inputs, structuredContent equals text JSON | Extra field, bad ID, empty search, missing req/evidence, version mismatch, expected error mapping |
| REST | Every endpoint path/method/status, list offset, multipart ingest, chat unavailable | Invalid JSON/multipart, bounds, not found, 410 gone, 503 SDK, version mismatch |
| Coverage | Real code/test line spans and all four statuses | ID-only comment, no tests, unsupported file, path escape, changed snapshot, missing workspace, timeout |
| SDK tools | Same names/input/output as MCP and valid citation markers | Tool error object, unresolved citation, expired session, unavailable SDK version |
| Native VERITY chat | Real Cline SDK agent invoked through `/api/v1/chat/*`; UI renders `ChatResponse` and resolved `Evidence[]` from canonical tools | Missing SDK yields `SDK_UNAVAILABLE`; no UI retrieval, independent agent answer or fabricated citation |

Each owner runs its focused contract suite before handoff. At hours 1, 3 and 5, all owners run the shared golden schema/ID suite. At hour 6, one end-to-end clean-start test ingests fixtures, runs multi-document search, resolves every returned evidence ID, exposes MCP, and checks coverage on the workspace. No test may assert a desired retrieval result by reading private SQL internals. The acceptance fixture records expected evidence IDs and status reasons, not only counts.

Schema validation uses the shared machine-readable JSON Schema companion in this `contracts` folder, including `additionalProperties:false` for v1 public input/output. The test harness also checks that every required public object carries `schema_version`, metadata carries `metadata_version`, all page values are positive or null, all public source paths are relative, and errors never leak absolute paths. An SDK smoke test pins the installed package and checks actual event/result properties. If the SDK cannot run, native chat reports `SDK_UNAVAILABLE` and is not counted as complete; the backend/external MCP baseline can still pass.
