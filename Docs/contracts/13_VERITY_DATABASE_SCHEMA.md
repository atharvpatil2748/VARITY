# SQLite database schema v1

**Owner:** Atharv. **Consumers:** Piyush through `KnowledgeStore`; Vanashree through coverage repository; no other direct SQL users. `PRAGMA user_version=1`, `foreign_keys=ON`, WAL for local reads. Persistence is the only schema/SQL owner. All timestamps are UTC RFC 3339 text. UUIDs are lowercase TEXT. `*_json` columns contain canonical JSON with sorted keys and `metadata_version` when metadata. `original_relpath` is relative to VERITY data directory. The following logical DDL is authoritative; exact trigger syntax may be adjusted to SQLite version without changing tables/columns.

```sql
CREATE TABLE sources (
  source_id TEXT PRIMARY KEY, source_key TEXT, source_path TEXT NOT NULL,
  registered_at TEXT NOT NULL, schema_version TEXT NOT NULL
);
CREATE TABLE documents (
  document_id TEXT PRIMARY KEY, source_id TEXT NOT NULL UNIQUE REFERENCES sources(source_id),
  name TEXT NOT NULL, media_type TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('spec','general')),
  status TEXT NOT NULL CHECK(status IN ('pending','ready','partial','failed')),
  active_version_id TEXT, indexed_at TEXT, schema_version TEXT NOT NULL
);
CREATE TABLE document_versions (
  version_id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(document_id),
  content_sha256 TEXT NOT NULL, metadata_json TEXT NOT NULL,
  original_relpath TEXT NOT NULL, created_at TEXT NOT NULL, indexed_at TEXT,
  chunker_version TEXT NOT NULL, embedding_model TEXT,
  status TEXT NOT NULL CHECK(status IN ('pending','ready','partial','failed')),
  schema_version TEXT NOT NULL, UNIQUE(document_id, content_sha256)
);
CREATE TABLE blocks (
  block_id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_versions(version_id),
  ordinal INTEGER NOT NULL, text TEXT NOT NULL, block_type TEXT NOT NULL,
  page INTEGER, heading_path_json TEXT NOT NULL,
  start_line INTEGER, end_line INTEGER, start_offset INTEGER, end_offset INTEGER,
  schema_version TEXT NOT NULL, UNIQUE(version_id, ordinal)
);
CREATE TABLE chunks (
  chunk_id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_versions(version_id),
  kind TEXT NOT NULL, text TEXT NOT NULL, heading_text TEXT NOT NULL,
  locator_json TEXT NOT NULL, block_start INTEGER NOT NULL, block_end INTEGER NOT NULL,
  ordinal INTEGER NOT NULL, requirement_id TEXT, schema_version TEXT NOT NULL,
  UNIQUE(version_id, ordinal)
);
CREATE TABLE requirements (
  version_id TEXT NOT NULL REFERENCES document_versions(version_id),
  requirement_id TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(source_id),
  document_id TEXT NOT NULL REFERENCES documents(document_id), local_id TEXT NOT NULL,
  title TEXT NOT NULL, text TEXT NOT NULL, constraints_json TEXT NOT NULL,
  edge_cases_json TEXT NOT NULL, api_refs_json TEXT NOT NULL,
  reference_ids_json TEXT NOT NULL, chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id),
  locator_json TEXT NOT NULL, schema_version TEXT NOT NULL,
  PRIMARY KEY(version_id, requirement_id), UNIQUE(version_id, local_id)
);
CREATE TABLE spec_entities (
  version_id TEXT NOT NULL REFERENCES document_versions(version_id),
  local_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('api_definition','acceptance_criterion')),
  title TEXT NOT NULL, text TEXT NOT NULL, reference_ids_json TEXT NOT NULL,
  chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id),
  locator_json TEXT NOT NULL, schema_version TEXT NOT NULL,
  PRIMARY KEY(version_id, local_id)
);
CREATE TABLE requirement_acceptance (
  version_id TEXT NOT NULL, requirement_id TEXT NOT NULL, ac_local_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  PRIMARY KEY(version_id, requirement_id, ac_local_id),
  FOREIGN KEY(version_id, requirement_id) REFERENCES requirements(version_id, requirement_id),
  FOREIGN KEY(version_id, ac_local_id) REFERENCES spec_entities(version_id, local_id)
);
CREATE TABLE embeddings (
  chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id), model_id TEXT NOT NULL,
  dimension INTEGER NOT NULL, vector_f32le BLOB NOT NULL,
  text_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(chunk_id, model_id)
);
CREATE TABLE evidence_refs (
  evidence_id TEXT PRIMARY KEY,
  version_id TEXT NOT NULL REFERENCES document_versions(version_id),
  chunk_id TEXT NOT NULL UNIQUE REFERENCES chunks(chunk_id)
);
CREATE TABLE coverage_runs (
  coverage_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
  workspace_revision TEXT NOT NULL, inspected_at TEXT NOT NULL,
  report_json TEXT NOT NULL, schema_version TEXT NOT NULL
);
CREATE VIRTUAL TABLE fts_chunks USING fts5(text, heading_text, content='chunks', content_rowid='rowid');
CREATE INDEX ix_versions_document ON document_versions(document_id, created_at);
CREATE INDEX ix_blocks_version ON blocks(version_id, ordinal);
CREATE INDEX ix_chunks_version_kind ON chunks(version_id, kind);
CREATE INDEX ix_requirements_source_local ON requirements(source_id, local_id);
CREATE INDEX ix_coverage_workspace_time ON coverage_runs(workspace_id, inspected_at);
```

FTS5 insert/update/delete triggers maintain `fts_chunks` transactionally from `chunks.rowid`; implementation must test rebuild and delete. `documents.active_version_id` is set only after a version and all canonical rows commit; application verifies it belongs to the same document. (A cross-table CHECK cannot express this.) `requirement_id` on chunks is validated against a requirement in the same version after insert; no cross-version links. `Requirement.acceptance_criteria` is reconstructed through `requirement_acceptance` and `spec_entities`. `Document.metadata` comes from its active `document_versions.metadata_json`; no competing metadata copy in `documents`. `Document.content_sha256` is the active version hash. `Source` and `Document` are one-to-one in v1.

`evidence_refs` makes opaque evidence IDs directly resolvable without scanning hashes. It is populated in the same transaction as chunks. `document_versions.indexed_at`, `chunker_version` and `embedding_model` preserve historical provenance even after a newer version becomes active. V1 retains old versions and evidence references; any future retention migration must leave a tombstone mapping so `EVIDENCE_GONE` remains distinguishable from a never-known ID.

Embedding vector BLOB is little-endian IEEE-754 float32, normalized, length `dimension*4`; model ID includes revision. Semantic scan may load rows into memory but must filter active versions and allowed document IDs. No Qdrant/SurrealDB. Old version rows remain to resolve citations. SQLite transaction handles canonical rows and FTS; embedding generation may run later and set version/document status `partial` until ready. Source file bytes live at `data/originals/<sha256>` and are written atomically before DB activation. Failure rolls back DB activation and leaves old active version usable.

Migration file `0001_initial.sql` creates exactly this v1 schema and sets `user_version=1`. Later migrations are numbered, transactional, backed up and forward-only. Unknown greater `user_version` raises `VERSION_UNSUPPORTED`. No module besides `verity/storage` adds tables or migrations.
