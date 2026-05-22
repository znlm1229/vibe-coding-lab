// T13: LLM 模糊匹配 API endpoint（CF Pages Function）
//
// SPEC 决策 5 第二道：异称表精确匹配失败时调本 endpoint，让 LLM 判断
// 用户输入是否在指代目标人物（如"诸葛丞相" → 诸葛亮）。
//
// 输入: { input: string, target: { name: string, aliases: string[] } }
// 输出: { correct: boolean, reason: string }
//
// 沿用 prototype B 已验证的 prompt + JSON 容错策略。

import { json, error } from "@sveltejs/kit";
import { env } from "$env/dynamic/private";
import type { RequestHandler } from "./$types";

export const POST: RequestHandler = async ({ request }) => {
  const body = (await request.json()) as {
    input: string;
    target: { name: string; aliases: string[] };
  };
  const { input, target } = body;

  if (!input?.trim()) throw error(400, "input 必填");
  if (!target?.name) throw error(400, "target.name 必填");

  const apiKey = env.YUNWU_API_KEY;
  const baseUrlRaw = env.YUNWU_BASE_URL ?? "https://yunwu.ai/v1";
  const model = env.LLM_MODEL ?? "gemini-3.1-flash-lite";

  if (!apiKey) throw error(500, "缺 YUNWU_API_KEY 环境变量（本地: 检查 .env；生产: 检查 CF Pages env vars）");

  const baseUrl = baseUrlRaw.replace(/\/+$/, "");
  const url = baseUrl.endsWith("/v1") ? `${baseUrl}/chat/completions` : `${baseUrl}/v1/chat/completions`;

  const prompt = `你是历史人物姓名识别助手。判断用户输入是否在指代目标人物。

目标人物：${target.name}
已知异称（字 / 号 / 谥号 / 庙号 / 别号）：${target.aliases.join("、")}

用户输入："${input}"

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
      signal: AbortSignal.timeout(10_000), // 10s 超时
    });
  } catch (e) {
    // 网络错误 / 超时
    throw error(504, `LLM 请求异常: ${e instanceof Error ? e.message : String(e)}`);
  }

  if (!llmResp.ok) {
    const errText = await llmResp.text();
    throw error(502, `LLM HTTP ${llmResp.status}: ${errText.slice(0, 200)}`);
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

  try {
    const parsed = JSON.parse(content);
    return json({
      correct: !!parsed.correct,
      reason: String(parsed.reason ?? ""),
    });
  } catch {
    // LLM 返回非 JSON 兜底
    return json({
      correct: false,
      reason: `LLM 返回无法解析：${content.slice(0, 100)}`,
    });
  }
};
