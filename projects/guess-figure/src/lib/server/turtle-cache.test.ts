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
  it("key 稳定，保留可读前缀和 figure/index/prompt 版本隔离字段", async () => {
    const key = await turtleCacheKey(baseKeyInput);
    const decodedKey = decodeURIComponent(key);

    expect(key).toBe(await turtleCacheKey(baseKeyInput));
    expect(decodedKey).toContain("turtle-cache:v1");
    expect(decodedKey).toContain("figure:zhuge-liang");
    expect(decodedKey).toContain("rag:rag-20260527");
    expect(decodedKey).toContain("prompt:prompt-v1");
    expect(decodedKey).not.toContain("他是否当过皇帝？");
  });

  it("question hash 为固定 64 hex", async () => {
    const key = await turtleCacheKey(baseKeyInput);
    const questionHash = key.match(/:q:([a-f0-9]{64})$/)?.[1];

    expect(questionHash).toBeDefined();
    expect(questionHash).toBe((await turtleCacheKey(baseKeyInput)).match(/:q:([a-f0-9]{64})$/)?.[1]);
  });

  it.each([
    ["figureId", "liu-bei"],
    ["normalizedQuestion", "他姓刘吗？"],
    ["ragIndexVersion", "rag-20260528"],
    ["promptVersion", "prompt-v2"],
  ] as const)("变更 %s 时 key 隔离", async (field, value) => {
    const changed = await turtleCacheKey({ ...baseKeyInput, [field]: value });
    expect(changed).not.toBe(await turtleCacheKey(baseKeyInput));
  });

  it("长中文问题不会让 KV key 超过 512 bytes", async () => {
    const key = await turtleCacheKey({
      ...baseKeyInput,
      normalizedQuestion: "他是不是在很长很长的历史叙述里仍然和某个事件有关？".repeat(40),
    });

    expect(new TextEncoder().encode(key).byteLength).toBeLessThanOrEqual(512);
  });
});

describe("turtle cache KV helpers", () => {
  it("写缓存使用 30 天 TTL", async () => {
    const { kv, puts } = mockKV();
    const key = await turtleCacheKey(baseKeyInput);

    await setTurtleCache(kv, key, { answer: "是" });

    expect(TURTLE_CACHE_TTL_SEC).toBe(30 * 24 * 60 * 60);
    expect(puts[0]).toMatchObject({ key, expirationTtl: TURTLE_CACHE_TTL_SEC });
  });

  it("cache hit 直接返回缓存，不调用后续依赖", async () => {
    const { kv } = mockKV();
    const key = await turtleCacheKey(baseKeyInput);
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
    const key = await turtleCacheKey(baseKeyInput);

    const result = await getOrResolveTurtleCache(kv, key, async () => ({ answer: "无关" }));

    expect(result).toEqual({ value: { answer: "无关" }, cacheHit: false });
    expect(await getTurtleCache(kv, key)).toEqual({ answer: "无关" });
  });
});
