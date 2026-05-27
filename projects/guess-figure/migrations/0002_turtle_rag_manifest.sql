-- 004 海龟汤 RAG manifest。
-- D1 只保存版本、统计、来源记录和 R2 object key；语料正文由 R2 托管。

CREATE TABLE IF NOT EXISTS turtle_corpus_versions (
  version TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'building',
  r2_prefix TEXT NOT NULL,
  manifest_r2_key TEXT,
  source_count INTEGER NOT NULL DEFAULT 0,
  chunk_count INTEGER NOT NULL DEFAULT 0,
  vector_count INTEGER NOT NULL DEFAULT 0,
  failed_source_count INTEGER NOT NULL DEFAULT 0,
  stats_json TEXT NOT NULL DEFAULT '{}',
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (status IN ('building', 'ready', 'failed', 'retired'))
);

CREATE TABLE IF NOT EXISTS turtle_index_versions (
  index_version TEXT PRIMARY KEY,
  corpus_version TEXT NOT NULL,
  vectorize_index_name TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  vector_dimensions INTEGER NOT NULL DEFAULT 1024,
  vector_metric TEXT NOT NULL DEFAULT 'cosine',
  status TEXT NOT NULL DEFAULT 'building',
  chunk_count INTEGER NOT NULL DEFAULT 0,
  vector_count INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  activated_at TEXT,
  retired_at TEXT,
  FOREIGN KEY (corpus_version) REFERENCES turtle_corpus_versions(version),
  CHECK (vector_dimensions = 1024),
  CHECK (vector_metric = 'cosine'),
  CHECK (status IN ('building', 'active', 'failed', 'retired'))
);

CREATE TABLE IF NOT EXISTS turtle_corpus_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  corpus_version TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  figure_id TEXT,
  title TEXT,
  source_url TEXT,
  source_ref TEXT,
  original_r2_object_key TEXT,
  normalized_r2_object_key TEXT,
  chunk_manifest_r2_key TEXT,
  checksum_sha256 TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  char_count INTEGER NOT NULL DEFAULT 0,
  byte_count INTEGER NOT NULL DEFAULT 0,
  chunk_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (corpus_version) REFERENCES turtle_corpus_versions(version),
  UNIQUE (corpus_version, source_type, source_id),
  CHECK (source_type IN ('profile', 'wikipedia', 'wikisource', 'figure_metadata')),
  CHECK (status IN ('pending', 'processed', 'failed', 'skipped'))
);

CREATE TABLE IF NOT EXISTS turtle_build_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  corpus_version TEXT NOT NULL,
  index_version TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  report_r2_object_key TEXT,
  checkpoint_r2_object_key TEXT,
  source_total INTEGER NOT NULL DEFAULT 0,
  source_processed INTEGER NOT NULL DEFAULT 0,
  source_failed INTEGER NOT NULL DEFAULT 0,
  chunk_count INTEGER NOT NULL DEFAULT 0,
  vector_count INTEGER NOT NULL DEFAULT 0,
  token_estimate INTEGER NOT NULL DEFAULT 0,
  stats_json TEXT NOT NULL DEFAULT '{}',
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT,
  error_message TEXT,
  FOREIGN KEY (corpus_version) REFERENCES turtle_corpus_versions(version),
  FOREIGN KEY (index_version) REFERENCES turtle_index_versions(index_version),
  CHECK (status IN ('running', 'succeeded', 'failed', 'partial'))
);

CREATE INDEX IF NOT EXISTS idx_turtle_index_versions_active
  ON turtle_index_versions(status, activated_at);

CREATE INDEX IF NOT EXISTS idx_turtle_corpus_sources_version_type
  ON turtle_corpus_sources(corpus_version, source_type);

CREATE INDEX IF NOT EXISTS idx_turtle_build_reports_versions
  ON turtle_build_reports(corpus_version, index_version);
