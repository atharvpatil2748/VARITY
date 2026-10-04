# UI-facing HTTP API v1

**Owner:** Vandit for HTTP adapter; Atharv for service and Cline SDK gateway. **Consumers:** native VERITY UI, SDK adapter, tests. Native chat is executed by the Cline SDK behind the frozen chat routes; the UI renders its response. Base URL `http://127.0.0.1:8765/api/v1`. JSON request/response bodies use `03` models; unknown fields are rejected. Success has `Content-Type: application/json`, `X-Request-ID` and `X-VERITY-Contract-Version: 1.0.0`; no success wrapper is added to canonical models. Errors use `{"error": Error}` from `17`. V1 serves loopback only by default.

| Method and path | Request | 2xx response | Errors / status |
|---|---|---|---|
| `GET /health` | None | `200 Health` | `503` when DB unavailable |
| `POST /documents` | `multipart/form-data`: required `file` ≤25 MiB, `mode`=`auto|spec|general` default auto, optional `source_id` UUIDv4 for reingest; filename required | `201 IngestResult` for new source/version, `200 IngestResult` for same bytes | `400 INVALID_REQUEST`, `413 LIMIT_EXCEEDED`, `415 UNSUPPORTED_FORMAT`, `422 SPEC_VALIDATION_ERROR`/`PARSER_ERROR` |
| `GET /documents?limit=50&offset=0&kind=...` | `limit` 1–100, `offset` ≥0, optional `kind` DocumentKind | `200 ListPage<Document>` | `400 INVALID_REQUEST` |
| `GET /documents/{document_id}` | UUIDv4 path | `200 Document` | `404 DOCUMENT_NOT_FOUND` |
| `GET /sources?limit=50&offset=0` | Same pagination | `200 ListPage<Source>` | `400 INVALID_REQUEST` |
| `POST /search` | JSON `SearchRequest` | `200 SearchResult` | `400 INVALID_REQUEST`, `404 DOCUMENT_NOT_FOUND`, `503 RETRIEVAL_UNAVAILABLE`, `504 TIMEOUT` |
| `GET /requirements/{requirement_id}` | `req_` ID | `200 Requirement` | `404 REQUIREMENT_NOT_FOUND` |
| `GET /evidence/{evidence_id}?context_chars=1000` | `ev_` ID; context 0–4000 | `200 EvidenceLookup` | `404 EVIDENCE_NOT_FOUND`, `410 EVIDENCE_GONE` |
| `POST /coverage` | JSON `CoverageRequest` | `200 CoverageResult` | `400 INVALID_REQUEST`, `404 REQUIREMENT_NOT_FOUND`/`WORKSPACE_NOT_FOUND`, `403 WORKSPACE_DENIED`, `503 COVERAGE_UNAVAILABLE`, `504 TIMEOUT` |
| `GET /coverage/{coverage_id}` | UUIDv4 path | `200 CoverageResult` stored immutable run | `404 COVERAGE_NOT_FOUND` |
| `POST /chat/sessions` | JSON `{}` | `201 ChatSession` | `503 SDK_UNAVAILABLE` |
| `POST /chat/sessions/{session_id}/messages` | JSON `{text: nonempty string ≤8000}` | `200 ChatResponse` | `404 SESSION_NOT_FOUND`, `503 SDK_UNAVAILABLE`, `504 TIMEOUT` |

`Health = {schema_version:"1.0.0", status:"ok"|"degraded", database:"ready"|"unavailable", retrieval_mode:RetrievalMode|null, sdk_available:boolean}`; all fields required. `IngestResult = {schema_version:"1.0.0", document:Document, created_new_version:boolean}`. `ListPage<T> = {schema_version:"1.0.0", items:T[], limit:integer, offset:integer, total:integer>=0}`. `ChatSession = {schema_version:"1.0.0", session_id:UUIDv4, created_at:UTC date-time}`. These are canonical API objects, not alternate Evidence models. Their machine schemas belong in the shared schema companion.

List ordering is ascending ID, stable for a fixed DB snapshot. Offset pagination is only for list endpoints; `offset+limit` selects the slice and `total` counts filtered records. Search has no pagination. `GET /sources` exposes relative paths only. `GET /evidence` returns the same Evidence as search with `score=null` because direct lookup has no query score. Chat endpoints are frozen but may be unavailable at runtime; a missing embedded SDK is a truthful `SDK_UNAVAILABLE`, not a different native agent. The UI uses REST for data/chat: chat routes delegate to `SdkGateway` and its Cline SDK agent; other routes call `VerityService`. The HTTP router only validates/deserializes, delegates and serializes; it does not read SQLite, reason over chat, retrieve independently or calculate statuses.

Example search: `POST /api/v1/search` body `{"query":"duplicate refund","document_ids":null,"limit":5}` → `200 SearchResult` with ordered `Evidence[]`. Example invalid input: `{"query":" "}` → `400 {"error":{"schema_version":"1.0.0","code":"INVALID_REQUEST","message":"query must contain at least two characters","details":null,"request_id":"<uuidv4>","retryable":false}}`. Example coverage: `POST /api/v1/coverage` with `{"requirement_ids":["req_<64hex>"],"workspace_id":"demo","run_tests":false}` → `200 CoverageResult`.
