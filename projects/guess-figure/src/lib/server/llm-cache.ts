// 002 T8: LLM 结果缓存 (KV GF_LLM_CACHE)
//
// SPEC v1.0:
//   - G3 缓存复用: 同 (figure_id, aliases_hash, normalized_input) 30 天内不调 LLM
//   - C5 cache key 含 aliases hash, figure aliases 改后自动失效 (Q9 grill 出来的关键修正)
//
// Cache key 格式:
//   llm-cache:v1:<figure_id>:<sha256(aliases.sort().join("|"))>:<sha256(normalized_input)>
//
// Cache value: { correct: boolean, reason: string }

import type { KVNamespace } from "@cloudflare/workers-types";

const CACHE_TTL_SEC = 30 * 24 * 60 * 60; // 30 天 (SPEC G3)

export interface CacheValue {
  correct: boolean;
  reason: string;
}

/** SHA-256 of UTF-8 string, hex 编码 */
async function sha256Hex(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * 构造 cache key (异步, 因 sha256 是 async).
 *
 * 设计:
 *   - figure_id 前缀: 不同 figure 隔离 (避免误命中)
 *   - aliases_hash: aliases 改 → key 改 → 旧 cache 自然失效 (Q9 关键)
 *     注意排序 + 用 | 分隔 (避免 ["A","BC"] 与 ["AB","C"] 撞 key)
 *   - normalized_input hash: 用 sha256 防 key 过长 / 含非法字符
 *   - "v1" 版本前缀: 未来 normalize 升级时换 v2, 老 cache 整体失效
 */
export async function cacheKey(
  figure_id: string,
  aliases: string[],
  normalizedInput: string,
): Promise<string> {
  const aliasesSorted = [...aliases].sort().join("|");
  const aliasesHash = await sha256Hex(aliasesSorted);
  const inputHash = await sha256Hex(normalizedInput);
  return `llm-cache:v1:${figure_id}:${aliasesHash}:${inputHash}`;
}

/**
 * 读 cache. 若 key 不存在或 value 非法 JSON 返 null.
 * KV.get 失败时也返 null (failure open, 走 LLM 兜底).
 */
export async function cacheGet(
  kv: KVNamespace,
  key: string,
): Promise<CacheValue | null> {
  try {
    const raw = await kv.get(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed.correct !== "boolean" || typeof parsed.reason !== "string") {
      return null;
    }
    return { correct: parsed.correct, reason: parsed.reason };
  } catch (e) {
    console.warn(`[llm-cache] read failed for ${key}:`, e);
    return null;
  }
}

/**
 * 写 cache, TTL 30 天.
 * KV.put 失败 silent (best-effort, 不阻塞响应). 返 true/false 供日志/测试用.
 */
export async function cacheSet(
  kv: KVNamespace,
  key: string,
  value: CacheValue,
  ttlSec: number = CACHE_TTL_SEC,
): Promise<{ ok: boolean }> {
  try {
    await kv.put(key, JSON.stringify(value), { expirationTtl: ttlSec });
    return { ok: true };
  } catch (e) {
    console.warn(`[llm-cache] write failed for ${key}:`, e);
    return { ok: false };
  }
}
