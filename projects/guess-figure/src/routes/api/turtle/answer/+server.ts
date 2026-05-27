import { error, json } from "@sveltejs/kit";
import figures from "$lib/data/figures.json";
import type { Figure, TurtleAnswerApiResponse, TurtleMode } from "$lib/types";
import {
  getTurtleSession,
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

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function _createTurtleAnswerHandler(deps: HandlerDeps = {}): RequestHandler {
  const figureList = deps.figures ?? (figures as Figure[]);

  return async ({ request, locals, platform }) => {
    const userId = locals.user_id;
    if (!userId) throw error(401, "未认证");

    const db = platform?.env?.GF_DB as TurtleD1Database | undefined;
    if (!db) throw error(503, "海龟汤会话存储暂不可用");

    const body = await readBody(request);
    const mode = readMode(body.mode);

    if (mode === "embedded") {
      const figureId = readRequiredString(body.figure_id, "figure_id");
      const gameId = readRequiredString(body.game_id, "game_id");
      if (!UUID_RE.test(gameId)) throw error(400, "game_id 必须是 UUID 字符串");
      try {
        await markEmbeddedTurtleUsed({ db, userId, gameId, figureId });
        return json({
          mode,
          used_turtle: true,
          consumes_answer: false,
        } satisfies TurtleAnswerApiResponse);
      } catch (cause) {
        if (cause instanceof TurtleSessionError) {
          if (cause.code === "conflict") throw error(409, cause.message);
          throw error(400, cause.message);
        }
        console.error("记录嵌入式海龟汤使用失败", cause);
        throw error(500, "记录嵌入式海龟汤使用失败");
      }
    }

    const sessionId = readRequiredString(body.session_id, "session_id");
    const answerText = readRequiredString(body.answer, "answer");
    const questionCount = readOptionalNonNegativeInteger(body.question_count, "question_count");
    const session = await getTurtleSession(db, sessionId);
    if (!session) throw error(400, "海龟汤会话不存在");
    if (session.user_id !== userId || session.mode !== "standalone") {
      throw error(409, "海龟汤会话与当前用户或模式不匹配");
    }

    const clientFigureId =
      typeof body.figure_id === "string" && body.figure_id.trim() ? body.figure_id.trim() : undefined;
    if (clientFigureId && clientFigureId !== session.figure_id) {
      throw error(409, "figure_id 与会话目标不匹配");
    }

    const figure = figureList.find((item) => item.id === session.figure_id);
    if (!figure) throw error(400, `figure_id 不存在: ${session.figure_id}`);

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
        reveal: result.completed
          ? {
              target_name: figure.name,
              target_aliases: figure.aliases,
              target_wiki_url: figure.wiki_url,
            }
          : undefined,
      } satisfies TurtleAnswerApiResponse);
    } catch (cause) {
      if (cause instanceof TurtleSessionError) {
        if (cause.code === "completed") throw error(409, "海龟汤会话已完成");
        if (cause.code === "attempts_exhausted") throw error(409, "答案提交机会已用完");
        if (cause.code === "not_found") throw error(400, "海龟汤会话不存在");
        if (cause.code === "conflict") throw error(409, cause.message);
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
