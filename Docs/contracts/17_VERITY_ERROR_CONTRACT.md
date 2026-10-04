# Error contract 1.0.0

**Owner:** Atharv for codes; Vandit for HTTP/MCP mapping. **Consumers:** all owners. All public failures become `Error` from `03`: `{schema_version:"1.0.0", code, message, details:null|object, request_id:UUIDv4, retryable:boolean}`. Core raises `VerityError` with the same code/message/details/retryable; adapters add `request_id`, serialize and do not expose tracebacks, credentials, absolute paths or model internals. Expected partial retrieval is a successful `SearchResult` with `omissions`, not an error.

| Code | When used | HTTP | Retryable default |
|---|---|---:|---|
| `INVALID_REQUEST` | Wrong type, bound, filter, ID syntax or unknown input field | 400 | false |
| `CONFIG_INVALID` | Startup config invalid | 500/health 503 | false |
| `VERSION_UNSUPPORTED` | Unsupported spec/config/schema/DB major or migration state | 409 | false |
| `UNSUPPORTED_FORMAT` | File media/extension unsupported | 415 | false |
| `SPEC_VALIDATION_ERROR` | Malformed authored spec, duplicate/dangling ID | 422 | false |
| `PARSER_ERROR` | Extraction failed or no usable content | 422 | false |
| `CHUNKING_ERROR` | Invalid chunk span/empty output for nonempty parsed doc | 500 | false |
| `LIMIT_EXCEEDED` | Upload/response/scan bound exceeded | 413 | false |
| `SOURCE_NOT_FOUND` | Reingest source ID absent | 404 | false |
| `DOCUMENT_NOT_FOUND` | Document ID/filter absent | 404 | false |
| `REQUIREMENT_NOT_FOUND` | Active requirement ID absent | 404 | false |
| `EVIDENCE_NOT_FOUND` | Never-known evidence ID | 404 | false |
| `EVIDENCE_GONE` | Previously valid version removed by retention | 410 | false |
| `COVERAGE_NOT_FOUND` | Coverage run ID absent | 404 | false |
| `WORKSPACE_NOT_FOUND` | Workspace config key/root absent | 404 | false |
| `WORKSPACE_DENIED` | Path escape, permission or disallowed workspace access | 403 | false |
| `MODEL_UNAVAILABLE` | Configured local model not provisioned | 503 | true |
| `RETRIEVAL_UNAVAILABLE` | Both search branches unavailable or index corrupt | 503 | true |
| `COVERAGE_UNAVAILABLE` | Scan/test infrastructure cannot produce trustworthy run | 503 | true |
| `SDK_UNAVAILABLE` | Cline SDK gateway for native VERITY chat not configured/running | 503 | true |
| `SESSION_NOT_FOUND` | Chat session absent/expired | 404 | false |
| `TIMEOUT` | Operation deadline exceeded | 504 | true |
| `INTERNAL_ERROR` | Unexpected failure; details sanitized | 500 | true |

HTTP success and error shapes are in `11`; MCP uses `isError=true` and the same Error object. SDK tool `execute` returns the same Error data for expected errors instead of throwing into the agent loop. `details` can include `field`, `line`, `expected_version`, `actual_version`, or bounded omission labels as appropriate; unknown detail keys are allowed, but never duplicate top-level fields. Error messages are plain English and not parsed by clients; clients branch on `code`. A not-found resource is distinct from a valid empty search. Unknown exceptions are logged with `request_id` on stderr and mapped to `INTERNAL_ERROR`.
