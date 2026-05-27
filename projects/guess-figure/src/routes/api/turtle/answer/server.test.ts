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
              if (sql.startsWith("UPDATE turtle_sessions")) {
                const [
                  question_count,
                  correct,
                  max_attempts,
                  _correct_for_won,
                  _max_attempts_for_won,
                  id,
                  user_id,
                  figure_id,
                ] = params;
                const session = sessions.get(String(id));
                if (
                  session &&
                  session.user_id === user_id &&
                  session.figure_id === figure_id &&
                  session.mode === "standalone" &&
                  !session.completed &&
                  session.answer_attempts_used < Number(max_attempts)
                ) {
                  const nextAttempts = session.answer_attempts_used + 1;
                  session.question_count = Math.max(session.question_count, Number(question_count));
                  session.answer_attempts_used = nextAttempts;
                  session.completed = Boolean(correct) || nextAttempts >= Number(max_attempts);
                  session.won = Boolean(correct) ? true : session.completed ? false : null;
                  session.used_turtle = true;
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

function seedStandalone(db: ReturnType<typeof createMemoryTurtleDb>, sessionId: string) {
  db._sessions.set(sessionId, {
    id: sessionId,
    user_id: "user-1",
    game_id: null,
    figure_id: "zhuge-liang",
    mode: "standalone",
    question_count: 6,
    answer_attempts_used: 0,
    completed: false,
    won: null,
    used_turtle: true,
  });
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
  it("standalone 只需 session_id 与 answer，完成后才返回 reveal", async () => {
    const db = createMemoryTurtleDb();
    seedStandalone(db, "session-reveal");
    const handler = _createTurtleAnswerHandler({ figures: [figure] });

    const response = await handler(
      mockEvent(
        {
          mode: "standalone",
          session_id: "session-reveal",
          answer: "孔明",
          question_count: 6,
        },
        db,
      ),
    );
    const body = await readJson(response);

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      correct: true,
      completed: true,
      won: true,
      reveal: {
        target_name: figure.name,
        target_aliases: figure.aliases,
        target_wiki_url: figure.wiki_url,
      },
    });
    expect(JSON.stringify(body)).not.toContain("figure_id");
    expect(JSON.stringify(body)).not.toContain("clues");
  });

  it("standalone 未完成时不揭晓 target", async () => {
    const db = createMemoryTurtleDb();
    seedStandalone(db, "session-hidden");
    const handler = _createTurtleAnswerHandler({ figures: [figure] });

    const body = await readJson(
      await handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "session-hidden",
            answer: "曹操",
            question_count: 6,
          },
          db,
        ),
      ),
    );

    expect(body.completed).toBe(false);
    expect(body).not.toHaveProperty("reveal");
    expect(JSON.stringify(body)).not.toContain(figure.name);
    expect(JSON.stringify(body)).not.toContain("孔明");
  });
  it("非法 JSON 对象返回 400", async () => {
    const handler = _createTurtleAnswerHandler({ figures: [figure] });

    await expect(handler(mockEvent(null))).rejects.toMatchObject({
      status: 400,
      body: { message: "请求体必须是 JSON 对象" },
    });
  });

  it("未知独立 session 返回 400，不隐式创建记录", async () => {
    const db = createMemoryTurtleDb();
    const handler = _createTurtleAnswerHandler({ figures: [figure] });

    await expect(
      handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "missing-session",
            figure_id: "zhuge-liang",
            answer: "曹操",
            question_count: 6,
          },
          db,
        ),
      ),
    ).rejects.toMatchObject({
      status: 400,
      body: { message: "海龟汤会话不存在" },
    });
    expect(db._sessions.has("missing-session")).toBe(false);
  });

  it("独立模式 3 次错答后完成失败，且 question_count 不减少", async () => {
    const db = createMemoryTurtleDb();
    seedStandalone(db, "session-1");
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
    seedStandalone(db, "session-2");
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

  it("嵌入式模式 game_id 非 UUID 返回 400", async () => {
    const handler = _createTurtleAnswerHandler({ figures: [figure] });

    await expect(
      handler(
        mockEvent({
          mode: "embedded",
          game_id: "not-a-uuid",
          figure_id: "zhuge-liang",
        }),
      ),
    ).rejects.toMatchObject({
      status: 400,
      body: { message: "game_id 必须是 UUID 字符串" },
    });
  });
});
