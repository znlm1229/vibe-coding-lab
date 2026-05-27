import { matchExactly } from "$lib/match-exact";
import type { Figure, TurtleMode } from "$lib/types";

const STANDALONE_MAX_ANSWER_ATTEMPTS = 3;

export type TurtleD1Database = {
  prepare(sql: string): {
    bind(...values: unknown[]): {
      first<T = unknown>(): Promise<T | null>;
      run(): Promise<{ meta?: { changes?: number } } | unknown>;
    };
  };
};

export interface TurtleSessionRecord {
  id: string;
  user_id: string;
  game_id: string | null;
  figure_id: string;
  mode: TurtleMode;
  question_count: number;
  answer_attempts_used: number;
  completed: boolean;
  won: boolean | null;
  used_turtle: boolean;
}

export interface TurtleAnswerResult {
  correct: boolean;
  completed: boolean;
  won: boolean;
  answer_attempts_used: number;
  answer_attempts_remaining: number;
  question_count: number;
}

export class TurtleSessionError extends Error {
  constructor(
    public readonly code: "completed" | "attempts_exhausted" | "not_found" | "conflict",
    message: string,
  ) {
    super(message);
  }
}

export async function getTurtleSession(
  db: TurtleD1Database,
  sessionId: string,
): Promise<TurtleSessionRecord | null> {
  const row = await db
    .prepare(
      "SELECT id, user_id, game_id, figure_id, mode, question_count, answer_attempts_used, completed, won, used_turtle FROM turtle_sessions WHERE id = ?",
    )
    .bind(sessionId)
    .first<TurtleSessionRow>();

  return row ? toSessionRecord(row) : null;
}

export async function createStandaloneTurtleSession(input: {
  db: TurtleD1Database;
  userId: string;
  sessionId: string;
  figureId: string;
  questionCount?: number;
}): Promise<TurtleSessionRecord> {
  return ensureTurtleSession({
    db: input.db,
    sessionId: input.sessionId,
    userId: input.userId,
    gameId: null,
    figureId: input.figureId,
    mode: "standalone",
    questionCount: Math.max(0, Math.trunc(input.questionCount ?? 0)),
    answerAttemptsUsed: 0,
    completed: false,
    won: null,
    usedTurtle: true,
  });
}

export async function submitStandaloneTurtleAnswer(input: {
  db: TurtleD1Database;
  userId: string;
  sessionId: string;
  figure: Figure;
  answer: string;
  questionCount?: number;
}): Promise<TurtleAnswerResult> {
  const questionCount = Math.max(0, Math.trunc(input.questionCount ?? 0));
  const current = await getTurtleSession(input.db, input.sessionId);
  if (!current) throw new TurtleSessionError("not_found", "海龟汤会话不存在");
  if (
    current.user_id !== input.userId ||
    current.figure_id !== input.figure.id ||
    current.mode !== "standalone"
  ) {
    throw new TurtleSessionError("conflict", "海龟汤会话与当前用户或人物不匹配");
  }
  if (current.completed) throw new TurtleSessionError("completed", "海龟汤会话已完成");
  if (current.answer_attempts_used >= STANDALONE_MAX_ANSWER_ATTEMPTS) {
    throw new TurtleSessionError("attempts_exhausted", "答案提交机会已用完");
  }

  const correct = matchExactly(input.answer, input.figure);
  const attemptsUsed = current.answer_attempts_used + 1;
  const completed = correct || attemptsUsed >= STANDALONE_MAX_ANSWER_ATTEMPTS;
  const won = correct;
  const storedQuestionCount = Math.max(current.question_count, questionCount);

  await input.db
    .prepare(
      "UPDATE turtle_sessions SET question_count = max(question_count, ?), answer_attempts_used = answer_attempts_used + 1, completed = ?, won = ?, used_turtle = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ? AND figure_id = ? AND mode = 'standalone' AND completed = 0 AND answer_attempts_used < ?",
    )
    .bind(
      storedQuestionCount,
      completed ? 1 : 0,
      completed ? (won ? 1 : 0) : null,
      input.sessionId,
      input.userId,
      input.figure.id,
      STANDALONE_MAX_ANSWER_ATTEMPTS,
    )
    .run();

  const stored = await getTurtleSession(input.db, input.sessionId);
  if (!stored) throw new TurtleSessionError("not_found", "海龟汤会话不存在");
  if (stored.answer_attempts_used === current.answer_attempts_used) {
    if (stored.completed) throw new TurtleSessionError("completed", "海龟汤会话已完成");
    throw new TurtleSessionError("attempts_exhausted", "答案提交机会已用完");
  }

  return {
    correct,
    completed: stored.completed,
    won: Boolean(stored.won),
    answer_attempts_used: stored.answer_attempts_used,
    answer_attempts_remaining: Math.max(
      0,
      STANDALONE_MAX_ANSWER_ATTEMPTS - stored.answer_attempts_used,
    ),
    question_count: stored.question_count,
  };
}

export async function markEmbeddedTurtleUsed(input: {
  db: TurtleD1Database;
  userId: string;
  gameId: string;
  figureId: string;
}): Promise<TurtleSessionRecord> {
  const sessionId = embeddedSessionId(input.gameId);
  await ensureTurtleSession({
    db: input.db,
    sessionId,
    userId: input.userId,
    gameId: input.gameId,
    figureId: input.figureId,
    mode: "embedded",
    questionCount: 0,
    answerAttemptsUsed: 0,
    completed: false,
    won: null,
    usedTurtle: true,
  });

  const session = await getTurtleSession(input.db, sessionId);
  if (!session) throw new TurtleSessionError("not_found", "嵌入式海龟汤会话不存在");
  return session;
}

export async function hasEmbeddedTurtleUsage(
  db: TurtleD1Database,
  userId: string,
  gameId: string,
): Promise<boolean> {
  const row = await db
    .prepare(
      "SELECT id FROM turtle_sessions WHERE user_id = ? AND game_id = ? AND mode = 'embedded' AND used_turtle = 1 LIMIT 1",
    )
    .bind(userId, gameId)
    .first<{ id: string }>();
  return Boolean(row);
}

export async function persistFinishedGame(input: {
  db: TurtleD1Database;
  gameId: string;
  userId: string;
  figureId: string;
  won: boolean;
  revealedCount: number;
  score: number;
  givenUp: boolean;
}): Promise<{ persisted: true; score: number; turtle_used: boolean }> {
  const turtleUsed = await hasEmbeddedTurtleUsage(input.db, input.userId, input.gameId);
  const effectiveScore = turtleUsed ? 0 : Math.round(input.score);
  const existing = await getFinishedGame(input.db, input.gameId);

  if (existing) {
    if (existing.user_id !== input.userId) {
      throw new TurtleSessionError("conflict", "game_id 已属于其他用户");
    }
    if (turtleUsed && existing.score !== 0) {
      await input.db
        .prepare("UPDATE games SET score = 0 WHERE id = ? AND user_id = ?")
        .bind(input.gameId, input.userId)
        .run();
    }
    const stored = await getFinishedGame(input.db, input.gameId);
    if (!stored) throw new TurtleSessionError("not_found", "游戏结算记录不存在");
    return { persisted: true, score: stored.score, turtle_used: turtleUsed };
  }

  await input.db
    .prepare(
      "INSERT INTO games (id, user_id, figure_id, won, revealed_count, score, given_up, played_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
    )
    .bind(
      input.gameId,
      input.userId,
      input.figureId,
      input.won ? 1 : 0,
      input.revealedCount,
      effectiveScore,
      input.givenUp ? 1 : 0,
    )
    .run();

  const stored = await getFinishedGame(input.db, input.gameId);
  return { persisted: true, score: stored?.score ?? effectiveScore, turtle_used: turtleUsed };
}

function embeddedSessionId(gameId: string): string {
  return `embedded:${gameId}`;
}

async function ensureTurtleSession(input: {
  db: TurtleD1Database;
  sessionId: string;
  userId: string;
  gameId: string | null;
  figureId: string;
  mode: TurtleMode;
  questionCount: number;
  answerAttemptsUsed: number;
  completed: boolean;
  won: boolean | null;
  usedTurtle: boolean;
}): Promise<TurtleSessionRecord> {
  await input.db
    .prepare(
      "INSERT INTO turtle_sessions (id, user_id, game_id, figure_id, mode, question_count, answer_attempts_used, completed, won, used_turtle, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET question_count = max(turtle_sessions.question_count, excluded.question_count), used_turtle = max(turtle_sessions.used_turtle, excluded.used_turtle), updated_at = CURRENT_TIMESTAMP",
    )
    .bind(
      input.sessionId,
      input.userId,
      input.gameId,
      input.figureId,
      input.mode,
      input.questionCount,
      input.answerAttemptsUsed,
      input.completed ? 1 : 0,
      input.won === null ? null : input.won ? 1 : 0,
      input.usedTurtle ? 1 : 0,
    )
    .run();

  const stored = await getTurtleSession(input.db, input.sessionId);
  if (!stored) throw new TurtleSessionError("not_found", "海龟汤会话不存在");
  if (
    stored.user_id !== input.userId ||
    stored.game_id !== input.gameId ||
    stored.figure_id !== input.figureId ||
    stored.mode !== input.mode
  ) {
    throw new TurtleSessionError("conflict", "海龟汤会话与当前用户、游戏、人物或模式不匹配");
  }
  return stored;
}

type TurtleSessionRow = {
  id: string;
  user_id: string;
  game_id: string | null;
  figure_id: string;
  mode: TurtleMode;
  question_count: number;
  answer_attempts_used: number;
  completed: number | boolean;
  won: number | boolean | null;
  used_turtle: number | boolean;
};

function toSessionRecord(row: TurtleSessionRow): TurtleSessionRecord {
  return {
    id: row.id,
    user_id: row.user_id,
    game_id: row.game_id,
    figure_id: row.figure_id,
    mode: row.mode,
    question_count: Number(row.question_count),
    answer_attempts_used: Number(row.answer_attempts_used),
    completed: Boolean(row.completed),
    won: row.won === null ? null : Boolean(row.won),
    used_turtle: Boolean(row.used_turtle),
  };
}

type FinishedGameRow = {
  id: string;
  user_id: string;
  figure_id: string;
  won: number;
  revealed_count: number;
  score: number;
  given_up: number;
};

async function getFinishedGame(
  db: TurtleD1Database,
  gameId: string,
): Promise<FinishedGameRow | null> {
  return db
    .prepare("SELECT id, user_id, figure_id, won, revealed_count, score, given_up FROM games WHERE id = ?")
    .bind(gameId)
    .first<FinishedGameRow>();
}
