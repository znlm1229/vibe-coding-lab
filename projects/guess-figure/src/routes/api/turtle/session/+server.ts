import { error, json, type RequestHandler } from "@sveltejs/kit";
import figures from "$lib/data/figures.json";
import intros from "$lib/data/turtle-intros.json";
import { createPublicTurtleSoupRound } from "$lib/turtle-soup-state";
import type { Figure } from "$lib/types";
import {
  createStandaloneTurtleSession,
  getTurtleSession,
  TurtleSessionError,
  type TurtleD1Database,
} from "$lib/server/turtle-session";

type TurtleSessionBody = {
  mode?: unknown;
};

type HandlerDeps = {
  figures?: Figure[];
  intros?: Record<string, string>;
  createSessionId?: () => string;
  random?: () => number;
};

export function _createTurtleSessionHandler(deps: HandlerDeps = {}): RequestHandler {
  const figureList = deps.figures ?? (figures as Figure[]);
  const introMap = deps.intros ?? (intros as Record<string, string>);
  const createSessionId = deps.createSessionId ?? (() => crypto.randomUUID());
  const random = deps.random ?? Math.random;

  return async ({ request, locals, platform }) => {
    const userId = locals.user_id;
    if (!userId) throw error(401, "未认证");

    const db = platform?.env?.GF_DB as TurtleD1Database | undefined;
    if (!db) throw error(503, "海龟汤会话存储暂不可用");

    const body = await readBody(request);
    const mode = readMode(body.mode);
    if (mode !== "standalone") throw error(400, "当前接口只支持 standalone 模式");

    const figure = pickFigureWithIntro(figureList, introMap, random);
    const sessionId = createSessionId();

    try {
      const existing = await getTurtleSession(db, sessionId);
      if (existing) throw new TurtleSessionError("conflict", "海龟汤会话编号已存在");

      const session = await createStandaloneTurtleSession({
        db,
        userId,
        sessionId,
        figureId: figure.id,
      });

      return json(
        createPublicTurtleSoupRound({
          session_id: session.id,
          turtle_intro: introMap[figure.name] ?? "一处微光未明",
          question_count: session.question_count,
          answer_attempts_used: session.answer_attempts_used,
          status: "playing",
          questions: [],
        }),
      );
    } catch (cause) {
      if (cause instanceof TurtleSessionError) {
        if (cause.code === "conflict") throw error(409, cause.message);
        throw error(400, cause.message);
      }
      console.error("创建独立海龟汤会话失败", cause);
      throw error(500, "创建独立海龟汤会话失败");
    }
  };
}

export const POST: RequestHandler = _createTurtleSessionHandler();

async function readBody(request: Request): Promise<TurtleSessionBody> {
  const raw = await request.text();
  if (!raw.trim()) return {};

  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    throw error(400, "请求体必须是 JSON");
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw error(400, "请求体必须是 JSON 对象");
  }
  return body as TurtleSessionBody;
}

function readMode(value: unknown): "standalone" {
  if (value === undefined || value === null || value === "") return "standalone";
  if (value === "standalone") return value;
  throw error(400, "mode 必须是 standalone");
}

function pickFigureWithIntro(
  figureList: Figure[],
  introMap: Record<string, string>,
  random: () => number,
): Figure {
  const candidates = figureList.filter((figure) => introMap[figure.name]);
  const pool = candidates.length > 0 ? candidates : figureList;
  if (pool.length === 0) throw error(500, "海龟汤题库为空");

  const index = Math.min(pool.length - 1, Math.floor(random() * pool.length));
  return pool[index];
}
