// T9: LLM 模糊匹配 client（前端调 /api/check-answer）
//
// 用法（在 +page.svelte）:
//   const r = await checkAnswerViaLLM(text, { name, aliases });
//   if (r.correct) { ... }

import type { Figure } from "./types";

export interface CheckAnswerResult {
  correct: boolean;
  reason: string;
}

export interface CheckAnswerError {
  ok: false;
  error: string;
}

/**
 * 调 /api/check-answer（LLM 模糊匹配）。
 *
 * 返回 { correct, reason }（API 成功）或 { ok: false, error }（HTTP / 网络错）。
 * 上层判断 `'correct' in result` 区分。
 */
export async function checkAnswerViaLLM(
  input: string,
  figure: Pick<Figure, "name" | "aliases">,
): Promise<CheckAnswerResult | CheckAnswerError> {
  try {
    const r = await fetch("/api/check-answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input,
        target: { name: figure.name, aliases: figure.aliases },
      }),
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
