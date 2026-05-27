import { describe, expect, it } from "vitest";
import type { Figure, TurtleMode } from "$lib/types";
import {
  createStandaloneTurtleSession,
  getTurtleSession,
  markEmbeddedTurtleUsed,
  persistFinishedGame,
  submitStandaloneTurtleAnswer,
  type TurtleSessionRecord,
} from "./turtle-session";

const figure: Figure = {
  id: "zhuge-liang",
  name: "诸葛亮",
  aliases: ["孔明", "卧龙"],
  clues: [],
  source: "test",
  wikidata_id: "Q-test",
  wiki_url: "https://example.test/zhuge-liang",
};

type StoredGame = {
  id: string;
  user_id: string;
  figure_id: string;
  won: number;
  revealed_count: number;
  score: number;
  given_up: number;
};

function createMemoryTurtleDb() {
  const sessions = new Map<string, TurtleSessionRecord>();
  const games = new Map<string, StoredGame>();

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
                return null;
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
                    mode: mode as TurtleMode,
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
                const [question_count, completed, won, id, user_id, figure_id] = params;
                const session = sessions.get(String(id));
                if (
                  session &&
                  session.user_id === user_id &&
                  session.figure_id === figure_id &&
                  session.mode === "standalone" &&
                  !session.completed &&
                  session.answer_attempts_used < 3
                ) {
                  session.question_count = Math.max(session.question_count, Number(question_count));
                  session.answer_attempts_used += 1;
                  session.completed = Boolean(completed);
                  session.won = won === null ? null : Boolean(won);
                  session.used_turtle = true;
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

describe("turtle-session", () => {
  it("未知独立会话提交答案时返回 not_found，不隐式创建会话", async () => {
    const db = createMemoryTurtleDb();

    await expect(
      submitStandaloneTurtleAnswer({
        db,
        userId: "user-1",
        sessionId: "missing-session",
        figure,
        answer: "曹操",
        questionCount: 4,
      }),
    ).rejects.toMatchObject({ code: "not_found" });
    expect(await getTurtleSession(db, "missing-session")).toBeNull();
  });

  it("独立模式有 3 次答案提交机会，错答只扣答案次数不扣提问次数", async () => {
    const db = createMemoryTurtleDb();
    await createStandaloneTurtleSession({
      db,
      userId: "user-1",
      sessionId: "session-1",
      figureId: "zhuge-liang",
      questionCount: 4,
    });

    const first = await submitStandaloneTurtleAnswer({
      db,
      userId: "user-1",
      sessionId: "session-1",
      figure,
      answer: "曹操",
      questionCount: 4,
    });
    const second = await submitStandaloneTurtleAnswer({
      db,
      userId: "user-1",
      sessionId: "session-1",
      figure,
      answer: "刘备",
      questionCount: 4,
    });
    const third = await submitStandaloneTurtleAnswer({
      db,
      userId: "user-1",
      sessionId: "session-1",
      figure,
      answer: "孙权",
      questionCount: 4,
    });

    expect(first).toMatchObject({
      correct: false,
      completed: false,
      answer_attempts_used: 1,
      answer_attempts_remaining: 2,
      question_count: 4,
    });
    expect(second.answer_attempts_remaining).toBe(1);
    expect(third).toMatchObject({
      correct: false,
      completed: true,
      won: false,
      answer_attempts_used: 3,
      answer_attempts_remaining: 0,
      question_count: 4,
    });

    const stored = await getTurtleSession(db, "session-1");
    expect(stored).toMatchObject({
      question_count: 4,
      answer_attempts_used: 3,
      completed: true,
      won: false,
    });
  });

  it("独立会话冲突时按 owner/figure/mode 拦截，不污染已有记录", async () => {
    const db = createMemoryTurtleDb();
    await createStandaloneTurtleSession({
      db,
      userId: "user-1",
      sessionId: "session-conflict",
      figureId: "zhuge-liang",
      questionCount: 1,
    });

    await expect(
      createStandaloneTurtleSession({
        db,
        userId: "user-2",
        sessionId: "session-conflict",
        figureId: "zhuge-liang",
        questionCount: 9,
      }),
    ).rejects.toMatchObject({ code: "conflict" });
    await markEmbeddedTurtleUsed({
      db,
      userId: "user-1",
      gameId: "game-conflict",
      figureId: "zhuge-liang",
    });
    await expect(
      markEmbeddedTurtleUsed({
        db,
        userId: "user-2",
        gameId: "game-conflict",
        figureId: "zhuge-liang",
      }),
    ).rejects.toMatchObject({ code: "conflict" });

    const stored = await getTurtleSession(db, "session-conflict");
    expect(stored).toMatchObject({
      user_id: "user-1",
      figure_id: "zhuge-liang",
      mode: "standalone",
      question_count: 1,
    });
  });

  it("独立模式猜中后完成会话，后续提交返回已完成冲突", async () => {
    const db = createMemoryTurtleDb();
    await createStandaloneTurtleSession({
      db,
      userId: "user-1",
      sessionId: "session-2",
      figureId: "zhuge-liang",
      questionCount: 2,
    });

    const result = await submitStandaloneTurtleAnswer({
      db,
      userId: "user-1",
      sessionId: "session-2",
      figure,
      answer: "孔明",
      questionCount: 2,
    });

    expect(result).toMatchObject({
      correct: true,
      completed: true,
      won: true,
      answer_attempts_used: 1,
      answer_attempts_remaining: 2,
      question_count: 2,
    });

    await expect(
      submitStandaloneTurtleAnswer({
        db,
        userId: "user-1",
        sessionId: "session-2",
        figure,
        answer: "诸葛亮",
        questionCount: 2,
      }),
    ).rejects.toMatchObject({ code: "completed" });
  });

  it("finish 重复提交返回 DB truth，且 turtle_used 后会把既有非 0 分强制归零", async () => {
    const db = createMemoryTurtleDb();
    const first = await persistFinishedGame({
      db,
      gameId: "game-1",
      userId: "user-1",
      figureId: "zhuge-liang",
      won: true,
      revealedCount: 6,
      score: 80,
      givenUp: false,
    });
    expect(first).toMatchObject({ score: 80, turtle_used: false });

    await markEmbeddedTurtleUsed({
      db,
      userId: "user-1",
      gameId: "game-1",
      figureId: "zhuge-liang",
    });
    const second = await persistFinishedGame({
      db,
      gameId: "game-1",
      userId: "user-1",
      figureId: "zhuge-liang",
      won: true,
      revealedCount: 6,
      score: 80,
      givenUp: false,
    });

    expect(second).toMatchObject({ score: 0, turtle_used: true });
    expect(db._games.get("game-1")?.score).toBe(0);
  });

  it("finish 遇到跨用户相同 game_id 时返回 conflict，不静默成功", async () => {
    const db = createMemoryTurtleDb();
    await persistFinishedGame({
      db,
      gameId: "game-owner",
      userId: "user-1",
      figureId: "zhuge-liang",
      won: true,
      revealedCount: 6,
      score: 80,
      givenUp: false,
    });

    await expect(
      persistFinishedGame({
        db,
        gameId: "game-owner",
        userId: "user-2",
        figureId: "zhuge-liang",
        won: true,
        revealedCount: 6,
        score: 90,
        givenUp: false,
      }),
    ).rejects.toMatchObject({ code: "conflict" });
  });
});
