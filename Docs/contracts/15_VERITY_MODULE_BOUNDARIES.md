# Module boundaries and dependency rules

**Owner:** Atharv for boundary changes. **Consumers:** all owners. The proposed package is `verity`. Public types/signatures are in `03` and `16`; ownership in `19`. No transport adapter contains business logic. Imports flow downward and cannot form cycles.

```text
models, errors, ids, config (foundation)
          ^
storage <--- ingestion
   ^             ^
   +--- retrieval+--- evidence
          ^             ^
          +--- service -+--- coverage
                    ^
         MCP / HTTP / Cline SDK adapters
                    ^
                    UI
```

| Module / owner | Owns and public boundary | Allowed dependencies | Forbidden dependencies |
|---|---|---|---|
| `verity/models.py`, `ids.py`, `errors.py`, `config.py` / Atharv | Canonical objects, ID generation, errors, config | Standard library / validation library | ingestion, storage, retrieval, coverage, transports |
| `verity/storage/*` / Atharv | SQLite DDL, migrations, `KnowledgeStore`, originals | foundation | MCP, HTTP, SDK, UI; no retrieval algorithms |
| `verity/ingestion/*` / Piyush | Spec/general parsing, normalized blocks, chunk drafts, ingestion coordinator | foundation and `KnowledgeStore` protocol | transports, coverage, direct SQL |
| `verity/retrieval/*` / Piyush | lexical/semantic ranking, RRF, rerank, `RetrievalService` | foundation and `KnowledgeStore` protocol | MCP, HTTP, SDK, UI, coverage evaluator; no SQL outside store |
| `verity/evidence.py` / Atharv | Evidence construction, resolver, citation formatter | foundation, store protocol, retrieval result | transports, coverage, direct SQL |
| `verity/coverage/*` / Vanashree | workspace scanner, candidate search, evaluator, `CoverageService` | foundation, `KnowledgeStore` protocol, optional retrieval public interface | MCP, HTTP, SDK, UI, direct SQL, writing code |
| `verity/service.py` / Atharv | `VerityService` orchestration / composition | all core public interfaces | transport-specific types, SQL |
| `verity/mcp/*` / Vandit | MCP registration, input validation, structured serialization | service, foundation | storage internals, retrieval internals, workspace scanner internals |
| `verity/http/*` / Vandit | `/api/v1` router and JSON/multipart serialization | service, foundation, SDK gateway protocol | SQL, ranking, coverage rules |
| `sdk-ui/gateway/*` / Atharv | Cline SDK agent runtime and canonical tool wrappers for native VERITY chat | public HTTP/service boundary only | SQLite, parser/retrieval internals, independent retrieval or Evidence logic |
| `sdk-ui/frontend/*` / Vanashree | Native VERITY UI; REST data views and SDK-agent chat presentation | `/api/v1` canonical responses only | SQLite, MCP client calls, private core imports, independent chat/retrieval engine |

Single concern owners: parsing/chunking/retrieval/reranking Piyush; persistence, evidence and citation Atharv; coverage Vanashree; MCP and API serialization Vandit; Cline SDK agent execution and SDK serialization Atharv. External Cline reaches `VerityService` through MCP. Native VERITY chat reaches the same service through the Cline SDK gateway's canonical tools. `VerityService` assembles these interfaces but does not reimplement them. File ownership is by module, not by every helper. Shared model/schema files are controlled by Atharv and rarely edited after freeze. A desired new field starts as a contract change under `02`, not a unilateral model edit.
