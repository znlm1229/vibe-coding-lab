import { describe, expect, it, vi } from "vitest";
import { _createTurtleQuestionHandler } from "./+server";
import type { Figure, TurtleQuestionApiResponse } from "$lib/types";
import type { TurtleCacheValue } from "$lib/server/turtle-cache";
import type { TurtleRagResult } from "$lib/server/turtle-rag";
import type { TurtleSessionRecord } from "$lib/server/turtle-session";

const figure: Figure = {
  id: "guan-yu",
  name: "关羽",
  aliases: ["关云长", "关公"],
  clues: [],
  source: "test",
  wikidata_id: "Q123",
  wiki_url: "https://example.test/guan-yu",
};

function mockKV(initial: Record<string, TurtleCacheValue> = {}) {
  const store = new Map(
    Object.entries(initial).map(([key, value]) => [key, JSON.stringify(value)]),
  );
  const puts: Array<{ key: string; value: string; options?: { expirationTtl?: number } }> = [];

  return {
    kv: {
      async get(key: string) {
        return store.get(key) ?? null;
      },
      async put(key: string, value: string, options?: { expirationTtl?: number }) {
        store.set(key, value);
        puts.push({ key, value, options });
      },
    },
    puts,
  };
}

function mockEvent(body: unknown, env?: Record<string, unknown>) {
  return {
    request: new Request("https://test.local/api/turtle/question", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "content-type": "application/json" },
    }),
    platform: env ? { env } : undefined,
    locals: { user_id: "user-test" },
    getClientAddress: () => "127.0.0.1",
  } as any;
}

function createMemoryTurtleDb() {
  const sessions = new Map<string, TurtleSessionRecord>();

  return {
    _sessions: sessions,
    prepare(sql: string) {
      return {
        bind(...params: unknown[]) {
          return {
            async first<T>() {
              if (sql.includes("FROM turtle_sessions") && sql.includes("WHERE id = ?")) {
                return (sessions.get(String(params[0])) ?? null) as T | null;
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
                if (!sessions.has(String(id))) {
                  sessions.set(String(id), {
                    id: String(id),
                    user_id: String(user_id),
                    game_id: game_id === null ? null : String(game_id),
                    figure_id: String(figure_id),
                    mode: mode as TurtleSessionRecord["mode"],
                    question_count: Number(question_count),
                    answer_attempts_used: Number(answer_attempts_used),
                    completed: Boolean(completed),
                    won: won === null ? null : Boolean(won),
                    used_turtle: Boolean(used_turtle),
                  });
                  changes = 1;
                }
              }
              if (sql.startsWith("UPDATE turtle_sessions SET question_count = question_count + 1")) {
                const [id, user_id, mode, maxQuestions] = params;
                const session = sessions.get(String(id));
                if (
                  session &&
                  session.user_id === user_id &&
                  session.mode === mode &&
                  !session.completed &&
                  session.question_count < Number(maxQuestions)
                ) {
                  session.question_count += 1;
                  session.used_turtle = true;
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

async function readJson(response: Response): Promise<TurtleQuestionApiResponse> {
  return (await response.json()) as TurtleQuestionApiResponse;
}

describe("/api/turtle/question", () => {
  it("standalone 通过 session_id 查目标并由服务端原子累计 15 次有效问题", async () => {
    const db = createMemoryTurtleDb();
    db._sessions.set("session-1", {
      id: "session-1",
      user_id: "user-test",
      game_id: null,
      figure_id: "guan-yu",
      mode: "standalone",
      question_count: 14,
      answer_attempts_used: 0,
      completed: false,
      won: null,
      used_turtle: true,
    });
    const answerTurtleQuestion = vi.fn(async (): Promise<TurtleRagResult> => ({
      answer: "是",
      evidence: [],
      degraded: false,
      ragIndexVersion: "test-index",
      promptVersion: "prompt-v1",
    }));
    const handler = _createTurtleQuestionHandler({ figures: [figure], answerTurtleQuestion });

    const response = await handler(
      mockEvent(
        {
          mode: "standalone",
          session_id: "session-1",
          question: "他是不是被后世尊为武圣？",
        },
        {
          GF_DB: db,
          GF_VECTORIZE: { query: vi.fn() },
          AI: { run: vi.fn() },
          RAG_INDEX_VERSION: "test-index",
        },
      ),
    );
    const body = await readJson(response);

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      answer: "是",
      consumes_question: true,
      question_count: 15,
    });
    expect(answerTurtleQuestion).toHaveBeenCalledWith(
      expect.objectContaining({
        targetFigure: expect.objectContaining({ id: "guan-yu" }),
      }),
    );

    await expect(
      handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "session-1",
            question: "他是不是皇帝？",
          },
          {
            GF_DB: db,
            GF_VECTORIZE: { query: vi.fn() },
            AI: { run: vi.fn() },
            RAG_INDEX_VERSION: "test-index",
          },
        ),
      ),
    ).rejects.toMatchObject({ status: 409 });
    expect(db._sessions.get("session-1")?.question_count).toBe(15);
  });

  it("standalone invalid 与 degraded 不扣服务端问题次数", async () => {
    const db = createMemoryTurtleDb();
    db._sessions.set("session-invalid", {
      id: "session-invalid",
      user_id: "user-test",
      game_id: null,
      figure_id: "guan-yu",
      mode: "standalone",
      question_count: 3,
      answer_attempts_used: 0,
      completed: false,
      won: null,
      used_turtle: true,
    });
    const handler = _createTurtleQuestionHandler({ figures: [figure] });

    const invalid = await readJson(
      await handler(
        mockEvent(
          { mode: "standalone", session_id: "session-invalid", question: "他是谁？" },
          { GF_DB: db },
        ),
      ),
    );
    const degraded = await readJson(
      await handler(
        mockEvent(
          { mode: "standalone", session_id: "session-invalid", question: "他是不是皇帝？" },
          { GF_DB: db },
        ),
      ),
    );

    expect(invalid).toMatchObject({ invalid: true, consumes_question: false });
    expect(degraded).toMatchObject({ degraded: true, consumes_question: false });
    expect(db._sessions.get("session-invalid")?.question_count).toBe(3);
  });

  it("standalone 已完成会话在 cache/RAG/LLM 前直接拒绝", async () => {
    const db = createMemoryTurtleDb();
    db._sessions.set("session-completed", {
      id: "session-completed",
      user_id: "user-test",
      game_id: null,
      figure_id: "guan-yu",
      mode: "standalone",
      question_count: 3,
      answer_attempts_used: 3,
      completed: true,
      won: false,
      used_turtle: true,
    });
    const getTurtleCache = vi.fn(async () => null);
    const setTurtleCache = vi.fn();
    const answerTurtleQuestion = vi.fn(async (): Promise<TurtleRagResult> => ({
      answer: "否",
      evidence: [],
      degraded: false,
      ragIndexVersion: "test-index",
      promptVersion: "prompt-v1",
    }));
    const aiRun = vi.fn();
    const vectorQuery = vi.fn();
    const handler = _createTurtleQuestionHandler({
      figures: [figure],
      getTurtleCache,
      setTurtleCache,
      answerTurtleQuestion,
    });

    await expect(
      handler(
        mockEvent(
          {
            mode: "standalone",
            session_id: "session-completed",
            question: "他是不是皇帝？",
          },
          {
            GF_DB: db,
            GF_LLM_CACHE: {},
            GF_VECTORIZE: { query: vectorQuery },
            AI: { run: aiRun },
            RAG_INDEX_VERSION: "test-index",
          },
        ),
      ),
    ).rejects.toMatchObject({ status: 409 });

    expect(getTurtleCache).not.toHaveBeenCalled();
    expect(setTurtleCache).not.toHaveBeenCalled();
    expect(answerTurtleQuestion).not.toHaveBeenCalled();
    expect(vectorQuery).not.toHaveBeenCalled();
    expect(aiRun).not.toHaveBeenCalled();
  });

  it("embedded 通过 game_id 建立会话并限制 5 次有效问题", async () => {
    const db = createMemoryTurtleDb();
    const answerTurtleQuestion = vi.fn(async (): Promise<TurtleRagResult> => ({
      answer: "否",
      evidence: [],
      degraded: false,
      ragIndexVersion: "test-index",
      promptVersion: "prompt-v1",
    }));
    const handler = _createTurtleQuestionHandler({ figures: [figure], answerTurtleQuestion });
    const env = {
      GF_DB: db,
      GF_VECTORIZE: { query: vi.fn() },
      AI: { run: vi.fn() },
      RAG_INDEX_VERSION: "test-index",
    };

    for (let index = 0; index < 5; index += 1) {
      const body = await readJson(
        await handler(
          mockEvent(
            {
              mode: "embedded",
              game_id: "123e4567-e89b-42d3-a456-426614174000",
              figure_id: "guan-yu",
              question: `他是不是皇帝？${index}`,
            },
            env,
          ),
        ),
      );
      expect(body).toMatchObject({ consumes_question: true, question_count: index + 1 });
    }

    await expect(
      handler(
        mockEvent(
          {
            mode: "embedded",
            game_id: "123e4567-e89b-42d3-a456-426614174000",
            figure_id: "guan-yu",
            question: "他是不是诗人？",
          },
          env,
        ),
      ),
    ).rejects.toMatchObject({ status: 409 });

    expect(db._sessions.get("embedded:123e4567-e89b-42d3-a456-426614174000")).toMatchObject({
      question_count: 5,
      used_turtle: true,
    });
  });
  it("合法 JSON 但不是对象时返回 400，避免 TypeError 变成 500", async () => {
    const handler = _createTurtleQuestionHandler({ figures: [figure] });

    await expect(handler(mockEvent(null))).rejects.toMatchObject({
      status: 400,
      body: { message: "请求体必须是 JSON 对象" },
    });
  });

  it("未知 mode 返回 400，且不调用 cache/RAG/LLM", async () => {
    const answerTurtleQuestion = vi.fn();
    const getTurtleCache = vi.fn();
    const setTurtleCache = vi.fn();
    const handler = _createTurtleQuestionHandler({
      figures: [figure],
      answerTurtleQuestion,
      getTurtleCache,
      setTurtleCache,
    });

    await expect(
      handler(mockEvent({ figure_id: "guan-yu", question: "他是不是皇帝？", mode: "arcade" })),
    ).rejects.toMatchObject({
      status: 400,
      body: { message: "mode 必须是 embedded 或 standalone" },
    });

    expect(getTurtleCache).not.toHaveBeenCalled();
    expect(setTurtleCache).not.toHaveBeenCalled();
    expect(answerTurtleQuestion).not.toHaveBeenCalled();
  });

  it("invalid 问法返回 invalid 且不调用 cache/RAG/LLM", async () => {
    const answerTurtleQuestion = vi.fn();
    const getTurtleCache = vi.fn();
    const setTurtleCache = vi.fn();
    const handler = _createTurtleQuestionHandler({
      figures: [figure],
      answerTurtleQuestion,
      getTurtleCache,
      setTurtleCache,
    });

    const response = await handler(mockEvent({ figure_id: "guan-yu", question: "他是谁？" }));
    const body = await readJson(response);

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      invalid: true,
      consumes_question: false,
    });
    expect(getTurtleCache).not.toHaveBeenCalled();
    expect(setTurtleCache).not.toHaveBeenCalled();
    expect(answerTurtleQuestion).not.toHaveBeenCalled();
  });

  it("cache miss 调用 RAG 并写入 KV cache", async () => {
    const { kv, puts } = mockKV();
    const answerTurtleQuestion = vi.fn(async (): Promise<TurtleRagResult> => ({
      answer: "是",
      evidence: [],
      degraded: false,
      ragIndexVersion: "test-index",
      promptVersion: "prompt-v1",
    }));
    const handler = _createTurtleQuestionHandler({
      figures: [figure],
      answerTurtleQuestion,
    });

    const response = await handler(
      mockEvent(
        { figure_id: "guan-yu", question: "他是不是被后世尊为武圣？", mode: "standalone" },
        {
          GF_LLM_CACHE: kv,
          GF_VECTORIZE: { query: vi.fn() },
          AI: { run: vi.fn() },
          RAG_INDEX_VERSION: "test-index",
        },
      ),
    );
    const body = await readJson(response);

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      answer: "是",
      consumes_question: true,
      cached: false,
    });
    expect(answerTurtleQuestion).toHaveBeenCalledOnce();
    expect(answerTurtleQuestion).toHaveBeenCalledWith(
      expect.objectContaining({
        targetFigure: expect.objectContaining({ id: "guan-yu", name: "关羽" }),
        normalizedQuestion: "他是不是被后世尊为武圣？",
        ragIndexVersion: "test-index",
        promptVersion: "prompt-v1",
      }),
    );
    expect(puts).toHaveLength(1);
    expect(JSON.parse(puts[0].value)).toEqual({ answer: "是" });
  });

  it("cache hit 直接返回 cached 且不调用 Vectorize / LLM / RAG", async () => {
    const answerTurtleQuestion = vi.fn();
    const aiRun = vi.fn();
    const vectorQuery = vi.fn();
    const keyForTest = vi.fn(async () => "cache-hit-key");
    const { kv } = mockKV({ "cache-hit-key": { answer: "否" } });
    const handler = _createTurtleQuestionHandler({
      figures: [figure],
      answerTurtleQuestion,
      turtleCacheKey: keyForTest,
    });

    const response = await handler(
      mockEvent(
        { figure_id: "guan-yu", question: "他是不是皇帝？" },
        {
          GF_LLM_CACHE: kv,
          GF_VECTORIZE: { query: vectorQuery },
          AI: { run: aiRun },
          RAG_INDEX_VERSION: "test-index",
        },
      ),
    );
    const body = await readJson(response);

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      answer: "否",
      consumes_question: true,
      cached: true,
    });
    expect(answerTurtleQuestion).not.toHaveBeenCalled();
    expect(vectorQuery).not.toHaveBeenCalled();
    expect(aiRun).not.toHaveBeenCalled();
  });

  it("RAG degraded 返回 200 degraded，不把错误当成否且不写缓存", async () => {
    const { kv, puts } = mockKV();
    const answerTurtleQuestion = vi.fn(async (): Promise<TurtleRagResult> => ({
      answer: "无关",
      evidence: [],
      degraded: true,
      ragIndexVersion: "test-index",
      promptVersion: "prompt-v1",
    }));
    const handler = _createTurtleQuestionHandler({
      figures: [figure],
      answerTurtleQuestion,
    });

    const response = await handler(
      mockEvent(
        { figure_id: "guan-yu", question: "他是不是被后世尊为武圣？" },
        {
          GF_LLM_CACHE: kv,
          GF_VECTORIZE: { query: vi.fn() },
          AI: { run: vi.fn() },
          RAG_INDEX_VERSION: "test-index",
        },
      ),
    );
    const body = await readJson(response);

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      answer: "无关",
      degraded: true,
      network_error: true,
      consumes_question: false,
      cached: false,
    });
    expect(body.answer).not.toBe("否");
    expect(puts).toHaveLength(0);
  });
});
