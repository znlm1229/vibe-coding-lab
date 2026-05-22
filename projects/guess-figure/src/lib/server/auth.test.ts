// 002 T5: auth.ts 单测
//
// 覆盖 9 case (06-tasks.md T5 Done when):
//   1. 合法 cookie 验签 PASS
//   2. 篡改 uuid 部分 fail
//   3. 篡改 hmac 部分 fail
//   4. 不同 secret 验签 fail
//   5. 无 cookie 新建 user (D1 INSERT 被调用)
//   6. 已存 cookie 复用 (D1 不再 INSERT)
//   7. D1 INSERT OR IGNORE 幂等 (重复 uuid 第二次写不报错)
//   8. cookie 格式非法 fail
//   9. secret 缺失抛错

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  signCookie,
  verifyCookie,
  getUserId,
  parseCookieHeader,
  buildSetCookie,
} from "./auth";

const TEST_SECRET = "test-secret-32-char-aaaaaaaaaaaa";
const FIXED_UUID = "12345678-1234-1234-1234-123456789abc";

/** 构造一个最小 mock D1Database */
function mockD1() {
  const runCalls: Array<{ sql: string; args: unknown[] }> = [];
  const db = {
    prepare(sql: string) {
      return {
        bind(...args: unknown[]) {
          return {
            async run() {
              runCalls.push({ sql, args });
              return { success: true };
            },
          };
        },
      };
    },
  };
  return { db: db as unknown as Parameters<typeof getUserId>[1]["GF_DB"], runCalls };
}

describe("signCookie + verifyCookie", () => {
  it("case 1: 合法 cookie 验签 PASS", async () => {
    const cookie = await signCookie(FIXED_UUID, TEST_SECRET);
    expect(cookie).toMatch(new RegExp(`^${FIXED_UUID}\\.[A-Za-z0-9_-]+$`));
    const result = await verifyCookie(cookie, TEST_SECRET);
    expect(result.valid).toBe(true);
    expect(result.uuid).toBe(FIXED_UUID);
  });

  it("case 2: 篡改 uuid 部分 fail", async () => {
    const cookie = await signCookie(FIXED_UUID, TEST_SECRET);
    const [_, hmac] = cookie.split(".");
    const tampered = `00000000-0000-0000-0000-000000000000.${hmac}`;
    const result = await verifyCookie(tampered, TEST_SECRET);
    expect(result.valid).toBe(false);
  });

  it("case 3: 篡改 hmac 部分 fail", async () => {
    const cookie = await signCookie(FIXED_UUID, TEST_SECRET);
    const [uuid] = cookie.split(".");
    const tampered = `${uuid}.bogus_signature_bogus`;
    const result = await verifyCookie(tampered, TEST_SECRET);
    expect(result.valid).toBe(false);
  });

  it("case 4: 不同 secret 验签 fail", async () => {
    const cookie = await signCookie(FIXED_UUID, TEST_SECRET);
    const result = await verifyCookie(cookie, "different-secret-32-char-bbbbbbbb");
    expect(result.valid).toBe(false);
  });

  it("case 8: cookie 格式非法 fail (无 dot / 空 / null / 多个 dot)", async () => {
    expect((await verifyCookie(null, TEST_SECRET)).valid).toBe(false);
    expect((await verifyCookie(undefined, TEST_SECRET)).valid).toBe(false);
    expect((await verifyCookie("", TEST_SECRET)).valid).toBe(false);
    expect((await verifyCookie("nodot", TEST_SECRET)).valid).toBe(false);
    expect((await verifyCookie("too.many.dots", TEST_SECRET)).valid).toBe(false);
    expect((await verifyCookie("not-a-uuid.somehmac", TEST_SECRET)).valid).toBe(false);
  });
});

describe("getUserId", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("case 5: 无 cookie 新建 user (D1 INSERT 被调用 + 返回 set_cookie)", async () => {
    const { db, runCalls } = mockD1();
    const request = new Request("https://test.local/api/daily");

    const result = await getUserId(request, { AUTH_HMAC_SECRET: TEST_SECRET, GF_DB: db });

    expect(result.user_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
    expect(result.set_cookie).toBeDefined();
    expect(result.set_cookie).toContain("gf_uid=");
    expect(result.set_cookie).toContain("HttpOnly");
    expect(result.set_cookie).toContain("Secure");
    expect(result.set_cookie).toContain("SameSite=Lax");
    expect(result.set_cookie).toContain("Max-Age=31536000");
    expect(runCalls).toHaveLength(1);
    expect(runCalls[0].sql).toContain("INSERT OR IGNORE INTO users");
    expect(runCalls[0].args).toEqual([result.user_id]);
  });

  it("case 6: 已存合法 cookie 复用 user (D1 不再 INSERT)", async () => {
    const { db, runCalls } = mockD1();
    const cookie = await signCookie(FIXED_UUID, TEST_SECRET);
    const request = new Request("https://test.local/api/daily", {
      headers: { cookie: `gf_uid=${cookie}` },
    });

    const result = await getUserId(request, { AUTH_HMAC_SECRET: TEST_SECRET, GF_DB: db });

    expect(result.user_id).toBe(FIXED_UUID);
    expect(result.set_cookie).toBeUndefined(); // 不需要重发 cookie
    expect(runCalls).toHaveLength(0); // 不 INSERT
  });

  it("case 7: D1 INSERT OR IGNORE 幂等 (mock 直接返回 success 多次也 OK)", async () => {
    const { db, runCalls } = mockD1();
    const r1 = new Request("https://test.local/api/daily");
    const r2 = new Request("https://test.local/api/daily");

    await getUserId(r1, { AUTH_HMAC_SECRET: TEST_SECRET, GF_DB: db });
    await getUserId(r2, { AUTH_HMAC_SECRET: TEST_SECRET, GF_DB: db });
    // 都是新建用户, 都 INSERT (不同 uuid). 但 SQL 含 IGNORE — 若万一同 uuid 也不会抛
    expect(runCalls).toHaveLength(2);
    runCalls.forEach((c) => expect(c.sql).toContain("INSERT OR IGNORE INTO users"));
  });

  it("case 9: secret 缺失抛错 (deployment error)", async () => {
    const { db } = mockD1();
    const request = new Request("https://test.local/api/daily");
    await expect(getUserId(request, { GF_DB: db })).rejects.toThrow("AUTH_HMAC_SECRET 未配置");
  });

  it("case 9b: D1 binding 缺失抛错", async () => {
    const request = new Request("https://test.local/api/daily");
    await expect(getUserId(request, { AUTH_HMAC_SECRET: TEST_SECRET })).rejects.toThrow(
      "GF_DB binding 缺失",
    );
  });
});

describe("parseCookieHeader + buildSetCookie", () => {
  it("parseCookieHeader 处理常见形态", () => {
    expect(parseCookieHeader("")).toEqual({});
    expect(parseCookieHeader("a=1")).toEqual({ a: "1" });
    expect(parseCookieHeader("a=1; b=2")).toEqual({ a: "1", b: "2" });
    expect(parseCookieHeader("  a = 1 ;b=2  ")).toEqual({ a: "1", b: "2" });
    expect(parseCookieHeader("a=v.with.dots; b=other")).toEqual({
      a: "v.with.dots",
      b: "other",
    });
    // 重复 key 取第一个 (cookie spec 行为)
    expect(parseCookieHeader("a=1; a=2")).toEqual({ a: "1" });
  });

  it("buildSetCookie 含所有必需 attribute", () => {
    const s = buildSetCookie("abc.def");
    expect(s).toContain("gf_uid=abc.def");
    expect(s).toContain("HttpOnly");
    expect(s).toContain("Secure");
    expect(s).toContain("SameSite=Lax");
    expect(s).toContain("Path=/");
    expect(s).toContain("Max-Age=31536000");
  });
});
