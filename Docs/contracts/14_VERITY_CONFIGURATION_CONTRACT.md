# Configuration contract 1.0.0

**Owner:** Atharv. **Consumers:** all owners. One `verity.toml` is authoritative; environment variables override named scalar fields only. Missing config uses defaults below. Secrets are env-only. At startup, config parser rejects unknown keys and invalid values with `CONFIG_INVALID`. All model files must be pre-provisioned for offline use; serving does not download them.

```toml
config_version = "1.0.0"
data_dir = "./data"
source_root = "./documents"
database_path = "./data/verity.sqlite3"
embedding_model = "BAAI/bge-m3@pinned-local-revision"
reranker_model = "BAAI/bge-reranker-v2-m3@pinned-local-revision"
embedding_required = false
reranker_enabled = true
search_limit_default = 8
search_limit_max = 20
lexical_candidates = 50
semantic_candidates = 50
rerank_candidates = 30
api_host = "127.0.0.1"
api_port = 8765
mcp_transport = "stdio"
log_level = "INFO"

[workspaces.demo]
root = "./demo-workspace"
test_command = ["python", "-m", "pytest", "-q"]
exclude = [".git", ".venv", "node_modules", "dist"]
```

Relative paths resolve against the config file directory, then are canonicalized. `source_root` is the allowlisted ingestion root; API uploads are copied into it under a safe generated name before registration. Workspace `root` must resolve to an existing directory; workspace IDs match `^[a-z][a-z0-9_-]{0,31}$`. `test_command` is an argument array, never shell text; absent means `run_tests=true` returns `COVERAGE_UNAVAILABLE`. Non-loopback `api_host` requires an explicit future security contract and is invalid in v1. `mcp_transport` accepts only `stdio` in v1. Candidate limits are positive, capped as in `06`, and `rerank_candidates <= lexical_candidates+semantic_candidates`. `embedding_required=false` allows lexical fallback; `true` fails startup if model unavailable.

| Environment variable | Type / required / default | Overrides / purpose |
|---|---|---|
| `VERITY_CONFIG_PATH` | path / no / `./verity.toml` | Select config file |
| `VERITY_DATA_DIR` | path / no / config value | `data_dir` |
| `VERITY_SOURCE_ROOT` | path / no / config value | `source_root` |
| `VERITY_DB_PATH` | path / no / config value | `database_path` |
| `VERITY_EMBEDDING_MODEL` | model ID string / no / config value | `embedding_model` |
| `VERITY_RERANKER_MODEL` | model ID string / no / config value | `reranker_model` |
| `VERITY_RERANKER_ENABLED` | boolean `true|false` / no / config value | `reranker_enabled` |
| `VERITY_API_HOST` | literal `127.0.0.1` / no / config value | `api_host` |
| `VERITY_API_PORT` | integer 1–65535 / no / config value | `api_port` |
| `VERITY_LOG_LEVEL` | `DEBUG|INFO|WARNING|ERROR` / no / config value | `log_level` |
| `VERITY_CLINE_PROVIDER_ID` | string / only if SDK enabled / none | SDK provider |
| `VERITY_CLINE_MODEL_ID` | string / only if SDK enabled / none | SDK model |
| `VERITY_CLINE_API_KEY` | secret string / provider-dependent / none | SDK credential, never logged |

There are no other v1 environment overrides. Workspace roots and test commands must be edited in `verity.toml`, not invented as dynamic env names. Config parsing and defaults are owned by `verity/config.py`; modules receive a frozen `VerityConfig` object, never read `os.environ` independently. The SDK gateway receives its provider settings from that config. Model revision placeholders in the sample must be replaced by locally available pinned IDs before the offline event; the identifier string is configuration, not a public model guarantee.
