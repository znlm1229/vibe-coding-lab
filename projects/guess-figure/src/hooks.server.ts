// 002 T6: 全局 server hook — 对所有 /api/* 请求做 cookie 鉴权 + 滚动续期
//
// SPEC v1.0 B1: 调 getUserId(request, env) → 挂 event.locals.user_id → append Set-Cookie
// SPEC C4: AUTH_HMAC_SECRET 未配置时返 500 + 日志
// SPEC C8: failure open 策略 (但 secret 缺失是 deployment error, 应该挂)

import type { Handle } from "@sveltejs/kit";
import { getUserId } from "$lib/server/auth";

export const handle: Handle = async ({ event, resolve }) => {
  // 仅对 /api/* 路径处理鉴权 (静态资源 / SSR 页面不需要)
  if (event.url.pathname.startsWith("/api/")) {
    const env = event.platform?.env;

    if (!env) {
      // local vite dev 模式下 event.platform 是 undefined (CF runtime 未加载)
      // 用 wrangler pages dev 跑才能完整测试; 此 fallback 仅给 SvelteKit `pnpm dev` 用
      event.locals.user_id = "dev-no-platform-stub";
      return resolve(event);
    }

    let userIdResult;
    try {
      userIdResult = await getUserId(event.request, env);
    } catch (e) {
      // SPEC C4: AUTH_HMAC_SECRET 未配置 / D1 binding 缺失 — deployment error
      console.error("[auth hook] error:", e);
      return new Response(
        e instanceof Error ? `Server misconfigured: ${e.message}` : "Server misconfigured",
        { status: 500 },
      );
    }

    event.locals.user_id = userIdResult.user_id;
    const response = await resolve(event);
    response.headers.append("Set-Cookie", userIdResult.set_cookie);
    return response;
  }

  return resolve(event);
};
