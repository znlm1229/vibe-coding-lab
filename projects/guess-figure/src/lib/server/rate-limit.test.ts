// 002 T7: rate-limit.ts 单测
//
// 覆盖 06-tasks.md T7 Done when 的 7 case:
//   1. counter < 阈值 ok
//   2. >= 阈值 reject
//   3. KV.get 失败 failure open (request 类型)
//   4. LLM budget KV 失败 failure close (返"已达上限"进入降级)
//   5. 不同 user_id 互不影响
//   6. 不同 IP 互不影响
//   7. UTC 日切 key 不同

import { describe, it, expect } from "vitest";
import {
  checkRateLimits,
  incrementCounter,
  utcDay,
} from "./rate-limit";

/** mock KV with controllable store + failures */
function mockKV(opts: { store?: Record<string, string>; failOn?: (key: string) => boolean } = {}) {
  const store = opts.store ?? {};
  const failOn = opts.failOn ?? (() => false);
  const calls: Array<{ op: "get" | "put"; key: string; value?: string }> = [];
  return {
    kv: {
      async get(key: string) {
        calls.push({ op: "get", key });
        if (failOn(key)) throw new Error("mock KV failure");
        return store[key] ?? null;
      },
      async put(key: string, value: string) {
        calls.push({ op: "put", key, value });
        if (failOn(key)) throw new Error("mock KV failure");
        store[key] = value;
      },
    } as any,
    store,
    calls,
  };
}

const TODAY = new Date("2026-05-22T12:00:00Z");
const TOMORROW = new Date("2026-05-23T12:00:00Z");
const DAY = "2026-05-22";

describe("utcDay", () => {
  it("returns YYYY-MM-DD UTC", () => {
    expect(utcDay(TODAY)).toBe("2026-05-22");
    expect(utcDay(TOMORROW)).toBe("2026-05-23");
    // UTC 0:00 边界
    expect(utcDay(new Date("2026-05-22T23:59:59Z"))).toBe("2026-05-22");
    expect(utcDay(new Date("2026-05-23T00:00:01Z"))).toBe("2026-05-23");
  });
});

describe("checkRateLimits — request 类型", () => {
  it("case 1: counter < 阈值 ok", async () => {
    const { kv } = mockKV({
      store: { [`ratelimit:ip:1.2.3.4:${DAY}`]: "5", [`ratelimit:user:abc:${DAY}`]: "10" },
    });
    const result = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_IP_DAILY: "200", RATE_LIMIT_PER_USER_DAILY: "200" },
      "abc",
      "1.2.3.4",
      "request",
      TODAY,
    );
    expect(result).toEqual({ ok: true });
  });

  it("case 2a: IP counter >= 阈值 reject with rate-limit-ip", async () => {
    const { kv } = mockKV({ store: { [`ratelimit:ip:1.2.3.4:${DAY}`]: "200" } });
    const result = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_IP_DAILY: "200" },
      "abc",
      "1.2.3.4",
      "request",
      TODAY,
    );
    expect(result).toEqual({ ok: false, reason: "rate-limit-ip" });
  });

  it("case 2b: user counter >= 阈值 reject with rate-limit-user", async () => {
    const { kv } = mockKV({ store: { [`ratelimit:user:abc:${DAY}`]: "200" } });
    const result = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_USER_DAILY: "200" },
      "abc",
      "1.2.3.4",
      "request",
      TODAY,
    );
    expect(result).toEqual({ ok: false, reason: "rate-limit-user" });
  });

  it("case 3: KV.get 失败 — failure OPEN (返 ok: true, 不阻塞用户)", async () => {
    const { kv } = mockKV({ failOn: () => true });
    const result = await checkRateLimits(
      { GF_RATELIMIT: kv },
      "abc",
      "1.2.3.4",
      "request",
      TODAY,
    );
    expect(result).toEqual({ ok: true });
  });
});

describe("checkRateLimits — llm 类型", () => {
  it("global counter < 阈值, user < 阈值 → ok", async () => {
    const { kv } = mockKV({
      store: { [`llm-quota:global:${DAY}`]: "100", [`llm-quota:user:abc:${DAY}`]: "10" },
    });
    const result = await checkRateLimits(
      { GF_RATELIMIT: kv, LLM_BUDGET_DAILY: "8000", LLM_BUDGET_PER_USER: "50" },
      "abc",
      "1.2.3.4",
      "llm",
      TODAY,
    );
    expect(result).toEqual({ ok: true });
  });

  it("global counter >= 阈值 reject with budget-global", async () => {
    const { kv } = mockKV({ store: { [`llm-quota:global:${DAY}`]: "8000" } });
    const result = await checkRateLimits(
      { GF_RATELIMIT: kv, LLM_BUDGET_DAILY: "8000", LLM_BUDGET_PER_USER: "50" },
      "abc",
      "1.2.3.4",
      "llm",
      TODAY,
    );
    expect(result).toEqual({ ok: false, reason: "budget-global" });
  });

  it("user LLM counter >= 阈值 reject with budget-user", async () => {
    const { kv } = mockKV({ store: { [`llm-quota:user:abc:${DAY}`]: "50" } });
    const result = await checkRateLimits(
      { GF_RATELIMIT: kv, LLM_BUDGET_DAILY: "8000", LLM_BUDGET_PER_USER: "50" },
      "abc",
      "1.2.3.4",
      "llm",
      TODAY,
    );
    expect(result).toEqual({ ok: false, reason: "budget-user" });
  });

  it("case 4: LLM budget KV 失败 — failure CLOSE (返 ok: false 进入降级)", async () => {
    const { kv } = mockKV({ failOn: () => true });
    const result = await checkRateLimits(
      { GF_RATELIMIT: kv, LLM_BUDGET_DAILY: "8000", LLM_BUDGET_PER_USER: "50" },
      "abc",
      "1.2.3.4",
      "llm",
      TODAY,
    );
    expect(result.ok).toBe(false);
    expect((result as any).reason).toBe("budget-global"); // 第一道失败 → budget-global
  });

  it("KV binding 缺失: llm 类型返 failure close", async () => {
    const result = await checkRateLimits({}, "abc", "1.2.3.4", "llm", TODAY);
    expect(result).toEqual({ ok: false, reason: "budget-global" });
  });

  it("KV binding 缺失: request 类型 failure open", async () => {
    const result = await checkRateLimits({}, "abc", "1.2.3.4", "request", TODAY);
    expect(result).toEqual({ ok: true });
  });
});

describe("checkRateLimits — 隔离性 + 日切", () => {
  it("case 5: 不同 user_id 互不影响 (user A 满, user B 仍 ok)", async () => {
    const { kv } = mockKV({ store: { [`ratelimit:user:A:${DAY}`]: "200" } });
    const resultA = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_USER_DAILY: "200" },
      "A",
      "1.2.3.4",
      "request",
      TODAY,
    );
    expect(resultA).toEqual({ ok: false, reason: "rate-limit-user" });

    const resultB = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_USER_DAILY: "200" },
      "B",
      "1.2.3.4",
      "request",
      TODAY,
    );
    expect(resultB).toEqual({ ok: true });
  });

  it("case 6: 不同 IP 互不影响", async () => {
    const { kv } = mockKV({ store: { [`ratelimit:ip:1.1.1.1:${DAY}`]: "200" } });
    const r1 = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_IP_DAILY: "200" },
      "u",
      "1.1.1.1",
      "request",
      TODAY,
    );
    expect(r1).toEqual({ ok: false, reason: "rate-limit-ip" });

    const r2 = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_IP_DAILY: "200" },
      "u",
      "2.2.2.2",
      "request",
      TODAY,
    );
    expect(r2).toEqual({ ok: true });
  });

  it("case 7: UTC 日切 key 不同 (今天满, 明天空)", async () => {
    const { kv } = mockKV({ store: { [`ratelimit:user:u:${DAY}`]: "200" } });
    const today = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_USER_DAILY: "200" },
      "u",
      "1.2.3.4",
      "request",
      TODAY,
    );
    expect(today).toEqual({ ok: false, reason: "rate-limit-user" });

    const tomorrow = await checkRateLimits(
      { GF_RATELIMIT: kv, RATE_LIMIT_PER_USER_DAILY: "200" },
      "u",
      "1.2.3.4",
      "request",
      TOMORROW,
    );
    expect(tomorrow).toEqual({ ok: true });
  });
});

describe("incrementCounter", () => {
  it("从 null 起步 INCR 到 1", async () => {
    const { kv, store } = mockKV();
    await incrementCounter(kv, "test-key");
    expect(store["test-key"]).toBe("1");
  });

  it("从 existing INCR + 1", async () => {
    const { kv, store } = mockKV({ store: { "test-key": "5" } });
    await incrementCounter(kv, "test-key");
    expect(store["test-key"]).toBe("6");
  });

  it("KV.put 失败 silent (不抛)", async () => {
    const { kv } = mockKV({ failOn: () => true });
    await expect(incrementCounter(kv, "test-key")).resolves.toBeUndefined();
  });
});
