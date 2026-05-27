import { describe, expect, it } from "vitest";
import { _createGameFinishHandler } from "./+server";
import type { Figure } from "$lib/types";
import { markEmbeddedTurtleUsed, type TurtleSessionRecord } from "$lib/server/turtle-session";

const figure: Figure = {
  id: "zhuge-liang",
  name: "诸葛亮",
  aliases: ["孔明"],
  clues: [],
  source: "test",
  wikidata_id: "Q-test",
  wiki_url: "https://example.test/zhuge-liang",
};

const gameId = "123e4567-e89b-42d3-a456-426614174000";

function createMemoryTurtleDb() {
  const sessions = new Map<string, TurtleSessionRecord>();
  const games = new Map<
    string,
    {
      id: string;
      user_id: string;
      figure_id: string;
      won: number;
      revealed_count: number;
      score: number;
      given_up: number;
    }
  >();

  return {
    _sessions: sessions,
    _games: games,
    prepare(sql: string) {
      return {
        bind(...params: unknown[]) {
          return {
            async first<T>() {
              if (sql.includes("FROM turtle_sessions") && sql.includes("WHERE id = ?")) {
                return (sessions.get(String(params[0])) ?? null) as T | null;
              }
              if (sql.includes("FROM turtle_sessions") && sql.includes("game_id = ?")) {
                for (const session of sessions.values()) {
                  if (
                    session.user_id === params[0] &&
                    session.game_id === params[1] &&
                    session.mode === "embedded" &&
                    session.used_turtle
                  ) {
                    return session as T;
                  }
                }
              }
              if (sql.includes("FROM games") && sql.includes("WHERE id = ?")) {
                return (games.get(String(params[0])) ?? null) as T | null;
              }
              return null;
            },
            async run() {
              let changes = 0;
              if (sql.startsWith("INSERT INTO turtle_sessions")) {
                const [
                  id,
                  user_id,
                  game_id,
                  figure_id,
                  mode,
                  question_count,
                  answer_attempts_used,
                  completed,
                  won,
                  used_turtle,
                ] = params;
                const existing = sessions.get(String(id));
                if (!existing) {
                  sessions.set(String(id), {
                    id: String(id),
                    user_id: String(user_id),
                    game_id: game_id === null ? null : String(game_id),
                    figure_id: String(figure_id),
                    mode: mode as TurtleSessionRecord["mode"],
                    question_count: Number(question_count),
                    answer_attempts_used: Number(answer_attempts_used),
                    completed: Boolean(completed),
                    won: won === null ? null : Boolean(won),
                    used_turtle: Boolean(used_turtle),
                  });
                  changes = 1;
                }
              }
              if (sql.startsWith("INSERT INTO games")) {
                const [id, user_id, figure_id, won, revealed_count, score, given_up] = params;
                if (!games.has(String(id))) {
                  games.set(String(id), {
                    id: String(id),
                    user_id: String(user_id),
                    figure_id: String(figure_id),
                    won: Number(won),
                    revealed_count: Number(revealed_count),
                    score: Number(score),
                    given_up: Number(given_up),
                  });
                  changes = 1;
                }
              }
              if (sql.startsWith("UPDATE games SET score = 0")) {
                const [id, user_id] = params;
                const game = games.get(String(id));
                if (game && game.user_id === user_id && game.score !== 0) {
                  game.score = 0;
                  changes = 1;
                }
              }
              return { success: true, meta: { changes } };
            },
          };
        },
      };
    },
  };
}

function mockEvent(body: unknown, db = createMemoryTurtleDb(), userId = "user-1") {
  return {
    request: new Request("https://test.local/api/game/finish", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "content-type": "application/json" },
    }),
    platform: { env: { GF_DB: db } },
    locals: { user_id: userId },
    getClientAddress: () => "127.0.0.1",
  } as any;
}

function finishBody(score = 80) {
  return {
    game_id: gameId,
    figure_id: "zhuge-liang",
    won: true,
    revealed_count: 6,
    score,
    given_up: false,
  };
}

describe("/api/game/finish", () => {
  it("嵌入式海龟汤使用后，响应 payload 与持久化 games 记录都固定 score=0", async () => {
    const db = createMemoryTurtleDb();
    await markEmbeddedTurtleUsed({
      db,
      userId: "user-1",
      gameId,
      figureId: "zhuge-liang",
    });
    const handler = _createGameFinishHandler({ figures: [figure] });

    const response = await handler(mockEvent(finishBody(), db));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      ok: true,
      game_id: gameId,
      persisted: true,
      score: 0,
      turtle_used: true,
    });
    expect(db._games.get(gameId)?.score).toBe(0);
  });

  it("重复提交返回 DB truth，不返回第二次请求里的新 score", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createGameFinishHandler({ figures: [figure] });

    await handler(mockEvent(finishBody(70), db));
    const response = await handler(mockEvent(finishBody(99), db));
    const body = await response.json();

    expect(body).toMatchObject({
      ok: true,
      score: 70,
      turtle_used: false,
    });
    expect(db._games.get(gameId)?.score).toBe(70);
  });

  it("先非 0 结算后检测到 turtle_used 时，短 UPDATE 强制归零并返回 DB truth", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createGameFinishHandler({ figures: [figure] });

    await handler(mockEvent(finishBody(70), db));
    await markEmbeddedTurtleUsed({
      db,
      userId: "user-1",
      gameId,
      figureId: "zhuge-liang",
    });
    const response = await handler(mockEvent(finishBody(70), db));
    const body = await response.json();

    expect(body).toMatchObject({
      ok: true,
      score: 0,
      turtle_used: true,
    });
    expect(db._games.get(gameId)?.score).toBe(0);
  });

  it("跨用户相同 game_id 返回 409，不静默成功", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createGameFinishHandler({ figures: [figure] });
    await handler(mockEvent(finishBody(70), db, "user-1"));

    await expect(handler(mockEvent(finishBody(70), db, "user-2"))).rejects.toMatchObject({
      status: 409,
      body: { message: "game_id 已属于其他用户" },
    });
  });

  it("revealed_count 小数返回 400", async () => {
    const handler = _createGameFinishHandler({ figures: [figure] });

    await expect(
      handler(mockEvent({ ...finishBody(), revealed_count: 6.5 })),
    ).rejects.toMatchObject({
      status: 400,
      body: { message: "revealed_count 必须是 1-7 的整数" },
    });
  });
});
