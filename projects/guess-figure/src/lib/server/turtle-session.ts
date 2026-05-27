import { matchExactly } from "$lib/match-exact";
import type { Figure, TurtleMode } from "$lib/types";

const STANDALONE_MAX_ANSWER_ATTEMPTS = 3;

type D1RunResult = {
  meta?: { changes?: number };
};

export type TurtleD1Database = {
  prepare(sql: string): {
    bind(...values: unknown[]): {
      first<T = unknown>(): Promise<T | null>;
      run(): Promise<D1RunResult>;
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
    public readonly code:
      | "completed"
      | "attempts_exhausted"
      | "question_limit"
      | "not_found"
      | "conflict",
    message: string,
  ) {
    super(message);
  }
}

export function getEmbeddedTurtleSessionId(gameId: string): string {
  return embeddedSessionId(gameId);
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

export async function consumeTurtleQuestion(input: {
  db: TurtleD1Database;
  userId: string;
  sessionId: string;
  mode: TurtleMode;
  maxQuestions: number;
}): Promise<TurtleSessionRecord> {
  const updateResult = await input.db
    .prepare(
      "UPDATE turtle_sessions SET question_count = question_count + 1, used_turtle = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ? AND mode = ? AND completed = 0 AND question_count < ?",
    )
    .bind(input.sessionId, input.userId, input.mode, input.maxQuestions)
    .run();

  const stored = await getTurtleSession(input.db, input.sessionId);
  if (!stored) throw new TurtleSessionError("not_found", "海龟汤会话不存在");
  if (stored.user_id !== input.userId || stored.mode !== input.mode) {
    throw new TurtleSessionError("conflict", "海龟汤会话与当前用户或模式不匹配");
  }
  if (changesOf(updateResult) !== 1) {
    if (stored.completed) throw new TurtleSessionError("completed", "海龟汤会话已完成");
    if (stored.question_count >= input.maxQuestions) {
      throw new TurtleSessionError("question_limit", "海龟汤提问次数已用完");
    }
    throw new TurtleSessionError("conflict", "海龟汤提问次数更新未生效");
  }
  return stored;
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
  const storedQuestionCount = Math.max(current.question_count, questionCount);
  const updateResult = await input.db
    .prepare(
      "UPDATE turtle_sessions SET question_count = max(question_count, ?), answer_attempts_used = answer_attempts_used + 1, completed = CASE WHEN ? = 1 OR answer_attempts_used + 1 >= ? THEN 1 ELSE 0 END, won = CASE WHEN ? = 1 THEN 1 WHEN answer_attempts_used + 1 >= ? THEN 0 ELSE NULL END, used_turtle = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ? AND figure_id = ? AND mode = 'standalone' AND completed = 0 AND answer_attempts_used < ?",
    )
    .bind(
      storedQuestionCount,
      correct ? 1 : 0,
      STANDALONE_MAX_ANSWER_ATTEMPTS,
      correct ? 1 : 0,
      STANDALONE_MAX_ANSWER_ATTEMPTS,
      input.sessionId,
      input.userId,
      input.figure.id,
      STANDALONE_MAX_ANSWER_ATTEMPTS,
    )
    .run();

  const stored = await getTurtleSession(input.db, input.sessionId);
  if (!stored) throw new TurtleSessionError("not_found", "海龟汤会话不存在");
  if (changesOf(updateResult) !== 1) {
    if (
      stored.user_id !== input.userId ||
      stored.figure_id !== input.figure.id ||
      stored.mode !== "standalone"
    ) {
      throw new TurtleSessionError("conflict", "海龟汤会话与当前用户或人物不匹配");
    }
    if (stored.completed) throw new TurtleSessionError("completed", "海龟汤会话已完成");
    if (stored.answer_attempts_used >= STANDALONE_MAX_ANSWER_ATTEMPTS) {
      throw new TurtleSessionError("attempts_exhausted", "答案提交机会已用完");
    }
    throw new TurtleSessionError("attempts_exhausted", "答案提交未生效");
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
  return ensureTurtleSession({
    db: input.db,
    sessionId: embeddedSessionId(input.gameId),
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
}

export async function ensureEmbeddedTurtleSession(input: {
  db: TurtleD1Database;
  userId: string;
  gameId: string;
  figureId: string;
}): Promise<TurtleSessionRecord> {
  return ensureTurtleSession({
    db: input.db,
    sessionId: embeddedSessionId(input.gameId),
    userId: input.userId,
    gameId: input.gameId,
    figureId: input.figureId,
    mode: "embedded",
    questionCount: 0,
    answerAttemptsUsed: 0,
    completed: false,
    won: null,
    usedTurtle: false,
  });
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

  await input.db
    .prepare(
      "INSERT OR IGNORE INTO games (id, user_id, figure_id, won, revealed_count, score, given_up, played_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
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

  let stored = await getFinishedGame(input.db, input.gameId);
  if (!stored) throw new TurtleSessionError("not_found", "游戏结算记录不存在");
  if (stored.user_id !== input.userId) {
    throw new TurtleSessionError("conflict", "game_id 已属于其他用户");
  }

  if (turtleUsed && stored.score !== 0) {
    await input.db
      .prepare("UPDATE games SET score = 0 WHERE id = ? AND user_id = ?")
      .bind(input.gameId, input.userId)
      .run();
    stored = await getFinishedGame(input.db, input.gameId);
    if (!stored) throw new TurtleSessionError("not_found", "游戏结算记录不存在");
    if (stored.user_id !== input.userId) {
      throw new TurtleSessionError("conflict", "game_id 已属于其他用户");
    }
  }

  return { persisted: true, score: stored.score, turtle_used: turtleUsed };
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
      "INSERT INTO turtle_sessions (id, user_id, game_id, figure_id, mode, question_count, answer_attempts_used, completed, won, used_turtle, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET question_count = max(turtle_sessions.question_count, excluded.question_count), used_turtle = max(turtle_sessions.used_turtle, excluded.used_turtle), updated_at = CURRENT_TIMESTAMP WHERE turtle_sessions.user_id = excluded.user_id AND ((turtle_sessions.game_id IS NULL AND excluded.game_id IS NULL) OR turtle_sessions.game_id = excluded.game_id) AND turtle_sessions.figure_id = excluded.figure_id AND turtle_sessions.mode = excluded.mode",
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

function changesOf(result: D1RunResult): number | undefined {
  return result.meta?.changes;
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
    .prepare(
      "SELECT id, user_id, figure_id, won, revealed_count, score, given_up FROM games WHERE id = ?",
    )
    .bind(gameId)
    .first<FinishedGameRow>();
}
