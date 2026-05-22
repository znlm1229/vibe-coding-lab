// 002 T7: 限流 + LLM 预算检查 (KV 计数器)
//
// SPEC v1.0:
//   - G1 钱袋子: V 日全局 LLM 预算 8000 (env LLM_BUDGET_DAILY)
//   - G2 单点抗刷: X 单 user 日 LLM 上限 50 (env LLM_BUDGET_PER_USER)
//   - G6 入口防滥用: P (dashboard) + Q (本文件) 双层; 单 IP 日 200 + 单 user 日 200
//   - C8 failure open (限流 KV 不可用) / failure close (LLM 预算 KV 不可用进入降级)
//
// KV key 形态:
//   - ratelimit:ip:<ip>:<UTC日>          - 单 IP 日总请求计数
//   - ratelimit:user:<uid>:<UTC日>       - 单 user 日总请求计数
//   - llm-quota:global:<UTC日>           - 全站日 LLM 调用计数
//   - llm-quota:user:<uid>:<UTC日>       - 单 user 日 LLM 调用计数

import type { KVNamespace } from "@cloudflare/workers-types";

const COUNTER_TTL_SEC = 26 * 60 * 60; // 26h, 跨 UTC 0:00 切换留 buffer

interface RateLimitEnv {
  GF_RATELIMIT?: KVNamespace;
  RATE_LIMIT_PER_IP_DAILY?: string;
  RATE_LIMIT_PER_USER_DAILY?: string;
  LLM_BUDGET_DAILY?: string;
  LLM_BUDGET_PER_USER?: string;
}

export type RateLimitReason =
  | "rate-limit-ip"
  | "rate-limit-user"
  | "budget-global"
  | "budget-user";

export type RateLimitResult =
  | { ok: true }
  | { ok: false; reason: RateLimitReason };

/** 返 UTC 日字符串 YYYY-MM-DD (SPEC G1 全局预算按 UTC 日窗口) */
export function utcDay(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

function parseLimit(value: string | undefined, defaultValue: number): number {
  if (!value) return defaultValue;
  const n = parseInt(value, 10);
  return Number.isFinite(n) && n > 0 ? n : defaultValue;
}

/** 安全读 KV: 若读失败返回 null (failure open 主 path), 调用方自己决定后续 */
async function safeKvGet(kv: KVNamespace, key: string): Promise<string | null> {
  try {
    return await kv.get(key);
  } catch (e) {
    console.warn(`[rate-limit] KV read failed for ${key}:`, e);
    return null;
  }
}

/**
 * 限流检查 — 在 endpoint 入口调用.
 *
 * @param kind
 *   - "request": 检查 IP + user 的日总请求上限 (RATE_LIMIT_PER_IP_DAILY / _USER_DAILY)
 *   - "llm": 检查 LLM 全局 + LLM 单 user 的日预算 (LLM_BUDGET_DAILY / _PER_USER)
 *
 * 返回:
 *   - {ok: true}: 通过, 调用方可继续
 *   - {ok: false, reason}: 超限, 调用方按 reason 决定 UX
 *     (rate-limit-* → 429; budget-* → 降级 degraded: true)
 *
 * C8 strategy:
 *   - "request" 类型: KV 读失败 → failure open (返 ok: true, 不阻塞用户)
 *   - "llm" 类型: KV 读失败 → failure close (返 ok: false reason="budget-global",
 *     防 LLM 无限调用烧钱)
 */
export async function checkRateLimits(
  env: RateLimitEnv,
  user_id: string,
  ip: string,
  kind: "request" | "llm",
  now: Date = new Date(),
): Promise<RateLimitResult> {
  const kv = env.GF_RATELIMIT;
  if (!kv) {
    // binding 缺失视作 deployment error; failure close for LLM, failure open for request
    return kind === "llm" ? { ok: false, reason: "budget-global" } : { ok: true };
  }

  const day = utcDay(now);

  if (kind === "request") {
    const ipLimit = parseLimit(env.RATE_LIMIT_PER_IP_DAILY, 200);
    const userLimit = parseLimit(env.RATE_LIMIT_PER_USER_DAILY, 200);

    const ipCount = parseInt((await safeKvGet(kv, `ratelimit:ip:${ip}:${day}`)) ?? "0", 10);
    if (ipCount >= ipLimit) return { ok: false, reason: "rate-limit-ip" };

    const userCount = parseInt(
      (await safeKvGet(kv, `ratelimit:user:${user_id}:${day}`)) ?? "0",
      10,
    );
    if (userCount >= userLimit) return { ok: false, reason: "rate-limit-user" };

    return { ok: true };
  }

  // kind === "llm"
  const globalLimit = parseLimit(env.LLM_BUDGET_DAILY, 8000);
  const userLimit = parseLimit(env.LLM_BUDGET_PER_USER, 50);

  // failure close: 若 KV 不可用, 视作"已达上限"进入降级 (防止 LLM 无限调用)
  let globalRaw: string | null;
  try {
    globalRaw = await kv.get(`llm-quota:global:${day}`);
  } catch {
    return { ok: false, reason: "budget-global" };
  }
  const globalCount = parseInt(globalRaw ?? "0", 10);
  if (globalCount >= globalLimit) return { ok: false, reason: "budget-global" };

  let userRaw: string | null;
  try {
    userRaw = await kv.get(`llm-quota:user:${user_id}:${day}`);
  } catch {
    return { ok: false, reason: "budget-user" };
  }
  const userCount = parseInt(userRaw ?? "0", 10);
  if (userCount >= userLimit) return { ok: false, reason: "budget-user" };

  return { ok: true };
}

/**
 * INCR 一个计数器 (read-modify-write).
 * KV 没有原生 INCR; 用 GET + PUT 实现. 并发 race 可能少计 1-2 (SPEC C8 接受).
 *
 * 写失败 silent (不抛, 不阻塞调用方); 限流结果可能轻微偏差但不影响 UX.
 */
export async function incrementCounter(
  kv: KVNamespace,
  key: string,
  ttlSec: number = COUNTER_TTL_SEC,
): Promise<void> {
  try {
    const current = parseInt((await kv.get(key)) ?? "0", 10);
    await kv.put(key, String(current + 1), { expirationTtl: ttlSec });
  } catch (e) {
    console.warn(`[rate-limit] INCR failed for ${key}:`, e);
  }
}

/** 便捷: 一次 INCR 请求计数器 (IP + user) */
export async function incrementRequestCounters(
  kv: KVNamespace,
  user_id: string,
  ip: string,
  now: Date = new Date(),
): Promise<void> {
  const day = utcDay(now);
  await Promise.all([
    incrementCounter(kv, `ratelimit:ip:${ip}:${day}`),
    incrementCounter(kv, `ratelimit:user:${user_id}:${day}`),
  ]);
}

/** 便捷: 一次 INCR LLM 调用计数器 (global + user) */
export async function incrementLlmCounters(
  kv: KVNamespace,
  user_id: string,
  now: Date = new Date(),
): Promise<void> {
  const day = utcDay(now);
  await Promise.all([
    incrementCounter(kv, `llm-quota:global:${day}`),
    incrementCounter(kv, `llm-quota:user:${user_id}:${day}`),
  ]);
}
