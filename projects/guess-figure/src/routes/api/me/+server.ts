// 002 T12: /api/me — user 战绩汇总
//
// SPEC v1.0 B4:
//   - GET 返 {user_id, total_games, total_wins, total_score_30d, recent_games[5]}
//   - Cache-Control: private, max-age=10
//
// 鉴权: 由 hooks.server.ts 在 /api/* 前置, locals.user_id 已挂.
// 新用户首次访问该 endpoint, hook 已 INSERT users 表; games 表查询返 0.

import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";

export interface GameRow {
  id: string;
  figure_id: string;
  won: number;
  revealed_count: number;
  score: number;
  given_up: number;
  played_at: string;
}

export interface MeResponse {
  user_id: string;
  total_games: number;
  total_wins: number;
  total_score_30d: number;
  recent_games: GameRow[];
}

export const GET: RequestHandler = async ({ locals, platform }) => {
  const userId = locals.user_id;
  const cfEnv = platform?.env;

  // vite dev fallback: cfEnv 或 D1 缺失时返空战绩 (允许本地开发不挂)
  if (!cfEnv?.GF_DB) {
    const stub: MeResponse = {
      user_id: userId,
      total_games: 0,
      total_wins: 0,
      total_score_30d: 0,
      recent_games: [],
    };
    return json(stub, {
      headers: { "Cache-Control": "private, max-age=10" },
    });
  }

  const db = cfEnv.GF_DB;

  // 用 batch 一次性发两个 query (D1 batch 比串行快一点)
  const [summaryRes, recentRes] = await db.batch([
    db
      .prepare(
        `SELECT
           COUNT(*) AS total_games,
           COALESCE(SUM(won), 0) AS total_wins,
           COALESCE(SUM(CASE WHEN played_at > datetime('now', '-30 days') THEN score ELSE 0 END), 0) AS total_score_30d
         FROM games
         WHERE user_id = ?`,
      )
      .bind(userId),
    db
      .prepare(
        `SELECT id, figure_id, won, revealed_count, score, given_up, played_at
         FROM games
         WHERE user_id = ?
         ORDER BY played_at DESC
         LIMIT 5`,
      )
      .bind(userId),
  ]);

  const summary = (summaryRes.results?.[0] ?? {}) as {
    total_games?: number;
    total_wins?: number;
    total_score_30d?: number;
  };
  const recent = (recentRes.results ?? []) as GameRow[];

  const response: MeResponse = {
    user_id: userId,
    total_games: summary.total_games ?? 0,
    total_wins: summary.total_wins ?? 0,
    total_score_30d: summary.total_score_30d ?? 0,
    recent_games: recent,
  };

  return json(response, {
    headers: { "Cache-Control": "private, max-age=10" },
  });
};
