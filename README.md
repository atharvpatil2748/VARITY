# VERITY

**Your documents. Your specs. Evidence that Cline can cite.**

VERITY is a local-first document/spec knowledge service for [Cline](https://cline.bot): it ingests
specifications and documents into a versioned SQLite knowledge store, retrieves them with
citable `Evidence`, and verifies whether your code actually implements the requirements —
every answer traceable to an exact source chunk, never invented.

- **Canonical evidence**: deterministic IDs (`req_…`, `ev_…`), exact quote + locator + version-bound provenance
- **Four frozen MCP tools** for external Cline clients: `search_evidence`, `get_requirement`, `get_evidence`, `check_coverage`
- **Native SDK chat**: a Cline-SDK-powered gateway and web UI for the VERITY agent (never a fake answer — `SDK_UNAVAILABLE` otherwise)
- **Honest coverage**: `IMPLEMENTED` / `PARTIAL` / `MISSING` / `UNCERTAIN` verdicts from inspectable evidence only; comment-only matches never count

## Architecture

```
                     ┌────────────────────────────────────────────┐
 external Cline ───▶ │ MCP stdio server (verity.mcp) ── four tools │──┐
                     └────────────────────────────────────────────┘  │
                     ┌────────────────────────────────────────────┐  │   ┌──────────────┐
 native chat UI  ───▶ │ HTTP API /api/v1 (loopback) + SDK gateway   │──┼──▶│ VerityService │
 (sdk-ui/frontend)   └────────────────────────────────────────────┘  │   └──────┬───────┘
                                                                       │          │
                     ┌────────────────────────────────────────────┐  │          │
 web browser     ───▶ │ HTTP API (documents/search/evidence/…)    │──┘          │
                     └────────────────────────────────────────────┘             │
                                                                              ▼
        ingestion (parser → chunker → spec records)   retrieval (lexical/hybrid + fusion)
        evidence service (citations, provenance)     coverage service (scanner → evaluator)
                                       └──────────── SQLite (FTS5) KnowledgeStore ────────────┘
```

One `VerityService` (contract 16) is the only adapter-facing API. MCP, HTTP, the SDK gateway
and the UI delegate to it and never touch SQL, ranking or citation logic directly.

## Repository layout

| Path | What lives here |
|---|---|
| `verity/models.py`, `ids.py`, `errors.py`, `config.py` | Canonical models, deterministic IDs, typed errors, configuration |
| `verity/storage/` | SQLite `KnowledgeStore` — the only package with SQL (migrations, FTS5) |
| `verity/ingestion/` | Parser router, chunkers, spec extraction, ingestion pipeline |
| `verity/retrieval/` | Lexical candidates, dense seam, RRF fusion, reranker |
| `verity/evidence.py` | Canonical `Evidence`/`Citation` assembly and provenance |
| `verity/service.py` | `VerityService` composition + the frozen `build_service()` factory |
| `verity/mcp/` | MCP stdio server (`python -m verity.mcp`), four frozen tools |
| `verity/http/` | FastAPI loopback API (`/api/v1`) incl. chat session routes |
| `verity/coverage/` | Workspace scanner, candidate retriever, allowlisted test runner, evaluator |
| `sdk-ui/gateway/` | Cline SDK chat gateway (Python) + pinned `@cline/sdk` Node bridge |
| `sdk-ui/frontend/` | Static web UI: documents, search, evidence, coverage and chat views |
| `tests/` | Contract pins, unit/integration suites, V10 external-client proof |
| `Docs/contracts/` | 21 frozen implementation contracts (the source of truth) |
| `Docs/roadmaps/` | Per-owner roadmaps, merge/integration plan, shared fixtures |
| `verity.toml` | Runtime configuration (contract 14) |
| `demo-workspace/` | Sample workspace the coverage engine scans |
| `documents/` | Default source root for your specs / docs (gitignored) |

## Prerequisites

- **Python 3.12** (tested; 3.11+ likely works) — on Windows, prefer the explicit interpreter path
- **Node.js 18+** — only needed for the native SDK chat bridge
- No network required: retrieval degrades honestly to `lexical_only` when no local embedding model is available

## Quickstart

```bash
# 1. install (editable, with MCP + HTTP extras)
python -m pip install -e ".[dev,mcp,http]"

# 2. sanity check — full contract + integration suite
python -m pytest tests/ -q        # 452 passed

# 3. seed the demo (idempotent): demo-workspace code + payments spec
python tests/v10/seed_demo.py

# 4. ingest your own documents (any markdown spec or general doc)
python - <<'PY'
import asyncio
from pathlib import Path
from verity.models import IngestMode, IngestRequest
from verity.service import build_service

service = build_service()
data = Path("my-spec.md").read_bytes()
print(asyncio.run(service.ingest(IngestRequest(source_path="my-spec.md", mode=IngestMode.AUTO), data)))
PY
```

Ingestion is content-addressed: re-ingesting unchanged bytes is a no-op; changed bytes create a
new immutable document version (history and rollback included). Specs follow the frontmatter +
`# Requirements / REQ-xxx` format of `Docs/contracts/04` — see
`tests/fixtures/contracts_v1/payments.md` for a complete example.

## MCP setup (external Cline clients)

The server speaks **stdio**: `python -m verity.mcp`. It reads configuration from
`VERITY_CONFIG_PATH` (default `./verity.toml`) and refuses to start on a fake service
(exit code 2) if the real `VerityService` is unavailable.

**Cline Desktop** — edit `~/.cline/data/settings/cline_mcp_settings.json`
**(or)** **Cline for VS Code** — edit
`%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "verity": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      "args": ["-m", "verity.mcp"],
      "cwd": "C:\\<path>\\to\\VARITY",
      "env": {
        "VERITY_CONFIG_PATH": "C:\\<path>\\to\\VARITY\\verity.toml",
        "PYTHONPATH": "C:\\<path>\\to\\VARITY"
      },
      "autoApprove": ["search_evidence", "get_requirement", "get_evidence", "check_coverage"],
      "disabled": false
    }
  }
}
```

Use the **explicit interpreter path** (a bare `python` may resolve to another program on PATH),
point `cwd` at this checkout, then reload Cline. The four tools and their contract-09 deadlines:

| Tool | Purpose | Deadline |
|---|---|---|
| `search_evidence` | Hybrid/lexical search with cited `Evidence` items | 15 s |
| `get_requirement` | Canonical `Requirement` incl. its evidence ID | 5 s |
| `get_evidence` | Evidence + provenance + surrounding context | 5 s |
| `check_coverage` | Evidence-backed implementation coverage run | 30 s |

Verify the connection headlessly (spawns the server exactly as Cline does):

```bash
python - <<'PY'
import asyncio, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    p = StdioServerParameters(command=sys.executable, args=["-m", "verity.mcp"],
                              cwd=".", env={"VERITY_CONFIG_PATH": "verity.toml"})
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as c:
            print(await c.initialize())
            print([t.name for t in (await c.list_tools()).tools])
            d = (await c.call_tool("search_evidence", {"query": "refund window"})).structured_content
            print(d["items"][0]["citation"]["label"])

asyncio.run(main())
PY
```

The full scripted external-client proof (all four tools + restart proof) is a test:

```bash
python -m pytest tests/test_v10_external_client.py -q -s
```

## HTTP API (loopback, contract 11)

```bash
python -c "from verity.service import build_service; from verity.http.app import serve; serve(build_service())"
# → uvicorn on 127.0.0.1:8765 per verity.toml (api_host / api_port)
```

| Route | Method | Purpose |
|---|---|---|
| `/api/v1/health` | GET | Health incl. `retrieval_mode` and `sdk_available` |
| `/api/v1/documents` | GET / POST | List documents / ingest (`{"source_path":…, "mode":…}` + body bytes) |
| `/api/v1/documents/{id}` | GET | One document (active version) |
| `/api/v1/sources` | GET | List sources |
| `/api/v1/search` | POST | `SearchRequest` → cited `SearchResult` |
| `/api/v1/requirements/{id}` | GET | Canonical requirement + evidence ID |
| `/api/v1/evidence/{id}` | GET | Evidence, provenance, context |
| `/api/v1/coverage` | POST | Run coverage (`requirement_ids`, `workspace_id`, `run_tests`) |
| `/api/v1/coverage/{id}` | GET | Immutable persisted coverage report |
| `/api/v1/chat/sessions` | POST | Native SDK chat session (SDK gateway required) |
| `/api/v1/chat/sessions/{id}/messages` | POST | Chat message → `ChatResponse` with resolved evidence |

All responses are the frozen contract-21 JSON schemas; errors are the canonical `HttpError`
body with typed contract-17 codes.

## Web UI (`sdk-ui/frontend`)

A dependency-free static frontend. Open `sdk-ui/frontend/index.html` in a browser:

- **Mock mode (default)**: typed in-memory fixtures — works fully offline, no backend
- **Real mode**: append `?api=real` — views call the live `/api/v1` API at
  `http://127.0.0.1:8765/api/v1` (start the HTTP server above first)

Views: documents/sources browser, upload/ingest, search with evidence cards, coverage
dashboard, and native chat. Real-mode chat additionally requires the SDK gateway wired into
the app (`create_app(service, gateway=SdkChatGateway(service))`) and the Node bridge below —
otherwise the API answers honestly with `SDK_UNAVAILABLE`.

## Native SDK chat bridge (contract 10)

```bash
cd sdk-ui/gateway/node_bridge
npm install            # pinned @cline/sdk 0.0.90
```

The Python `ClineSdkRuntime` spawns this bridge (`node agent.mjs`); the bridge calls the
Python `VerityService` **only** through the loopback HTTP API (`VERITY_API_BASE`, default
`http://127.0.0.1:8765`). If the SDK or Node is unavailable the gateway raises
`SDK_UNAVAILABLE` — it never substitutes a fake agent or a canned answer.

## Coverage: is it actually implemented?

`check_coverage` scans a configured workspace and reports evidence-backed verdicts per
requirement (contract 12). Statuses are derived **only** from inspectable spans:

| Status | Meaning |
|---|---|
| `IMPLEMENTED` | Credible implementation + non-failing (or executed-passing) test evidence |
| `PARTIAL` | Credible implementation without test support, or a relevant test failed |
| `MISSING` | Scan completed; only comment matches name the requirement |
| `UNCERTAIN` | No analyzable evidence, workspace changed, or requested tests didn't pass — honest uncertainty, never invented coverage |

Safety rules: only the scanner reads workspace files (`read_lines`: manifest-member paths only,
200-line / 8,000-char caps, SHA-256 verified against the snapshot); tests run **only** the
allowlisted `test_command` from config with a 20 s timeout; every coverage report is an
immutable persisted row.

**Practical tip:** reference the requirement ID on the definition line of your code/tests
(`def accept_refund(purchase, now):  # REQ-001`) — mentions in docstrings/comments alone are
deliberately not counted as implementation evidence.

## Configuration (`verity.toml`)

```toml
config_version = "1.0.0"
data_dir       = "./data"                  # knowledge store location
source_root    = "./documents"            # default document source root
database_path  = "./data/verity.sqlite3"
embedding_model = "BAAI/bge-m3@pinned-local-revision"   # optional; lexical fallback is honest
reranker_enabled = true
api_host = "127.0.0.1"                    # loopback only
api_port = 8765
mcp_transport = "stdio"

[workspaces.demo]                          # coverage targets
root = "./demo-workspace"
test_command = ["python", "-m", "pytest", "-v"]   # the ONLY command run_tests may execute
exclude = [".git", ".venv", "node_modules", "dist"]
```

The file is read from `VERITY_CONFIG_PATH` (default `./verity.toml`); relative paths resolve
against the config file's directory. Set `test_command` to your interpreter explicitly and
keep `-v`-style output so passing tests can be mapped to files.

## Testing

```bash
python -m pytest tests/ -q                          # full suite (452 tests)
python -m pytest tests/test_v10_external_client.py -q -s   # scripted external MCP proof
```

The suite includes contract pins (frozen signatures against `Docs/contracts/16`), JSON-schema
validation against the live contract-21 `$defs`, storage migration/rollback/restart tests,
MCP/HTTP parity over one real service, and the automated external-client trace.

## Documentation

- `Docs/contracts/01_VERITY_CONTRACT_INDEX.md` — index of the 21 frozen contracts
  (data schemas, retrieval, evidence, MCP, API v1, coverage, database, errors, JSON schemas …)
- `Docs/contracts/02_VERITY_VERSIONING_POLICY.md` — amendment/change-log policy
- `Docs/roadmaps/` — per-owner roadmaps, module ownership matrix, merge/integration plan
- `tests/v10/runbook.md` — external-Cline demo runbook (scripted trace + recorded session)
- `Docs/ARCHITECTURE.md` — architecture and implementation specification

## Known limitations (honest by design)

- Search reports `retrieval_mode: lexical_only` until a local embedding model is configured —
  never presented as hybrid
- Native chat requires the Node bridge + running loopback API; otherwise `SDK_UNAVAILABLE`
- Coverage is bounded (file caps, per-requirement span caps, 30 s deadline) and never guesses
- A no-match search is a successful empty `SearchResult`, not an error; unknown IDs are typed
  `*_NOT_FOUND` errors, never hallucinated content

## Team

Built for the Cline hackathon by **Atharv Patil** (core, storage, evidence, service, SDK
gateway), **Piyush Ghayal** (ingestion, retrieval), **Vandit Gupta** (MCP + HTTP transports),
and **Vanashree** (coverage engine, web UI). Implementation follows the frozen contract
package in `Docs/contracts/` — see `Docs/contracts/19_VERITY_TEAM_OWNERSHIP.md`.


