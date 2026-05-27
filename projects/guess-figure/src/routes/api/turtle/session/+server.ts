import { error, json, type RequestHandler } from "@sveltejs/kit";
import figures from "$lib/data/figures.json";
import type { Figure, TurtleMode } from "$lib/types";
import {
  createStandaloneTurtleSession,
  TurtleSessionError,
  type TurtleD1Database,
} from "$lib/server/turtle-session";

type TurtleSessionBody = {
  mode?: unknown;
  session_id?: unknown;
  figure_id?: unknown;
};

type HandlerDeps = {
  figures?: Figure[];
};

export function _createTurtleSessionHandler(deps: HandlerDeps = {}): RequestHandler {
  const figureList = deps.figures ?? (figures as Figure[]);

  return async ({ request, locals, platform }) => {
    const userId = locals.user_id;
    if (!userId) throw error(401, "未认证");

    const db = platform?.env?.GF_DB as TurtleD1Database | undefined;
    if (!db) throw error(503, "海龟汤会话存储暂不可用");

    const body = await readBody(request);
    const mode = readMode(body.mode);
    if (mode !== "standalone") throw error(400, "当前接口只支持 standalone 模式");

    const sessionId = readRequiredString(body.session_id, "session_id");
    const figureId = readRequiredString(body.figure_id, "figure_id");
    const figure = figureList.find((item) => item.id === figureId);
    if (!figure) throw error(400, `figure_id 不存在: ${figureId}`);

    try {
      const session = await createStandaloneTurtleSession({
        db,
        userId,
        sessionId,
        figureId,
      });

      return json({
        mode,
        session_id: session.id,
        figure_id: session.figure_id,
        question_count: session.question_count,
        answer_attempts_used: session.answer_attempts_used,
      });
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
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    throw error(400, "请求体必须是 JSON");
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw error(400, "请求体必须是 JSON 对象");
  }
  return body as TurtleSessionBody;
}

function readRequiredString(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw error(400, `${field} 必填`);
  }
  return value.trim();
}

function readMode(value: unknown): TurtleMode {
  if (value === undefined || value === null || value === "") return "standalone";
  if (value === "standalone" || value === "embedded") return value;
  throw error(400, "mode 必须是 embedded 或 standalone");
}
