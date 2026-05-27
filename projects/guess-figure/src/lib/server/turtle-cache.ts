import type { KVNamespace } from "@cloudflare/workers-types";

export const TURTLE_CACHE_TTL_SEC = 30 * 24 * 60 * 60;

export type TurtleAnswer = "是" | "否" | "无关";

export interface TurtleCacheValue {
  answer: TurtleAnswer;
}

export interface TurtleCacheKeyInput {
  figureId: string;
  normalizedQuestion: string;
  ragIndexVersion: string;
  promptVersion: string;
}

/**
 * 缓存 key 同时受人物、问题 hash、RAG 索引版本和 prompt 版本约束。
 * normalizedQuestion 只入 SHA-256，避免长中文问题超过 Cloudflare KV 512 bytes key 限制。
 */
export async function turtleCacheKey(input: TurtleCacheKeyInput): Promise<string> {
  const questionHash = await sha256Hex(input.normalizedQuestion);

  return [
    "turtle-cache",
    "v1",
    `figure:${encodePart(input.figureId)}`,
    `rag:${encodePart(input.ragIndexVersion)}`,
    `prompt:${encodePart(input.promptVersion)}`,
    `q:${questionHash}`,
  ].join(":");
}

export async function getTurtleCache(
  kv: KVNamespace,
  key: string,
): Promise<TurtleCacheValue | null> {
  try {
    const raw = await kv.get(key);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (!isTurtleCacheValue(parsed)) return null;

    return parsed;
  } catch (e) {
    console.warn(`[turtle-cache] read failed for ${key}:`, e);
    return null;
  }
}

export async function setTurtleCache(
  kv: KVNamespace,
  key: string,
  value: TurtleCacheValue,
  ttlSec: number = TURTLE_CACHE_TTL_SEC,
): Promise<{ ok: boolean }> {
  try {
    await kv.put(key, JSON.stringify(value), { expirationTtl: ttlSec });
    return { ok: true };
  } catch (e) {
    console.warn(`[turtle-cache] write failed for ${key}:`, e);
    return { ok: false };
  }
}

/**
 * cache hit 时直接返回，不调用 resolver。
 * 这让上层可以用 mock 断言 Vectorize / LLM 等后续依赖没有被触发。
 */
export async function getOrResolveTurtleCache(
  kv: KVNamespace,
  key: string,
  resolver: () => Promise<TurtleCacheValue>,
): Promise<{ value: TurtleCacheValue; cacheHit: boolean }> {
  const cached = await getTurtleCache(kv, key);
  if (cached) {
    return { value: cached, cacheHit: true };
  }

  const value = await resolver();
  await setTurtleCache(kv, key, value);
  return { value, cacheHit: false };
}

async function sha256Hex(input: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function encodePart(value: string): string {
  return encodeURIComponent(value);
}

function isTurtleCacheValue(value: unknown): value is TurtleCacheValue {
  if (!value || typeof value !== "object") return false;

  const answer = (value as { answer?: unknown }).answer;
  return answer === "是" || answer === "否" || answer === "无关";
}
