# MCP tools v1.0.0

**Owner:** Vandit. **Consumers:** external Cline clients, Atharv SDK parity and service teams. MCP exposes VERITY's evidence and knowledge layer to external Cline clients; native VERITY chat uses the Cline SDK under `10`. The canonical four tools are `search_evidence`, `get_requirement`, `get_evidence`, `check_coverage`. No aliases for `search_knowledge`, `search_multi_document`, `trace_provenance` or `compare_sources`. `search_evidence` supports multi-document filters; `get_evidence` includes provenance. The MCP server exposes stdio. Logs use stderr and stdout is protocol-only.

Each call validates the exact JSON Schema below and invokes the named `VerityService` method once. MCP output's `structuredContent` is the canonical success object from `03`, without a transport-specific model. For clients requiring text content, return the identical compact JSON serialization in `content[0].text`. Errors set MCP `isError=true` and return the canonical `Error` object in `structuredContent` and mirrored text. No tool handler calls SQLite, formats a citation, runs retrieval strategies or scans files itself. `request_id` is assigned by adapter and appears on errors; success payloads are canonical model objects. All input schemas have `additionalProperties:false`.

| Tool | Core call | Deterministic / side effect | Deadline |
|---|---|---|---|
| `search_evidence` | `VerityService.search_evidence(SearchRequest)` | Deterministic for fixed index/model; read-only | 15 s |
| `get_requirement` | `VerityService.get_requirement(requirement_id)` | Deterministic; read-only | 5 s |
| `get_evidence` | `VerityService.get_evidence(evidence_id, context_chars)` | Deterministic; read-only | 5 s |
| `check_coverage` | `VerityService.check_coverage(CoverageRequest)` | Depends on workspace snapshot; writes an immutable report, never code | 30 s |

## Exact input schemas

```json
{
  "search_evidence": {"type":"object","additionalProperties":false,"required":["query"],"properties":{"query":{"type":"string","minLength":2,"maxLength":2000},"document_ids":{"type":["array","null"],"minItems":1,"maxItems":100,"uniqueItems":true,"items":{"type":"string","format":"uuid"},"default":null},"document_kinds":{"type":["array","null"],"minItems":1,"uniqueItems":true,"items":{"type":"string","enum":["spec","general"]},"default":null},"chunk_kinds":{"type":["array","null"],"minItems":1,"uniqueItems":true,"items":{"type":"string","enum":["requirement","acceptance_criterion","api_definition","general_chunk","code_chunk"]},"default":null},"limit":{"type":"integer","minimum":1,"maximum":20,"default":8},"per_document_limit":{"type":["integer","null"],"minimum":1,"maximum":20,"default":null}}},
  "get_requirement": {"type":"object","additionalProperties":false,"required":["requirement_id"],"properties":{"requirement_id":{"type":"string","pattern":"^req_[0-9a-f]{64}$"}}},
  "get_evidence": {"type":"object","additionalProperties":false,"required":["evidence_id"],"properties":{"evidence_id":{"type":"string","pattern":"^ev_[0-9a-f]{64}$"},"context_chars":{"type":"integer","minimum":0,"maximum":4000,"default":1000}}},
  "check_coverage": {"type":"object","additionalProperties":false,"required":["requirement_ids","workspace_id"],"properties":{"requirement_ids":{"type":"array","minItems":1,"maxItems":50,"uniqueItems":true,"items":{"type":"string","pattern":"^req_[0-9a-f]{64}$"}},"workspace_id":{"type":"string","pattern":"^[a-z][a-z0-9_-]{0,31}$"},"run_tests":{"type":"boolean","default":false}}}
}
```

Output schemas are the exact `$defs` in `21_VERITY_V1_JSON_SCHEMAS.json`: `search_evidence -> SearchResult`, `get_requirement -> Requirement`, `get_evidence -> EvidenceLookup`, `check_coverage -> CoverageResult`. Every output has `schema_version=1.0.0`; unknown output fields are prohibited in v1. Error output is `$defs/Error`. This reference avoids four divergent copies of Evidence.

Examples: `search_evidence({"query":"duplicate refund"}) -> SearchResult{items:[Evidence...]}`; `get_requirement({"requirement_id":"req_<64hex>"}) -> Requirement{local_id:"REQ-003",...}`; `get_evidence({"evidence_id":"ev_<64hex>"}) -> EvidenceLookup{evidence:Evidence,...}`; `check_coverage({"requirement_ids":["req_<64hex>"],"workspace_id":"demo"}) -> CoverageResult{results:[RequirementCoverage...]}`. Placeholder IDs in examples must be replaced with actual 64-hex IDs in tests. Tool descriptions tell Cline to use `search_evidence` before coding, resolve exact clauses with `get_requirement`, cite Evidence markers, and call `check_coverage` after changes. Descriptions are guidance, not a policy enforcement mechanism.

Errors by tool: search `INVALID_REQUEST`, `DOCUMENT_NOT_FOUND`, `RETRIEVAL_UNAVAILABLE`, `TIMEOUT`; requirement/evidence `INVALID_REQUEST`, `REQUIREMENT_NOT_FOUND`/`EVIDENCE_NOT_FOUND`, `EVIDENCE_GONE`; coverage `INVALID_REQUEST`, `REQUIREMENT_NOT_FOUND`, `WORKSPACE_NOT_FOUND`, `WORKSPACE_DENIED`, `COVERAGE_UNAVAILABLE`, `TIMEOUT`. All may return `VERSION_UNSUPPORTED` or `INTERNAL_ERROR` if relevant. A no-match search returns an empty SearchResult, never an error. MCP registration and serialization are transport-owned; use the installed MCP SDK's exact result shape in implementation, verified by contract tests.
