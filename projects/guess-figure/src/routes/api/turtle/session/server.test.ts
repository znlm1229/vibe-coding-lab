import { describe, expect, it } from "vitest";
import type { Figure } from "$lib/types";
import type { TurtleSessionRecord } from "$lib/server/turtle-session";
import { _createTurtleSessionHandler } from "./+server";

const figure: Figure = {
  id: "target",
  name: "目标人物",
  aliases: [],
  clues: [],
  source: "test",
  wikidata_id: "Q-test",
  wiki_url: "https://example.test/target",
};

function createMemoryTurtleDb() {
  const sessions = new Map<string, TurtleSessionRecord>();

  return {
    _sessions: sessions,
    prepare(sql: string) {
      return {
        bind(...params: unknown[]) {
          return {
            async first<T>() {
              if (sql.includes("FROM turtle_sessions") && sql.includes("WHERE id = ?")) {
                return (sessions.get(String(params[0])) ?? null) as T | null;
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
                } else if (
                  existing.user_id === user_id &&
                  existing.game_id === (game_id === null ? null : String(game_id)) &&
                  existing.figure_id === figure_id &&
                  existing.mode === mode
                ) {
                  existing.question_count = Math.max(existing.question_count, Number(question_count));
                  existing.used_turtle = existing.used_turtle || Boolean(used_turtle);
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

function mockEvent(body: unknown, db = createMemoryTurtleDb()) {
  return {
    request: new Request("https://test.local/api/turtle/session", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "content-type": "application/json" },
    }),
    platform: { env: { GF_DB: db } },
    locals: { user_id: "user-1" },
    getClientAddress: () => "127.0.0.1",
  } as any;
}

describe("/api/turtle/session", () => {
  it("为 standalone 页面创建 T7 答案接口所需 session", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createTurtleSessionHandler({ figures: [figure] });

    const response = await handler(
      mockEvent(
        {
          mode: "standalone",
          session_id: "session-1",
          figure_id: "target",
        },
        db,
      ),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      mode: "standalone",
      session_id: "session-1",
      figure_id: "target",
      question_count: 0,
      answer_attempts_used: 0,
    });
    expect(db._sessions.get("session-1")).toMatchObject({
      user_id: "user-1",
      figure_id: "target",
      mode: "standalone",
      used_turtle: true,
    });
  });
});
