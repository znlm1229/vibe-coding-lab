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
import type { RequestHandler } from "./$types";

const DEFAULT_RAG_INDEX_VERSION = "turtle-rag-v1";
const TURTLE_PROMPT_VERSION = "prompt-v1";
const INVALID_QUESTION_REASON = "请提出能用“是/否”回答的问题";
const DEGRADED_REASON = "海龟汤问答暂时不可用，请稍后重试";

type TurtleQuestionBody = {
  figure_id?: unknown;
  question?: unknown;
  mode?: unknown;
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

  return async ({ request, platform }) => {
    const body = await readBody(request);
    const figureId = readRequiredString(body.figure_id, "figure_id");
    const question = readRequiredString(body.question, "question");
    const mode = readMode(body.mode);

    const figure = figureList.find((item) => item.id === figureId);
    if (!figure) {
      throw error(400, `figure_id 不存在: ${figureId}`);
    }

    const validation = validateTurtleQuestion(question);
    if (!validation.valid) {
      return response({
        invalid: true,
        consumes_question: false,
        reason: INVALID_QUESTION_REASON,
        mode,
      });
    }

    const env = platform?.env;
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
        return response({
          answer: cached.answer,
          consumes_question: true,
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
        // Cloudflare 的 metadata 类型比 turtle-rag 的已校验 chunk metadata 更宽，这里在 API 边界收窄。
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

    return response({
      answer: result.answer,
      consumes_question: true,
      cached: false,
      mode,
      rag_index_version: ragIndexVersion,
      prompt_version: promptVersion,
    });
  };
}

export const POST: RequestHandler = _createTurtleQuestionHandler();

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
