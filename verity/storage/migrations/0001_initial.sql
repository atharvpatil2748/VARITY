-- VERITY database schema v1 (Docs/contracts/13_VERITY_DATABASE_SCHEMA.md).
-- Creates exactly the v1 schema and sets PRAGMA user_version=1.
-- Owner: Atharv (verity/storage is the only SQL owner).

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

CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO fts_chunks(rowid, text, heading_text)
  VALUES (new.rowid, new.text, new.heading_text);
END;
CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO fts_chunks(fts_chunks, rowid, text, heading_text)
  VALUES ('delete', old.rowid, old.text, old.heading_text);
END;
CREATE TRIGGER chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO fts_chunks(fts_chunks, rowid, text, heading_text)
  VALUES ('delete', old.rowid, old.text, old.heading_text);
  INSERT INTO fts_chunks(rowid, text, heading_text)
  VALUES (new.rowid, new.text, new.heading_text);
END;

PRAGMA user_version = 1;