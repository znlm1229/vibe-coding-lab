import { error, json } from "@sveltejs/kit";
import figures from "$lib/data/figures.json";
import type { Figure, TurtleAnswerApiResponse, TurtleMode } from "$lib/types";
import {
  markEmbeddedTurtleUsed,
  submitStandaloneTurtleAnswer,
  TurtleSessionError,
  type TurtleD1Database,
} from "$lib/server/turtle-session";
import type { RequestHandler } from "./$types";

type TurtleAnswerBody = {
  mode?: unknown;
  session_id?: unknown;
  game_id?: unknown;
  figure_id?: unknown;
  answer?: unknown;
  question_count?: unknown;
};

type HandlerDeps = {
  figures?: Figure[];
};

export function _createTurtleAnswerHandler(deps: HandlerDeps = {}): RequestHandler {
  const figureList = deps.figures ?? (figures as Figure[]);

  return async ({ request, locals, platform }) => {
    const userId = locals.user_id;
    if (!userId) throw error(401, "未认证");

    const db = platform?.env?.GF_DB as TurtleD1Database | undefined;
    if (!db) throw error(503, "海龟汤会话存储暂不可用");

    const body = await readBody(request);
    const mode = readMode(body.mode);
    const figureId = readRequiredString(body.figure_id, "figure_id");
    const figure = figureList.find((item) => item.id === figureId);
    if (!figure) throw error(400, `figure_id 不存在: ${figureId}`);

    if (mode === "embedded") {
      const gameId = readRequiredString(body.game_id, "game_id");
      await markEmbeddedTurtleUsed({ db, userId, gameId, figureId });
      return json({
        mode,
        used_turtle: true,
        consumes_answer: false,
      } satisfies TurtleAnswerApiResponse);
    }

    const sessionId = readRequiredString(body.session_id, "session_id");
    const answerText = readRequiredString(body.answer, "answer");
    const questionCount = readOptionalNonNegativeInteger(body.question_count, "question_count");

    try {
      const result = await submitStandaloneTurtleAnswer({
        db,
        userId,
        sessionId,
        figure,
        answer: answerText,
        questionCount,
      });

      return json({
        mode,
        correct: result.correct,
        completed: result.completed,
        won: result.won,
        answer_attempts_used: result.answer_attempts_used,
        answer_attempts_remaining: result.answer_attempts_remaining,
        question_count: result.question_count,
        consumes_answer: true,
      } satisfies TurtleAnswerApiResponse);
    } catch (cause) {
      if (cause instanceof TurtleSessionError) {
        if (cause.code === "completed") throw error(409, "海龟汤会话已完成");
        if (cause.code === "attempts_exhausted") throw error(409, "答案提交机会已用完");
        throw error(400, cause.message);
      }
      console.error("提交海龟汤答案失败", cause);
      throw error(500, "提交海龟汤答案失败");
    }
  };
}

export const POST: RequestHandler = _createTurtleAnswerHandler();

async function readBody(request: Request): Promise<TurtleAnswerBody> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    throw error(400, "请求体必须是 JSON");
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw error(400, "请求体必须是 JSON 对象");
  }
  return body as TurtleAnswerBody;
}

function readRequiredString(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw error(400, `${field} 必填`);
  }
  return value.trim();
}

function readMode(value: unknown): TurtleMode {
  if (value === undefined || value === null || value === "") return "standalone";
  if (value === "embedded" || value === "standalone") return value;
  throw error(400, "mode 必须是 embedded 或 standalone");
}

function readOptionalNonNegativeInteger(value: unknown, field: string): number | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw error(400, `${field} 必须是非负整数`);
  }
  return value;
}
