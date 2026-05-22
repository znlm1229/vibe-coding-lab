// 002 T8: llm-cache.ts 单测
//
// 覆盖 06-tasks.md T8 Done when 的 5 case:
//   1. 同 figure+aliases+input 同 key
//   2. aliases 改后 key 不同
//   3. aliases 顺序不同但 sort 后同 key
//   4. cacheSet 后立即 cacheGet 命中
//   5. KV.put 失败 silent (cacheSet 返 ok=false 但不抛)

import { describe, it, expect } from "vitest";
import { cacheKey, cacheGet, cacheSet } from "./llm-cache";

/** mock KV (同 rate-limit.test.ts 的简化版) */
function mockKV(opts: { failOn?: (key: string) => boolean } = {}) {
  const store: Record<string, string> = {};
  const failOn = opts.failOn ?? (() => false);
  return {
    kv: {
      async get(key: string) {
        if (failOn(key)) throw new Error("mock KV failure");
        return store[key] ?? null;
      },
      async put(key: string, value: string) {
        if (failOn(key)) throw new Error("mock KV failure");
        store[key] = value;
      },
    } as any,
    store,
  };
}

describe("cacheKey", () => {
  it("case 1: 同 figure + 同 aliases + 同 input → 同 key", async () => {
    const k1 = await cacheKey("诸葛亮", ["孔明", "卧龙"], "诸葛丞相");
    const k2 = await cacheKey("诸葛亮", ["孔明", "卧龙"], "诸葛丞相");
    expect(k1).toBe(k2);
    expect(k1).toMatch(/^llm-cache:v1:诸葛亮:[a-f0-9]{64}:[a-f0-9]{64}$/);
  });

  it("case 2: aliases 改后 key 不同 (Q9 关键: aliases 影响 LLM prompt 必须 invalidate)", async () => {
    const k1 = await cacheKey("诸葛亮", ["孔明"], "诸葛丞相");
    const k2 = await cacheKey("诸葛亮", ["孔明", "卧龙"], "诸葛丞相");
    expect(k1).not.toBe(k2);
  });

  it("case 3: aliases 顺序不同但 sort 后同 key", async () => {
    const k1 = await cacheKey("诸葛亮", ["孔明", "卧龙", "武乡侯"], "诸葛丞相");
    const k2 = await cacheKey("诸葛亮", ["武乡侯", "孔明", "卧龙"], "诸葛丞相");
    expect(k1).toBe(k2);
  });

  it("不同 figure_id 隔离 (即使 aliases + input 都一样)", async () => {
    const k1 = await cacheKey("诸葛亮", ["孔明"], "孔明");
    const k2 = await cacheKey("曹操", ["孔明"], "孔明");
    expect(k1).not.toBe(k2);
  });

  it("不同 input → 不同 key", async () => {
    const k1 = await cacheKey("诸葛亮", ["孔明"], "诸葛丞相");
    const k2 = await cacheKey("诸葛亮", ["孔明"], "诸葛先生");
    expect(k1).not.toBe(k2);
  });

  it("空 aliases 不抛, 返合法 key", async () => {
    const k = await cacheKey("诸葛亮", [], "孔明");
    expect(k).toMatch(/^llm-cache:v1:诸葛亮:[a-f0-9]{64}:[a-f0-9]{64}$/);
  });
});

describe("cacheGet + cacheSet 集成", () => {
  it("case 4: cacheSet 后立即 cacheGet 命中", async () => {
    const { kv } = mockKV();
    const k = await cacheKey("诸葛亮", ["孔明"], "诸葛丞相");
    const writeResult = await cacheSet(kv, k, { correct: true, reason: "诸葛丞相指诸葛亮" });
    expect(writeResult.ok).toBe(true);

    const readResult = await cacheGet(kv, k);
    expect(readResult).toEqual({ correct: true, reason: "诸葛丞相指诸葛亮" });
  });

  it("不存在的 key cacheGet 返 null", async () => {
    const { kv } = mockKV();
    expect(await cacheGet(kv, "llm-cache:v1:no-such:0:0")).toBeNull();
  });

  it("KV 中含非法 JSON value → 返 null (容错)", async () => {
    const { kv, store } = mockKV();
    store["bad-key"] = "not-valid-json";
    expect(await cacheGet(kv, "bad-key")).toBeNull();
  });

  it("KV 中 value 缺字段 → 返 null", async () => {
    const { kv, store } = mockKV();
    store["incomplete-key"] = JSON.stringify({ correct: true /* 缺 reason */ });
    expect(await cacheGet(kv, "incomplete-key")).toBeNull();
  });

  it("cacheGet 在 KV.get 失败时返 null (failure open)", async () => {
    const { kv } = mockKV({ failOn: () => true });
    expect(await cacheGet(kv, "any-key")).toBeNull();
  });

  it("case 5: cacheSet 在 KV.put 失败时返 ok=false 但不抛", async () => {
    const { kv } = mockKV({ failOn: () => true });
    const result = await cacheSet(kv, "any-key", { correct: true, reason: "..." });
    expect(result.ok).toBe(false);
  });
});
