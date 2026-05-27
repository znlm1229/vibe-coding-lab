import { describe, expect, it } from "vitest";
import type { Figure } from "$lib/types";
import type { TurtleSessionRecord } from "$lib/server/turtle-session";
import { _createTurtleSessionHandler } from "./+server";

const figure: Figure = {
  id: "target",
  name: "目标人物",
  aliases: ["目标别名"],
  clues: [{ text: "普通线索", difficulty: 1 }],
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
  it("由服务端生成 session_id，并且响应只包含公开 round 字段", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createTurtleSessionHandler({
      figures: [figure],
      intros: { [figure.name]: "半盏微光" },
      createSessionId: () => "123e4567-e89b-42d3-a456-426614174000",
      random: () => 0,
    });

    const response = await handler(
      mockEvent(
        {
          mode: "standalone",
          session_id: "client-controlled",
          figure_id: "target",
        },
        db,
      ),
    );
    const body = await response.json();
    const serialized = JSON.stringify(body);

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      session_id: "123e4567-e89b-42d3-a456-426614174000",
      turtle_intro: "半盏微光",
      question_count: 0,
      answer_attempts_used: 0,
      status: "playing",
      questions: [],
    });
    expect(body.session_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
    expect(body.session_id).not.toBe("client-controlled");
    expect(body).not.toHaveProperty("figure_id");
    expect(body).not.toHaveProperty("name");
    expect(body).not.toHaveProperty("aliases");
    expect(body).not.toHaveProperty("clues");
    expect(body).not.toHaveProperty("wiki_url");
    expect(serialized).not.toContain("target");
    expect(serialized).not.toContain(figure.name);
    expect(serialized).not.toContain("目标别名");
    expect(serialized).not.toContain("普通线索");
    expect(serialized).not.toContain("wiki_url");
    expect(db._sessions.get("123e4567-e89b-42d3-a456-426614174000")).toMatchObject({
      user_id: "user-1",
      figure_id: "target",
      mode: "standalone",
      used_turtle: true,
    });
    expect(db._sessions.has("client-controlled")).toBe(false);
  });

  it("非对象 JSON、未知 mode 和 embedded mode 返回 400，且不创建会话", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createTurtleSessionHandler({
      figures: [figure],
      createSessionId: () => "123e4567-e89b-42d3-a456-426614174000",
    });

    await expect(handler(mockEvent(null, db))).rejects.toMatchObject({ status: 400 });
    await expect(handler(mockEvent({ mode: "arcade" }, db))).rejects.toMatchObject({
      status: 400,
    });
    await expect(handler(mockEvent({ mode: "embedded" }, db))).rejects.toMatchObject({
      status: 400,
    });

    expect(db._sessions.size).toBe(0);
  });

  it("服务端生成的 session_id 已被其他用户占用时返回 409", async () => {
    const db = createMemoryTurtleDb();
    db._sessions.set("123e4567-e89b-42d3-a456-426614174000", {
      id: "123e4567-e89b-42d3-a456-426614174000",
      user_id: "other-user",
      game_id: null,
      figure_id: "target",
      mode: "standalone",
      question_count: 0,
      answer_attempts_used: 0,
      completed: false,
      won: null,
      used_turtle: true,
    });
    const handler = _createTurtleSessionHandler({
      figures: [figure],
      createSessionId: () => "123e4567-e89b-42d3-a456-426614174000",
    });

    await expect(handler(mockEvent({ mode: "standalone" }, db))).rejects.toMatchObject({
      status: 409,
    });
  });
});
