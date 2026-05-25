// 002 T10+T11: /api/check-answer 完整 pipeline 改造
//
// 现状(001) → 002 改造:
//   - body 从 {input, target: {name, aliases}} 改为 {input, figure_id}
//   - server 按 figure_id 查 figures.json 拿 aliases (不信任 client 传 target)
//   - server 跑 normalize + matchExactly 短路 (T10)
//   - 加 KV 限流 (request 类 IP+user) + LLM 缓存查 + LLM 预算检查 + LLM 调用 + INCR 计数器 (T11)
//   - 响应增字段: cached / degraded / network_error
//
// pipeline 顺序 (SPEC v1.0 B2):
//   1. 限流检查 (request kind) → 429 if 超
//   2. server normalize + matchExactly 短路 → {correct:true, reason:"精确匹配"}
//   3. LLM 缓存查 → 命中 → {...cached_value, cached:true}
//   4. LLM 预算检查 (llm kind) → 超 → {correct:false, reason:..., degraded:true}
//   5. 调 LLM (现有 try/catch + JSON 容错保留)
//   6. LLM 失败 → {correct:false, reason:..., network_error:true} (不 INCR 计数)
//   7. LLM 成功 → INCR LLM counters + 写 cache + 返响应
//
// 全程: INCR request counters (IP + user) 在 endpoint 入口后立即做 (不阻塞响应路径).

import { json, error } from "@sveltejs/kit";
import { env } from "$env/dynamic/private";
import figures from "$lib/data/figures.json";
import type { Figure } from "$lib/types";
import { normalize, matchExactly } from "$lib/match-exact";
import { cacheGet, cacheSet, cacheKey } from "$lib/server/llm-cache";
import {
  checkRateLimits,
  incrementLlmCounters,
  incrementRequestCounters,
} from "$lib/server/rate-limit";
import type { RequestHandler } from "./$types";

// V/X 触发时的降级文案 (SPEC OQ2 — taste 类, 用户应自行替换)
const DEGRADED_REASON_GLOBAL = "今日 AI 裁判额度已用尽，仅接受精确答案（含异称）";
const DEGRADED_REASON_USER = "你今日 AI 裁判额度已用完，仅接受精确答案（含异称）";
// LLM 失败文案 (SPEC OQ3 — taste 类)
const NETWORK_ERROR_REASON = "AI 响应异常，请稍后重试";

export const POST: RequestHandler = async ({ request, locals, platform, getClientAddress }) => {
  // 输入解析
  const body = (await request.json()) as { input?: string; figure_id?: string };
  const inputRaw = body.input?.trim();
  const figureId = body.figure_id?.trim();
  if (!inputRaw) throw error(400, "input 必填");
  if (!figureId) throw error(400, "figure_id 必填");

  // 查 figure (题库内不存在 → 400)
  const figure = (figures as Figure[]).find((f) => f.id === figureId);
  if (!figure) throw error(400, `figure_id 不存在: ${figureId}`);

  const cfEnv = platform?.env;
  const userId = locals.user_id;
  const ip = getClientAddress();

  // 1. 限流检查 (request kind) — 任一超返 429
  if (cfEnv) {
    const limitResult = await checkRateLimits(cfEnv, userId, ip, "request");
    if (!limitResult.ok) {
      throw error(429, `请求过于频繁 (${limitResult.reason})`);
    }
    // INCR request counters (fire-and-forget, 不阻塞响应路径)
    if (cfEnv.GF_RATELIMIT) {
      incrementRequestCounters(cfEnv.GF_RATELIMIT, userId, ip).catch(() => {
        // silent — failure open (SPEC C8)
      });
    }
  }

  // 2. server normalize + match-exact 短路 (T10) — 不调 LLM, 不写缓存, 不增 LLM 计数
  const normalized = normalize(inputRaw);
  if (matchExactly(inputRaw, figure)) {
    return json({ correct: true, reason: "精确匹配" });
  }

  // 3. LLM 缓存查
  if (cfEnv?.GF_LLM_CACHE) {
    const key = await cacheKey(figure.id, figure.aliases, normalized);
    const cached = await cacheGet(cfEnv.GF_LLM_CACHE, key);
    if (cached) {
      return json({ ...cached, cached: true });
    }
  }

  // 4. LLM 预算检查
  if (cfEnv) {
    const budgetResult = await checkRateLimits(cfEnv, userId, ip, "llm");
    if (!budgetResult.ok) {
      const reason =
        budgetResult.reason === "budget-global" ? DEGRADED_REASON_GLOBAL : DEGRADED_REASON_USER;
      return json({ correct: false, reason, degraded: true });
    }
  }

  // 5. 调 LLM (沿用 001 现有代码, 仅保留)
  const apiKey = env.YUNWU_API_KEY;
  const baseUrlRaw = env.YUNWU_BASE_URL ?? "https://yunwu.ai/v1";
  const model = env.LLM_MODEL ?? "gemini-3.1-flash-lite";
  if (!apiKey) throw error(500, "缺 YUNWU_API_KEY 环境变量");

  const baseUrl = baseUrlRaw.replace(/\/+$/, "");
  const url = baseUrl.endsWith("/v1") ? `${baseUrl}/chat/completions` : `${baseUrl}/v1/chat/completions`;

  const prompt = `你是历史人物姓名识别助手。判断用户输入是否在指代目标人物。

目标人物：${figure.name}
已知异称（字 / 号 / 谥号 / 庙号 / 别号）：${figure.aliases.join("、")}

用户输入："${inputRaw}"

判定规则：
- 用户输入是本名 / 字 / 号 / 谥号 / 庙号 / 别号 → YES
- 用户输入是异称的常见组合或简写（如"诸葛丞相"指诸葛亮、"曹孟德"指曹操）→ YES
- 用户输入仅是姓氏（如"诸葛"）→ NO（太宽泛）
- 用户输入仅是单名（如"亮"）→ NO（信息不足）
- 用户输入是错别字 → NO（不容忍错字）
- 不确定 → NO

请严格输出 JSON：{"correct": true|false, "reason": "<一句话理由>"}
不要任何 markdown 代码块标记或额外说明文字。`;

  let llmResp: Response;
  try {
    llmResp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: prompt }],
        temperature: 0.1,
        max_tokens: 300,
      }),
      signal: AbortSignal.timeout(10_000),
    });
  } catch (e) {
    // 6. 网络/超时失败 — 返 network_error: true, 不 INCR LLM 计数 (云雾失败不扣)
    return json({
      correct: false,
      reason: NETWORK_ERROR_REASON,
      network_error: true,
    });
  }

  if (!llmResp.ok) {
    const errText = await llmResp.text();
    // HTTP 5xx 也算 network_error (云雾服务异常, 用户不该被扣线索)
    return json({
      correct: false,
      reason: `${NETWORK_ERROR_REASON} (HTTP ${llmResp.status})`,
      network_error: true,
    });
  }

  const data = (await llmResp.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  let content = data.choices?.[0]?.message?.content?.trim() ?? "";

  // 容错 1: 剥 markdown 代码块
  if (content.startsWith("```")) {
    const parts = content.split("```");
    if (parts.length >= 2) {
      content = parts[1];
      if (content.startsWith("json")) content = content.slice(4);
      content = content.trim();
    }
  }
  // 容错 2: 抠首个 {...} 块
  if (!content.startsWith("{")) {
    const m = content.match(/\{[\s\S]*\}/);
    if (m) content = m[0];
  }

  let llmResult: { correct: boolean; reason: string };
  try {
    const parsed = JSON.parse(content);
    llmResult = {
      correct: !!parsed.correct,
      reason: String(parsed.reason ?? ""),
    };
  } catch {
    // LLM 返非 JSON 兜底 — 视作 false 但不是 network_error (是 LLM 内容错误)
    llmResult = {
      correct: false,
      reason: `LLM 返回无法解析：${content.slice(0, 100)}`,
    };
  }

  // 7. LLM 成功 — INCR LLM counters + 写缓存 (fire-and-forget)
  if (cfEnv?.GF_RATELIMIT) {
    incrementLlmCounters(cfEnv.GF_RATELIMIT, userId).catch(() => {
      // silent
    });
  }
  if (cfEnv?.GF_LLM_CACHE) {
    const key = await cacheKey(figure.id, figure.aliases, normalized);
    cacheSet(cfEnv.GF_LLM_CACHE, key, llmResult).catch(() => {
      // silent
    });
  }

  return json(llmResult);
};
