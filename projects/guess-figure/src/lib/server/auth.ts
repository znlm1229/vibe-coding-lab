// 002 T5: cookie HMAC 签名 / 验签 + getUserId 入口
//
// SPEC v1.0 B1 / C4: cookie 内容 = "<uuid>.<hmac_b64>", HMAC-SHA256(uuid, AUTH_HMAC_SECRET)
// HttpOnly + Secure + SameSite=Lax, Max-Age=31536000 (365 天滚动续期)
//
// 注意:
//   - 使用 Web Crypto API (CF Workers/Pages runtime 原生), 不用 Node crypto
//   - signCookie / verifyCookie 是纯函数, 易测试
//   - getUserId 整合 cookie 读 + 验签 + D1 INSERT OR IGNORE 新 user

import type { D1Database } from "@cloudflare/workers-types";

const COOKIE_NAME = "gf_uid";
const COOKIE_MAX_AGE_SEC = 365 * 24 * 60 * 60; // 365 天

// ====================================================================
// 纯函数：HMAC sign / verify
// ====================================================================

/** base64url 编码 (无 padding, URL safe), 适合 cookie value */
function b64urlEncode(bytes: ArrayBuffer): string {
  const arr = new Uint8Array(bytes);
  let bin = "";
  for (const b of arr) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function hmacSha256(message: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return b64urlEncode(sig);
}

/** 用 secret HMAC-SHA256 签 uuid, 返回 cookie value `<uuid>.<hmac_b64url>` */
export async function signCookie(uuid: string, secret: string): Promise<string> {
  const hmac = await hmacSha256(uuid, secret);
  return `${uuid}.${hmac}`;
}

/** 验证 cookie value, 返回 {valid, uuid?}. 不抛, 任何形态错均返 valid: false */
export async function verifyCookie(
  cookieValue: string | null | undefined,
  secret: string,
): Promise<{ valid: boolean; uuid?: string }> {
  if (!cookieValue) return { valid: false };
  const parts = cookieValue.split(".");
  if (parts.length !== 2) return { valid: false };
  const [uuid, hmac] = parts;
  if (!uuid || !hmac) return { valid: false };
  // UUID v4 形态: 8-4-4-4-12 (小写 hex + dash)
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(uuid)) {
    return { valid: false };
  }
  const expectedHmac = await hmacSha256(uuid, secret);
  // 常量时间比较 (防 timing attack)
  if (expectedHmac.length !== hmac.length) return { valid: false };
  let diff = 0;
  for (let i = 0; i < hmac.length; i++) {
    diff |= hmac.charCodeAt(i) ^ expectedHmac.charCodeAt(i);
  }
  return diff === 0 ? { valid: true, uuid } : { valid: false };
}

// ====================================================================
// getUserId — 入口 (T6 hooks.server.ts 调用)
// ====================================================================

export interface GetUserIdResult {
  user_id: string;
  /** 若新建 user 或验签失败需重发, 返回 Set-Cookie header value (供 hook 加到响应) */
  set_cookie?: string;
}

interface GetUserIdEnv {
  AUTH_HMAC_SECRET?: string;
  GF_DB?: D1Database;
}

/**
 * 从 request cookies 读 gf_uid, 验签;
 * - 验签通过 → 用 uuid 当 user_id (D1 用户行假设已存)
 * - 验签失败 / cookie 缺 → 生成新 uuid, INSERT D1 user 行 (INSERT OR IGNORE 幂等), 返回 set_cookie
 *
 * 滚动续期: 即使 cookie 合法, hook 仍可选择重发 Set-Cookie 续期 maxAge. 本函数将 set_cookie
 *   返回**仅在新建** user 时填充; 续期逻辑由 T6 hook 决定 (传入 alwaysSetCookie 参数等).
 */
export async function getUserId(
  request: Request,
  env: GetUserIdEnv,
): Promise<GetUserIdResult> {
  const secret = env.AUTH_HMAC_SECRET;
  if (!secret) {
    throw new Error("AUTH_HMAC_SECRET 未配置 (检查 CF Pages env vars / 本地 .env)");
  }
  const db = env.GF_DB;
  if (!db) {
    throw new Error("GF_DB binding 缺失 (wrangler.toml 配置或 dashboard binding)");
  }

  // 读 cookie
  const cookieHeader = request.headers.get("cookie") ?? "";
  const cookies = parseCookieHeader(cookieHeader);
  const gfUid = cookies[COOKIE_NAME];

  const verification = await verifyCookie(gfUid, secret);
  if (verification.valid && verification.uuid) {
    return { user_id: verification.uuid };
  }

  // 验签失败或无 cookie — 新建 user
  const newUuid = crypto.randomUUID();
  await db
    .prepare("INSERT OR IGNORE INTO users (id, created_at) VALUES (?, datetime('now'))")
    .bind(newUuid)
    .run();

  const signed = await signCookie(newUuid, secret);
  return { user_id: newUuid, set_cookie: buildSetCookie(signed) };
}

/** 构造 Set-Cookie header value, HttpOnly + Secure + SameSite=Lax + Max-Age 365d */
export function buildSetCookie(signedValue: string): string {
  return `${COOKIE_NAME}=${signedValue}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${COOKIE_MAX_AGE_SEC}`;
}

/** 简易 cookie 解析 (RFC 6265 兼容子集; 不处理 quote-escape) */
export function parseCookieHeader(header: string): Record<string, string> {
  const out: Record<string, string> = {};
  if (!header) return out;
  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    const k = part.slice(0, eq).trim();
    const v = part.slice(eq + 1).trim();
    if (k && !(k in out)) out[k] = v;
  }
  return out;
}
