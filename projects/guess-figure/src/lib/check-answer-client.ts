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

// ====================================================================
// 002 T14: 响应分类 + 线索消耗判断
//
// 把 fetch 响应分成 5 个互斥 outcome, 让 callsite (page.svelte) 用 switch 统一处理.
// SPEC G7: 仅 wrong 才消耗线索; correct / degraded / network_error / client_error 都不消耗.
// SPEC AC8 / AC9 / AC22 的核心.
// ====================================================================

export type CheckAnswerOutcome =
  /** server 判正确 — 调 game.markWon() */
  | { kind: "correct"; reason: string; cached?: boolean }
  /** server 判错 (无 degraded / network_error 标志) — 调 game.consumeOnWrongAnswer() */
  | { kind: "wrong"; reason: string }
  /** V (日全局) / X (单 user 日) 配额触发降级 — 不消耗线索, 提示用户改输精确答案 */
  | { kind: "degraded"; reason: string }
  /** LLM 子调用失败 (云雾超时 / 5xx) — 不消耗线索, 提示重试 */
  | { kind: "network_error"; reason: string }
  /** client 层 fetch 自身失败 (HTTP 5xx 或网络断) — 不消耗线索, 提示重试 */
  | { kind: "client_error"; reason: string };

/** 把 fetch 结果归类为单一互斥的 outcome */
export function classifyResult(
  result: CheckAnswerResult | CheckAnswerError,
): CheckAnswerOutcome {
  if ("ok" in result) {
    return { kind: "client_error", reason: result.error };
  }
  if (result.network_error) {
    return { kind: "network_error", reason: result.reason };
  }
  if (result.degraded) {
    return { kind: "degraded", reason: result.reason };
  }
  if (result.correct) {
    return { kind: "correct", reason: result.reason, cached: result.cached };
  }
  return { kind: "wrong", reason: result.reason };
}

/** SPEC G7: 仅 "wrong" outcome 应消耗线索. 其他 4 种均不消耗. */
export function shouldConsumeClue(outcome: CheckAnswerOutcome): boolean {
  return outcome.kind === "wrong";
}
