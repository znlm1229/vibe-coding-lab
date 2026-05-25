// 临时 debug endpoint — 诊断 production runtime 看到的 bindings + env vars 列表
// 不返 value (避免泄露 secret), 仅返 key 名 + 类型
//
// 用法: curl https://guess-figure.pages.dev/api/_debug
//
// FIXME: Stage 7 调试完后 git revert 此文件 (避免 production 暴露内部状态)

import { json } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";

export const GET: RequestHandler = async ({ platform, locals }) => {
  const env = platform?.env ?? {};
  const keys: Record<string, string> = {};

  // 列每个 env key + 其类型 (不返 value)
  for (const k of Object.keys(env)) {
    const v = (env as Record<string, unknown>)[k];
    if (v == null) {
      keys[k] = "null";
    } else if (typeof v === "string") {
      // env var: 显示长度而非内容
      keys[k] = `string(len=${v.length})`;
    } else if (typeof v === "object" && v) {
      // D1Database / KVNamespace: 显示是否含已知方法
      const obj = v as Record<string, unknown>;
      const hints: string[] = [];
      if (typeof obj.prepare === "function") hints.push("D1");
      if (typeof obj.get === "function" && typeof obj.put === "function") hints.push("KV");
      keys[k] = `object(${hints.join("+") || "unknown"})`;
    } else {
      keys[k] = typeof v;
    }
  }

  return json({
    platform_env_keys: keys,
    user_id_from_locals: locals.user_id ?? null,
    has_platform: !!platform,
  });
};
