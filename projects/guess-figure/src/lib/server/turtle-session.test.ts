import { describe, expect, it } from "vitest";
import type { Figure } from "$lib/types";
import {
  getTurtleSession,
  markEmbeddedTurtleUsed,
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

type StoredSession = TurtleSessionRecord;
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
  const sessions = new Map<string, StoredSession>();
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
                    mode: mode as StoredSession["mode"],
                    question_count: Number(question_count),
                    answer_attempts_used: Number(answer_attempts_used),
                    completed: Boolean(completed),
                    won: won === null ? null : Boolean(won),
                    used_turtle: Boolean(used_turtle),
                  });
                }
                return { success: true };
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
                return { success: true };
              }
              if (sql.startsWith("INSERT OR IGNORE INTO games")) {
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
                }
                return { success: true };
              }
              return { success: true };
            },
          };
        },
      };
    },
  };
}

describe("turtle-session", () => {
  it("独立模式有 3 次答案提交机会，错答只扣答案次数不扣提问次数", async () => {
    const db = createMemoryTurtleDb();

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

  it("独立模式猜中后完成会话，后续提交返回已完成冲突", async () => {
    const db = createMemoryTurtleDb();

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

  it("嵌入式模式会按 game_id 持久化海龟汤已使用状态", async () => {
    const db = createMemoryTurtleDb();

    await markEmbeddedTurtleUsed({
      db,
      userId: "user-1",
      gameId: "game-1",
      figureId: "zhuge-liang",
    });

    const stored = await getTurtleSession(db, "embedded:game-1");
    expect(stored).toMatchObject({
      user_id: "user-1",
      game_id: "game-1",
      figure_id: "zhuge-liang",
      mode: "embedded",
      used_turtle: true,
    });
  });
});
