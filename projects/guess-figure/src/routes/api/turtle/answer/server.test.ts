import { describe, expect, it } from "vitest";
import { _createTurtleAnswerHandler } from "./+server";
import type { Figure, TurtleAnswerApiResponse } from "$lib/types";
import type { TurtleSessionRecord } from "$lib/server/turtle-session";

const figure: Figure = {
  id: "zhuge-liang",
  name: "诸葛亮",
  aliases: ["孔明", "卧龙"],
  clues: [],
  source: "test",
  wikidata_id: "Q-test",
  wiki_url: "https://example.test/zhuge-liang",
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
                if (!sessions.has(String(id))) {
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
                }
              }
              if (sql.startsWith("UPDATE turtle_sessions")) {
                const [question_count, answer_attempts_used, completed, won, id] = params;
                const session = sessions.get(String(id));
                if (session) {
                  session.question_count = Number(question_count);
                  session.answer_attempts_used = Number(answer_attempts_used);
                  session.completed = Boolean(completed);
                  session.won = won === null ? null : Boolean(won);
                  session.used_turtle = true;
                }
              }
              return { success: true };
            },
          };
        },
      };
    },
  };
}

function mockEvent(body: unknown, db = createMemoryTurtleDb()) {
  return {
    request: new Request("https://test.local/api/turtle/answer", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "content-type": "application/json" },
    }),
    platform: { env: { GF_DB: db } },
    locals: { user_id: "user-1" },
    getClientAddress: () => "127.0.0.1",
  } as any;
}

async function readJson(response: Response): Promise<TurtleAnswerApiResponse> {
  return (await response.json()) as TurtleAnswerApiResponse;
}

describe("/api/turtle/answer", () => {
  it("非法 JSON 对象返回 400", async () => {
    const handler = _createTurtleAnswerHandler({ figures: [figure] });

    await expect(handler(mockEvent(null))).rejects.toMatchObject({
      status: 400,
      body: { message: "请求体必须是 JSON 对象" },
    });
  });

  it("独立模式 3 次错答后完成失败，且 question_count 不减少", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createTurtleAnswerHandler({ figures: [figure] });

    const first = await readJson(
      await handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "session-1",
            figure_id: "zhuge-liang",
            answer: "曹操",
            question_count: 6,
          },
          db,
        ),
      ),
    );
    const second = await readJson(
      await handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "session-1",
            figure_id: "zhuge-liang",
            answer: "刘备",
            question_count: 6,
          },
          db,
        ),
      ),
    );
    const third = await readJson(
      await handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "session-1",
            figure_id: "zhuge-liang",
            answer: "孙权",
            question_count: 6,
          },
          db,
        ),
      ),
    );

    expect(first).toMatchObject({
      correct: false,
      completed: false,
      answer_attempts_remaining: 2,
      question_count: 6,
    });
    expect(second.answer_attempts_remaining).toBe(1);
    expect(third).toMatchObject({
      correct: false,
      completed: true,
      won: false,
      answer_attempts_remaining: 0,
      question_count: 6,
    });
  });

  it("独立模式次数耗尽后再次提交返回 409", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createTurtleAnswerHandler({ figures: [figure] });
    for (const answer of ["曹操", "刘备", "孙权"]) {
      await handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "session-2",
            figure_id: "zhuge-liang",
            answer,
            question_count: 0,
          },
          db,
        ),
      );
    }

    await expect(
      handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "session-2",
            figure_id: "zhuge-liang",
            answer: "诸葛亮",
            question_count: 0,
          },
          db,
        ),
      ),
    ).rejects.toMatchObject({
      status: 409,
      body: { message: "海龟汤会话已完成" },
    });
  });
});
