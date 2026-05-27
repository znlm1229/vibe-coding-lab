// 002 T13: /api/game/finish 游戏结束幂等写战绩。
// T7: 若当前局使用过嵌入式海龟汤，结算分数固定为 0。

import { json, error } from "@sveltejs/kit";
import figures from "$lib/data/figures.json";
import type { Figure } from "$lib/types";
import {
  persistFinishedGame,
  TurtleSessionError,
  type TurtleD1Database,
} from "$lib/server/turtle-session";
import type { RequestHandler } from "./$types";

interface FinishBody {
  game_id?: string;
  figure_id?: string;
  won?: boolean;
  revealed_count?: number;
  score?: number;
  given_up?: boolean;
}

type HandlerDeps = {
  figures?: Figure[];
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function _createGameFinishHandler(deps: HandlerDeps = {}): RequestHandler {
  const figureList = deps.figures ?? (figures as Figure[]);

  return async ({ request, locals, platform }) => {
    const userId = locals.user_id;
    if (!userId) throw error(401, "未认证");

    const body = (await request.json().catch(() => null)) as FinishBody | null;
    if (!body || typeof body !== "object" || Array.isArray(body)) {
      throw error(400, "body 必须是 JSON 对象");
    }

    const { game_id, figure_id, won, revealed_count, score, given_up } = body;
    if (typeof game_id !== "string" || !UUID_RE.test(game_id)) {
      throw error(400, "game_id 必须是 UUID 字符串");
    }
    if (typeof figure_id !== "string" || !figure_id) {
      throw error(400, "figure_id 必填");
    }
    if (!figureList.some((f) => f.id === figure_id)) {
      throw error(400, `figure_id 不在题库: ${figure_id}`);
    }
    if (typeof won !== "boolean") throw error(400, "won 必须是 boolean");
    if (
      typeof revealed_count !== "number" ||
      !Number.isInteger(revealed_count) ||
      revealed_count < 1 ||
      revealed_count > 7
    ) {
      throw error(400, "revealed_count 必须是 1-7 的整数");
    }
    if (typeof score !== "number" || !Number.isFinite(score)) {
      throw error(400, "score 必须是数字");
    }
    if (typeof given_up !== "boolean") throw error(400, "given_up 必须是 boolean");

    const db = platform?.env?.GF_DB as TurtleD1Database | undefined;
    if (!db) {
      return json({
        ok: true,
        game_id,
        persisted: false,
        score: Math.round(score),
        turtle_used: false,
      });
    }

    try {
      const result = await persistFinishedGame({
        db,
        gameId: game_id,
        userId,
        figureId: figure_id,
        won,
        revealedCount: revealed_count,
        score,
        givenUp: given_up,
      });

      return json({ ok: true, game_id, ...result });
    } catch (cause) {
      if (cause instanceof TurtleSessionError) {
        if (cause.code === "conflict") throw error(409, cause.message);
        throw error(400, cause.message);
      }
      console.error("写入游戏结算失败", cause);
      throw error(500, "写入游戏结算失败");
    }
  };
}

export const POST: RequestHandler = _createGameFinishHandler();
