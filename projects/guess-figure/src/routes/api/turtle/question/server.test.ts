import { describe, expect, it, vi } from "vitest";
import { _createTurtleQuestionHandler } from "./+server";
import type { Figure, TurtleQuestionApiResponse } from "$lib/types";
import type { TurtleCacheValue } from "$lib/server/turtle-cache";
import type { TurtleRagResult } from "$lib/server/turtle-rag";

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

async function readJson(response: Response): Promise<TurtleQuestionApiResponse> {
  return (await response.json()) as TurtleQuestionApiResponse;
}

describe("/api/turtle/question", () => {
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
