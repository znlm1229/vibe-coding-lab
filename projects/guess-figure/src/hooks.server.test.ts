// 002 T6: hooks.server.ts 单元测试
//
// 测试策略 (限于 SvelteKit hook 的"框架内函数"性质):
//   - 直接 import handle 函数, mock event 与 resolve
//   - 验证 /api/* path 调 getUserId + 挂 locals + append Set-Cookie
//   - 验证非 /api/ 路径不调 getUserId 直接 resolve
//   - 完整集成测试 (curl localhost:5173/api/daily) 留 Stage 8 人工 (AC1)

import { describe, it, expect, vi, beforeEach } from "vitest";
import { handle } from "./hooks.server";
import * as auth from "$lib/server/auth";

const TEST_SECRET = "test-secret-32-char-aaaaaaaaaaaa";

/** 构造一个最小 mock D1Database */
function mockD1() {
  return {
    prepare() {
      return {
        bind() {
          return { async run() { return { success: true }; } };
        },
      };
    },
  } as unknown as App.Platform extends infer P ? P : never;
}

/** 构造一个最小 mock RequestEvent (覆盖 hook 用到的字段) */
function mockEvent(opts: {
  pathname: string;
  cookie?: string;
  platformEnv?: App.Platform["env"];
}): Parameters<typeof handle>[0]["event"] {
  const headers = new Headers();
  if (opts.cookie) headers.set("cookie", opts.cookie);
  return {
    url: new URL(`https://test.local${opts.pathname}`),
    request: new Request(`https://test.local${opts.pathname}`, { headers }),
    locals: {} as App.Locals,
    platform: opts.platformEnv ? { env: opts.platformEnv } : undefined,
  } as unknown as Parameters<typeof handle>[0]["event"];
}

describe("hooks.server handle", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("非 /api/ 路径不调 getUserId, 直接 resolve", async () => {
    const event = mockEvent({ pathname: "/" });
    const resolveSpy = vi.fn(async () => new Response("page", { status: 200 }));
    const getUserIdSpy = vi.spyOn(auth, "getUserId");

    const response = await handle({ event, resolve: resolveSpy } as any);

    expect(resolveSpy).toHaveBeenCalledOnce();
    expect(getUserIdSpy).not.toHaveBeenCalled();
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("/api/* 路径调 getUserId + 挂 locals + append Set-Cookie", async () => {
    const event = mockEvent({
      pathname: "/api/daily",
      platformEnv: { AUTH_HMAC_SECRET: TEST_SECRET, GF_DB: mockD1() as any },
    });
    const resolveSpy = vi.fn(async () => new Response("data", { status: 200 }));
    const getUserIdSpy = vi.spyOn(auth, "getUserId").mockResolvedValue({
      user_id: "abc-user-id",
      set_cookie: "gf_uid=abc-user-id.hmac; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=31536000",
    });

    const response = await handle({ event, resolve: resolveSpy } as any);

    expect(getUserIdSpy).toHaveBeenCalledOnce();
    expect((event.locals as App.Locals).user_id).toBe("abc-user-id");
    expect(response.headers.get("set-cookie")).toContain("gf_uid=abc-user-id.");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=31536000");
  });

  it("/api/* 但 platform.env 缺失 (vite dev fallback): 给 dev-no-platform-stub user_id", async () => {
    const event = mockEvent({ pathname: "/api/daily" /* no platformEnv */ });
    const resolveSpy = vi.fn(async () => new Response("data", { status: 200 }));

    const response = await handle({ event, resolve: resolveSpy } as any);

    expect((event.locals as App.Locals).user_id).toBe("dev-no-platform-stub");
    expect(response.status).toBe(200);
  });

  it("/api/* 但 getUserId 抛错 (SPEC C4 deployment error): 返 500", async () => {
    const event = mockEvent({
      pathname: "/api/daily",
      platformEnv: { GF_DB: mockD1() as any /* 故意不给 secret */ },
    });
    const resolveSpy = vi.fn(async () => new Response("data"));
    vi.spyOn(auth, "getUserId").mockRejectedValue(new Error("AUTH_HMAC_SECRET 未配置"));

    const response = await handle({ event, resolve: resolveSpy } as any);

    expect(response.status).toBe(500);
    const text = await response.text();
    expect(text).toContain("AUTH_HMAC_SECRET 未配置");
    expect(resolveSpy).not.toHaveBeenCalled(); // 不到 endpoint
  });
});
