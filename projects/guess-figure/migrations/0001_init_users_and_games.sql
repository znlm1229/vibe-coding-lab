-- 002-account-rate-limit T1: 初始化 users 与 games 表
--
-- 与 SPEC v1.0 [04-spec.md] C5 schema 兼容性约束对齐:
--   - users 必须含 nullable email TEXT UNIQUE 与 merged_from_user_id（即使 002 不使用）
--   - 这两字段为 003 邮箱迁移 / merge 流程预留，002 阶段为 NULL
--
-- D1 是 SQLite-compatible, 用 SQLite 语法。

-- ====================================================================
-- users 表
-- ====================================================================
CREATE TABLE IF NOT EXISTS users (
  id                  TEXT PRIMARY KEY,                            -- UUID v4 字符串 (cookie 中的 uuid 部分)
  email               TEXT UNIQUE,                                 -- 003 邮箱迁移用; 002 时一律 NULL
  merged_from_user_id TEXT,                                        -- 003 merge 流程用; 002 时一律 NULL
  created_at          TEXT NOT NULL DEFAULT (datetime('now'))      -- ISO 8601 UTC
);

-- ====================================================================
-- games 表
-- ====================================================================
CREATE TABLE IF NOT EXISTS games (
  id              TEXT PRIMARY KEY,                                -- client crypto.randomUUID() 生成 (幂等所需, SPEC OQ5)
  user_id         TEXT NOT NULL,
  figure_id       TEXT NOT NULL,                                   -- 与 src/lib/data/figures.json 的 id 字段对齐 (e.g. "乾隆")
  won             INTEGER NOT NULL,                                -- 0 / 1
  revealed_count  INTEGER NOT NULL,                                -- 1-7
  score           INTEGER NOT NULL,
  given_up        INTEGER NOT NULL DEFAULT 0,                      -- 0 / 1
  played_at       TEXT NOT NULL DEFAULT (datetime('now')),         -- ISO 8601 UTC
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- INDEX 用于 /api/me 的 "ORDER BY played_at DESC LIMIT 5" 高效查询
CREATE INDEX IF NOT EXISTS idx_games_user_played
  ON games(user_id, played_at DESC);
