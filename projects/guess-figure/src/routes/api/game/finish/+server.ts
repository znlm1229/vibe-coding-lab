// 002 T13: /api/game/finish — 游戏结束幂等写战绩
//
// SPEC v1.0 B3:
//   - POST body {game_id, figure_id, won, revealed_count, score, given_up}
//   - 用 INSERT OR IGNORE (game_id 主键去重) 实现幂等 — 同 id 重发返同 game_id
//   - 400: body 字段缺/越界; 401: 无 cookie (hook 没设 locals); 500: D1 异常
//
// 鉴权由 hooks.server.ts 前置; locals.user_id 已挂. 本 endpoint 仅消费.

import { json, error } from "@sveltejs/kit";
import figures from "$lib/data/figures.json";
import type { Figure } from "$lib/types";
import type { RequestHandler } from "./$types";

interface FinishBody {
  game_id?: string;
  figure_id?: string;
  won?: boolean;
  revealed_count?: number;
  score?: number;
  given_up?: boolean;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export const POST: RequestHandler = async ({ request, locals, platform }) => {
  const userId = locals.user_id;
  if (!userId) throw error(401, "未认证 (hook 未挂 user_id)");

  // dev fallback: 没有 platform 时不写数据库, 但返回 ok 让前端逻辑继续
  const cfEnv = platform?.env;

  const body = (await request.json().catch(() => null)) as FinishBody | null;
  if (!body) throw error(400, "body 必须是 JSON");

  const { game_id, figure_id, won, revealed_count, score, given_up } = body;

  // 校验
  if (typeof game_id !== "string" || !UUID_RE.test(game_id)) {
    throw error(400, "game_id 必须是 UUID 字符串");
  }
  if (typeof figure_id !== "string" || !figure_id) {
    throw error(400, "figure_id 必填");
  }
  if (!(figures as Figure[]).some((f) => f.id === figure_id)) {
    throw error(400, `figure_id 不在题库: ${figure_id}`);
  }
  if (typeof won !== "boolean") throw error(400, "won 必须是 boolean");
  if (typeof revealed_count !== "number" || revealed_count < 1 || revealed_count > 7) {
    throw error(400, "revealed_count 必须是 1-7 的数字");
  }
  if (typeof score !== "number" || !Number.isFinite(score)) {
    throw error(400, "score 必须是数字");
  }
  if (typeof given_up !== "boolean") throw error(400, "given_up 必须是 boolean");

  // dev fallback: 不写数据库, 返 ok
  if (!cfEnv?.GF_DB) {
    return json({ ok: true, game_id, persisted: false });
  }

  // INSERT OR IGNORE — 同 game_id 重发不抛
  await cfEnv.GF_DB.prepare(
    `INSERT OR IGNORE INTO games
       (id, user_id, figure_id, won, revealed_count, score, given_up, played_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))`,
  )
    .bind(
      game_id,
      userId,
      figure_id,
      won ? 1 : 0,
      revealed_count,
      Math.round(score),
      given_up ? 1 : 0,
    )
    .run();

  return json({ ok: true, game_id, persisted: true });
};
