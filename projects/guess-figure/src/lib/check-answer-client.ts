// 002 T10: 改 body schema, 从 {target: {name, aliases}} 改为 {figure_id}
// (server 按 figure_id 从 figures.json 查 aliases — 不再信任 client 传 target)
//
// 用法（在 +page.svelte）— callsite 传 figure 不变, 内部只用 .id:
//   const r = await checkAnswerViaLLM(text, game.figure);
//   if ('correct' in r) { ... }

import type { Figure } from "./types";

export interface CheckAnswerResult {
  correct: boolean;
  reason: string;
  /** T11: KV 缓存命中 (响应延迟 < 200ms) */
  cached?: boolean;
  /** T11: V/X 配额触发降级模式 (前端不消耗线索, 仅接受精确答案) */
  degraded?: boolean;
  /** T11: LLM 网络/超时失败 (前端不消耗线索, 提示重试) */
  network_error?: boolean;
}

export interface CheckAnswerError {
  ok: false;
  error: string;
}

/**
 * 调 /api/check-answer (server 端 normalize → match-exact → KV cache → LLM).
 *
 * 返回 CheckAnswerResult (API 成功, 含 cached/degraded/network_error 可选 flag)
 *   或 CheckAnswerError (HTTP 5xx / 客户端网络异常 — 注意与 result.network_error 不同,
 *   后者是 server 成功响应但 LLM 子调用挂了; 前者是 fetch 本身挂了).
 *
 * 上层判断 `'correct' in result` 区分.
 */
export async function checkAnswerViaLLM(
  input: string,
  figure: Pick<Figure, "id">,
): Promise<CheckAnswerResult | CheckAnswerError> {
  try {
    const r = await fetch("/api/check-answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input, figure_id: figure.id }),
    });
    if (!r.ok) {
      const errText = await r.text();
      return { ok: false, error: `HTTP ${r.status}: ${errText.slice(0, 200)}` };
    }
    const data = (await r.json()) as CheckAnswerResult;
    return data;
  } catch (e) {
    return { ok: false, error: `网络错误: ${e instanceof Error ? e.message : String(e)}` };
  }
}
