import { describe, expect, it } from "vitest";
import {
  TURTLE_CACHE_TTL_SEC,
  getOrResolveTurtleCache,
  getTurtleCache,
  setTurtleCache,
  turtleCacheKey,
} from "./turtle-cache";

function mockKV() {
  const store: Record<string, string> = {};
  const puts: Array<{ key: string; value: string; expirationTtl?: number }> = [];

  return {
    kv: {
      async get(key: string) {
        return store[key] ?? null;
      },
      async put(key: string, value: string, options?: { expirationTtl?: number }) {
        store[key] = value;
        puts.push({ key, value, expirationTtl: options?.expirationTtl });
      },
    } as any,
    puts,
    store,
  };
}

const baseKeyInput = {
  figureId: "zhuge-liang",
  normalizedQuestion: "他是否当过皇帝？",
  ragIndexVersion: "rag-20260527",
  promptVersion: "prompt-v1",
};

describe("turtleCacheKey", () => {
  it("key 稳定且包含 figure_id、normalized_question、rag_index_version、prompt_version", () => {
    const key = turtleCacheKey(baseKeyInput);

    expect(key).toBe(turtleCacheKey(baseKeyInput));
    expect(decodeURIComponent(key)).toContain("zhuge-liang");
    expect(decodeURIComponent(key)).toContain("他是否当过皇帝？");
    expect(decodeURIComponent(key)).toContain("rag-20260527");
    expect(decodeURIComponent(key)).toContain("prompt-v1");
  });

  it.each([
    ["figureId", "liu-bei"],
    ["normalizedQuestion", "他姓刘吗？"],
    ["ragIndexVersion", "rag-20260528"],
    ["promptVersion", "prompt-v2"],
  ] as const)("变更 %s 时 key 隔离", (field, value) => {
    const changed = turtleCacheKey({ ...baseKeyInput, [field]: value });
    expect(changed).not.toBe(turtleCacheKey(baseKeyInput));
  });
});

describe("turtle cache KV helpers", () => {
  it("写缓存使用 30 天 TTL", async () => {
    const { kv, puts } = mockKV();
    const key = turtleCacheKey(baseKeyInput);

    await setTurtleCache(kv, key, { answer: "是" });

    expect(TURTLE_CACHE_TTL_SEC).toBe(30 * 24 * 60 * 60);
    expect(puts[0]).toMatchObject({ key, expirationTtl: TURTLE_CACHE_TTL_SEC });
  });

  it("cache hit 直接返回缓存，不调用后续依赖", async () => {
    const { kv } = mockKV();
    const key = turtleCacheKey(baseKeyInput);
    await setTurtleCache(kv, key, { answer: "否" });

    let resolverCalls = 0;
    const result = await getOrResolveTurtleCache(kv, key, async () => {
      resolverCalls += 1;
      return { answer: "是" as const };
    });

    expect(result).toEqual({ value: { answer: "否" }, cacheHit: true });
    expect(resolverCalls).toBe(0);
  });

  it("cache miss 调用后续依赖并写入缓存", async () => {
    const { kv } = mockKV();
    const key = turtleCacheKey(baseKeyInput);

    const result = await getOrResolveTurtleCache(kv, key, async () => ({ answer: "无关" }));

    expect(result).toEqual({ value: { answer: "无关" }, cacheHit: false });
    expect(await getTurtleCache(kv, key)).toEqual({ answer: "无关" });
  });
});
