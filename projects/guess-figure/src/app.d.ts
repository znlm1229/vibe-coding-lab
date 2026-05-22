// See https://svelte.dev/docs/kit/types#app
import type { D1Database, KVNamespace } from "@cloudflare/workers-types";

declare global {
  namespace App {
    // 由 src/hooks.server.ts 在 /api/* 请求时填充 (002 T6)
    interface Locals {
      user_id: string;
    }

    interface Platform {
      env?: {
        // === 001 (现有 LLM 调用) ===
        YUNWU_API_KEY?: string;
        YUNWU_BASE_URL?: string;
        LLM_MODEL?: string;

        // === 002 限流 / LLM 预算 env vars (SPEC C3) ===
        LLM_BUDGET_DAILY?: string;          // 默认 "8000"; Stage 3 实测 ¥0.000526/call → ¥4.2/天
        LLM_BUDGET_PER_USER?: string;       // 默认 "50"
        RATE_LIMIT_PER_IP_DAILY?: string;   // 默认 "200"
        RATE_LIMIT_PER_USER_DAILY?: string; // 默认 "200"
        AUTH_HMAC_SECRET?: string;          // cookie HMAC 密钥 (SPEC C4)

        // === 002 bindings ===
        GF_DB?: D1Database;                 // users + games 表 (T1)
        GF_RATELIMIT?: KVNamespace;         // 限流计数器 (T2)
        GF_LLM_CACHE?: KVNamespace;         // LLM 结果缓存 (T2)
      };
    }
  }
}

export {};
