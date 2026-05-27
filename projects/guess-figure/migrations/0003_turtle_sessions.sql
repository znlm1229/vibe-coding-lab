-- 004 T7: 海龟汤会话、答案次数与嵌入式使用状态
-- D1 仅保存轻量状态；RAG 证据和语料正文不进入本表。

CREATE TABLE IF NOT EXISTS turtle_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  game_id TEXT,
  figure_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  question_count INTEGER NOT NULL DEFAULT 0,
  answer_attempts_used INTEGER NOT NULL DEFAULT 0,
  completed INTEGER NOT NULL DEFAULT 0,
  won INTEGER,
  used_turtle INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CHECK (mode IN ('embedded', 'standalone')),
  CHECK (question_count >= 0),
  CHECK (answer_attempts_used >= 0 AND answer_attempts_used <= 3),
  CHECK (completed IN (0, 1)),
  CHECK (won IS NULL OR won IN (0, 1)),
  CHECK (used_turtle IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_turtle_sessions_user_game
  ON turtle_sessions(user_id, game_id, mode);

CREATE INDEX IF NOT EXISTS idx_turtle_sessions_user_updated
  ON turtle_sessions(user_id, updated_at DESC);
