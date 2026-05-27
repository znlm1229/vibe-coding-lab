import { error, json } from "@sveltejs/kit";
import figures from "$lib/data/figures.json";
import type { Figure, TurtleMode, TurtleQuestionApiResponse } from "$lib/types";
import {
  getTurtleCache,
  setTurtleCache,
  turtleCacheKey,
  type TurtleCacheValue,
} from "$lib/server/turtle-cache";
import { validateTurtleQuestion } from "$lib/server/turtle-question";
import {
  answerTurtleQuestion,
  type AnswerTurtleQuestionInput,
  type TurtleRagDependencies,
  type TurtleRagResult,
} from "$lib/server/turtle-rag";
import {
  consumeTurtleQuestion,
  ensureEmbeddedTurtleSession,
  getEmbeddedTurtleSessionId,
  getTurtleSession,
  TurtleSessionError,
  type TurtleD1Database,
} from "$lib/server/turtle-session";
import type { RequestHandler } from "./$types";

const DEFAULT_RAG_INDEX_VERSION = "turtle-rag-v1";
const TURTLE_PROMPT_VERSION = "prompt-v1";
const INVALID_QUESTION_REASON = "请提出能用“是/否”回答的问题";
const DEGRADED_REASON = "海龟汤问答暂时不可用，请稍后重试";
const STANDALONE_MAX_QUESTIONS = 15;
const EMBEDDED_MAX_QUESTIONS = 5;

type TurtleQuestionBody = {
  figure_id?: unknown;
  question?: unknown;
  mode?: unknown;
  session_id?: unknown;
  game_id?: unknown;
};

type SessionQuestionContext = {
  db: TurtleD1Database;
  userId: string;
  sessionId: string;
  mode: TurtleMode;
  maxQuestions: number;
  figureId?: string;
};

type HandlerDeps = {
  figures?: Figure[];
  answerTurtleQuestion?: (input: AnswerTurtleQuestionInput) => Promise<TurtleRagResult>;
  getTurtleCache?: typeof getTurtleCache;
  setTurtleCache?: typeof setTurtleCache;
  turtleCacheKey?: typeof turtleCacheKey;
};

function response(body: TurtleQuestionApiResponse): Response {
  return json(body);
}

export function _createTurtleQuestionHandler(deps: HandlerDeps = {}): RequestHandler {
  const figureList = deps.figures ?? (figures as Figure[]);
  const resolveAnswer = deps.answerTurtleQuestion ?? answerTurtleQuestion;
  const readCache = deps.getTurtleCache ?? getTurtleCache;
  const writeCache = deps.setTurtleCache ?? setTurtleCache;
  const buildCacheKey = deps.turtleCacheKey ?? turtleCacheKey;

  return async ({ request, platform, locals }) => {
    const body = await readBody(request);
    const question = readRequiredString(body.question, "question");
    const mode = readMode(body.mode);
    const env = platform?.env;

    const { figure, sessionContext } = await resolveFigureAndSession({
      body,
      mode,
      env,
      userId: locals.user_id,
      figures: figureList,
    });

    const validation = validateTurtleQuestion(question);
    if (!validation.valid) {
      return response({
        invalid: true,
        consumes_question: false,
        reason: INVALID_QUESTION_REASON,
        mode,
      });
    }

    if (sessionContext) {
      const stored = await getTurtleSession(sessionContext.db, sessionContext.sessionId);
      if (!stored && sessionContext.mode === "standalone") {
        throw error(400, "海龟汤会话不存在");
      }
      if (stored && stored.question_count >= sessionContext.maxQuestions) {
        throw error(409, "海龟汤提问次数已用完");
      }
    }

    const ragIndexVersion = env?.RAG_INDEX_VERSION ?? DEFAULT_RAG_INDEX_VERSION;
    const promptVersion = TURTLE_PROMPT_VERSION;
    const cacheKey = await buildCacheKey({
      figureId: figure.id,
      normalizedQuestion: validation.normalizedQuestion,
      ragIndexVersion,
      promptVersion,
    });

    if (env?.GF_LLM_CACHE) {
      const cached = await readCache(env.GF_LLM_CACHE, cacheKey);
      if (cached) {
        const counted = await consumeIfNeeded(sessionContext);
        return response({
          answer: cached.answer,
          consumes_question: true,
          question_count: counted?.question_count,
          questions_remaining: counted
            ? Math.max(0, sessionContext!.maxQuestions - counted.question_count)
            : undefined,
          cached: true,
          mode,
          rag_index_version: ragIndexVersion,
          prompt_version: promptVersion,
        });
      }
    }

    if (!env?.AI || !env?.GF_VECTORIZE) {
      return degradedResponse({ mode, ragIndexVersion, promptVersion });
    }

    const result = await resolveAnswer({
      targetFigure: {
        id: figure.id,
        name: figure.name,
        aliases: figure.aliases,
      },
      normalizedQuestion: validation.normalizedQuestion,
      ragIndexVersion,
      promptVersion,
      dependencies: {
        ai: env.AI,
        // 在 API 边界把 Cloudflare metadata 类型收窄为 turtle-rag 已校验形状。
        vectorize: env.GF_VECTORIZE as unknown as TurtleRagDependencies["vectorize"],
      },
    });

    if (result.degraded) {
      return degradedResponse({ mode, ragIndexVersion, promptVersion, answer: result.answer });
    }

    const cacheValue: TurtleCacheValue = { answer: result.answer };
    if (env.GF_LLM_CACHE) {
      await writeCache(env.GF_LLM_CACHE, cacheKey, cacheValue);
    }

    const counted = await consumeIfNeeded(sessionContext);
    return response({
      answer: result.answer,
      consumes_question: true,
      question_count: counted?.question_count,
      questions_remaining: counted
        ? Math.max(0, sessionContext!.maxQuestions - counted.question_count)
        : undefined,
      cached: false,
      mode,
      rag_index_version: ragIndexVersion,
      prompt_version: promptVersion,
    });
  };
}

export const POST: RequestHandler = _createTurtleQuestionHandler();

async function resolveFigureAndSession(input: {
  body: TurtleQuestionBody;
  mode?: TurtleMode;
  env?: App.Platform["env"];
  userId?: string;
  figures: Figure[];
}): Promise<{ figure: Figure; sessionContext?: SessionQuestionContext }> {
  const db = input.env?.GF_DB as TurtleD1Database | undefined;

  if (input.mode === "standalone" && isNonEmptyString(input.body.session_id)) {
    if (!input.userId) throw error(401, "未认证");
    if (!db) throw error(503, "海龟汤会话存储暂不可用");
    const sessionId = input.body.session_id.trim();
    const session = await getTurtleSession(db, sessionId);
    if (!session) throw error(400, "海龟汤会话不存在");
    if (session.user_id !== input.userId || session.mode !== "standalone") {
      throw error(409, "海龟汤会话与当前用户或模式不匹配");
    }
    const figure = findFigure(input.figures, session.figure_id);
    return {
      figure,
      sessionContext: {
        db,
        userId: input.userId,
        sessionId,
        mode: "standalone",
        maxQuestions: STANDALONE_MAX_QUESTIONS,
      },
    };
  }

  if (input.mode === "embedded" && isNonEmptyString(input.body.game_id)) {
    if (!input.userId) throw error(401, "未认证");
    if (!db) throw error(503, "海龟汤会话存储暂不可用");
    const gameId = input.body.game_id.trim();
    const figureId = readRequiredString(input.body.figure_id, "figure_id");
    const figure = findFigure(input.figures, figureId);
    const sessionId = getEmbeddedTurtleSessionId(gameId);
    const existing = await getTurtleSession(db, sessionId);
    if (existing) {
      if (
        existing.user_id !== input.userId ||
        existing.game_id !== gameId ||
        existing.figure_id !== figureId ||
        existing.mode !== "embedded"
      ) {
        throw error(409, "海龟汤会话与当前用户、游戏、人物或模式不匹配");
      }
    }
    return {
      figure,
      sessionContext: {
        db,
        userId: input.userId,
        sessionId,
        mode: "embedded",
        maxQuestions: EMBEDDED_MAX_QUESTIONS,
        figureId,
      },
    };
  }

  const figureId = readRequiredString(input.body.figure_id, "figure_id");
  return { figure: findFigure(input.figures, figureId) };
}

async function consumeIfNeeded(
  sessionContext: SessionQuestionContext | undefined,
): Promise<Awaited<ReturnType<typeof consumeTurtleQuestion>> | undefined> {
  if (!sessionContext) return undefined;
  if (sessionContext.mode === "embedded") {
    const existing = await getTurtleSession(sessionContext.db, sessionContext.sessionId);
    if (!existing) {
      const gameId = sessionContext.sessionId.slice("embedded:".length);
      const figureId = sessionContext.figureId;
      if (!figureId) throw new TurtleSessionError("not_found", "海龟汤会话不存在");
      await ensureEmbeddedTurtleSession({
        db: sessionContext.db,
        userId: sessionContext.userId,
        gameId,
        figureId,
      });
    }
  }
  try {
    return await consumeTurtleQuestion(sessionContext);
  } catch (cause) {
    if (cause instanceof TurtleSessionError) {
      if (cause.code === "question_limit") throw error(409, cause.message);
      if (cause.code === "completed") throw error(409, cause.message);
      if (cause.code === "not_found") throw error(400, cause.message);
      if (cause.code === "conflict") throw error(409, cause.message);
    }
    throw cause;
  }
}

async function readBody(request: Request): Promise<TurtleQuestionBody> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    throw error(400, "请求体必须是 JSON");
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw error(400, "请求体必须是 JSON 对象");
  }
  return body as TurtleQuestionBody;
}

function readRequiredString(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw error(400, `${field} 必填`);
  }
  return value.trim();
}

function readMode(value: unknown): TurtleMode | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  if (value === "embedded" || value === "standalone") return value;
  throw error(400, "mode 必须是 embedded 或 standalone");
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function findFigure(figures: Figure[], figureId: string): Figure {
  const figure = figures.find((item) => item.id === figureId);
  if (!figure) throw error(400, `figure_id 不存在: ${figureId}`);
  return figure;
}

function degradedResponse(input: {
  mode?: TurtleMode;
  ragIndexVersion: string;
  promptVersion: string;
  answer?: TurtleQuestionApiResponse["answer"];
}): Response {
  return response({
    answer: input.answer ?? "无关",
    consumes_question: false,
    cached: false,
    degraded: true,
    network_error: true,
    reason: DEGRADED_REASON,
    mode: input.mode,
    rag_index_version: input.ragIndexVersion,
    prompt_version: input.promptVersion,
  });
}
