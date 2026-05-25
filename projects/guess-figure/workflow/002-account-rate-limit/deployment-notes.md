# 002 Deployment Notes — T17 + T18 dashboard 配置

> CF Pages dashboard 操作不入 git, SPEC C6 已规约 "本文件是 source of truth"。
> 部署前确保 P1-P6 代码全部 commit (T1-T16 完成); 部署后跑 T19 verify_ac.sh.

---

## 前置 (本地终端确认)

```bash
cd projects/guess-figure
pnpm exec wrangler whoami     # 已登录 (上次 wrangler login 后 token 持久)
pnpm exec wrangler d1 list    # 见 guess-figure-db (id: 076b1fb2-...-3c5010af2c5b)
pnpm exec wrangler kv namespace list  # 见 GF_RATELIMIT + GF_LLM_CACHE
```

3 个资源 ID（已回填到 wrangler.toml）:

| Binding | 类型 | ID |
|---|---|---|
| `GF_DB` | D1 | `076b1fb2-a238-4190-8d61-3c5010af2c5b` |
| `GF_RATELIMIT` | KV | `797aa9b778dd4a69a970e6befb4ae6b1` |
| `GF_LLM_CACHE` | KV | `c7d92348d3ea4c1aae42d2804c7e13e4` |

---

## T17 step 1 — Environment Variables（CF Pages dashboard）

**路径**: dashboard.cloudflare.com → Workers & Pages → **guess-figure** → Settings → **Environment variables**

为 **Production** + **Preview** 两个 environment 各添加 5 个 variables：

| 变量名 | 类型 | 值 | 说明 |
|---|---|---|---|
| `LLM_BUDGET_DAILY` | Plaintext | `8000` | SPEC G1, V 阈值 |
| `LLM_BUDGET_PER_USER` | Plaintext | `50` | SPEC G2, X 阈值 |
| `RATE_LIMIT_PER_IP_DAILY` | Plaintext | `200` | SPEC G6 |
| `RATE_LIMIT_PER_USER_DAILY` | Plaintext | `200` | SPEC G6 |
| `AUTH_HMAC_SECRET` | **Encrypted** | （见下） | SPEC C4 — 32 字符随机 hex |

**生成 secret**（**Production 和 Preview 应该用不同的 secret**，避免 preview 泄露影响 prod）:

```bash
# Production secret
openssl rand -hex 32
# 输出形如: 3a7f8e2b9c1d4e6f8a2c5b7d9e1f3a5c7b9d1e3f5a7c9b1d3e5f7a9c1b3d5e7f
# 复制此值到 dashboard Production env vars 的 AUTH_HMAC_SECRET

# Preview secret (再跑一次)
openssl rand -hex 32
```

⚠️ **secret 不要入 git / 不要贴到 commit message / 不要贴 PR description**。

设置完后, **save** + **trigger redeploy** (dashboard 一般会提示).

---

## T17 step 2 — D1 + KV Bindings（CF Pages dashboard）

**路径**: dashboard → Workers & Pages → guess-figure → Settings → **Functions** → **Bindings**

### D1 Database

点 "**Add binding**" → "**D1 database**":

| Field | Value |
|---|---|
| Variable name | `GF_DB` |
| D1 database | guess-figure-db |

为 Production + Preview 各加一次（同一 D1 实例两个 env 都用）。

### KV Namespace × 2

点 "**Add binding**" → "**KV namespace**":

| # | Variable name | Namespace |
|---|---|---|
| 1 | `GF_RATELIMIT` | GF_RATELIMIT (id `797aa9b7...`) |
| 2 | `GF_LLM_CACHE` | GF_LLM_CACHE (id `c7d92348...`) |

同上, Production + Preview 各一次。

---

## T17 step 3 — Remote D1 Migration

在本地终端跑（一次性，不可逆）:

```bash
cd projects/guess-figure
pnpm exec wrangler d1 migrations apply guess-figure-db --remote
```

期望输出:
```
Migrations to be applied:
  0001_init_users_and_games.sql
About to apply 1 migration(s)... continue? (Y/n) Y
🌀 Executing on remote database guess-figure-db (076b1fb2-...)
🚣 4 commands executed successfully.
```

**验证 schema**（remote）:
```bash
pnpm exec wrangler d1 execute guess-figure-db --remote \
  --command "SELECT name FROM sqlite_master WHERE type='table'"
# 期望: users, games, _cf_KV (D1 内部)
```

---

## T17 step 4 — 触发 Production Deploy

push 本任务全部 commit 到 main:

```bash
git push origin main
```

CF Pages 自动 build + deploy。在 dashboard → Deployments tab 看进度（typical 1-2 分钟）。

**验证部署成功**:

```bash
# 1. /api/daily 必须返 Set-Cookie
curl -sI https://guess-figure.pages.dev/api/daily | grep -i set-cookie
# 期望: set-cookie: gf_uid=<uuid>.<hmac>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=31536000

# 2. /api/me 必须返 user 战绩 JSON
curl -s https://guess-figure.pages.dev/api/me
# 期望: {"user_id":"...","total_games":0,"total_wins":0,"total_score_30d":0,"recent_games":[]}

# 3. /api/check-answer body 必须接受 figure_id
curl -s -X POST https://guess-figure.pages.dev/api/check-answer \
  -H "Content-Type: application/json" \
  -d '{"input":"诸葛亮","figure_id":"诸葛亮"}'
# 期望: {"correct":true,"reason":"精确匹配"} (server match-exact 短路)
```

任一失败 → 检查 dashboard env vars / bindings 是否填全 + secret 是否设。

---

## T18 — CF Rate Limiting Rules (Security)

**路径**: dashboard → guess-figure → Security → **WAF** → **Rate limiting rules**

⚠️ Pages 项目的 Rate Limiting 是 Cloudflare CDN / WAF 层面的，需在 Cloudflare 主 dashboard 上找：
- 路径可能在 "**guess-figure.pages.dev**" zone 下 (而非 Pages 项目)
- 如果 *.pages.dev 子域不支持 custom rules (需 Pro plan), **T18 跳过, 仅靠 T7 (Q) 计数器兜底, 接受 Workers 配额暴露**

如能配, 加 2 个 rules:

### Rule 1: 极端攻击拦截 (POST /api/check-answer)

| Field | Value |
|---|---|
| Description | 002 防 LLM endpoint 爆刷 |
| If incoming request matches | URI Path starts with `/api/check-answer` **AND** Request Method equals `POST` |
| Then take action | Block |
| For duration | 5 minutes |
| Counting period | 60 seconds |
| Threshold | **60 requests** per IP |
| Characteristics | Client IP |

### Rule 2: 探测扫描拦截 (任意 /api/*)

| Field | Value |
|---|---|
| Description | 002 防 /api/* 整体爆刷 |
| If incoming request matches | URI Path starts with `/api/` |
| Then take action | Block |
| For duration | 5 minutes |
| Counting period | 60 seconds |
| Threshold | **200 requests** per IP |
| Characteristics | Client IP |

保存 + 启用。

**验证（手动压测）**:

```bash
# 触发 Rule 1: 70 次 POST 应该最后几次返 429
for i in $(seq 1 70); do
  curl -s -o /dev/null -w "[$i] %{http_code}\n" -X POST \
    https://guess-figure.pages.dev/api/check-answer \
    -H "Content-Type: application/json" \
    -d '{"input":"test","figure_id":"诸葛亮"}'
done | tail -20
# 期望: 后几次出现 429
```

完成后 dashboard → Analytics → Rate Limiting 应见触发计数 > 0。

---

## 完成后 ✅ checklist

- [ ] Production env vars 5 个齐全（含 AUTH_HMAC_SECRET 已设）
- [ ] Preview env vars 5 个齐全（含**不同**的 AUTH_HMAC_SECRET）
- [ ] D1 binding GF_DB 在 Production + Preview 都配
- [ ] KV bindings GF_RATELIMIT + GF_LLM_CACHE 在 Production + Preview 都配
- [ ] `wrangler d1 migrations apply --remote` 已跑, schema 已建
- [ ] git push 已 trigger production deploy, build 成功
- [ ] `curl /api/daily` 见 Set-Cookie + 3 flag
- [ ] `curl /api/me` 见 user 战绩 JSON
- [ ] `curl -X POST /api/check-answer {"input":"诸葛亮","figure_id":"诸葛亮"}` 见 `{correct:true}`
- [ ] T18 Rate Limiting Rule 1 + 2 配好 (或确认 free plan 不支持, 跳过)
- [ ] T19 `scripts/verify_ac.sh` 跑过, ≥ 18 / 22 AC 自动 PASS

完成后 → Stage 8 Human QA (T20 调 verification-before-completion skill 准备入场报告).

---

## 部署记录（填写时间 + 异常）

| 时间 | 操作 | 结果 / 异常 |
|---|---|---|
| (待) | env vars production 5 个 | |
| (待) | env vars preview 5 个 | |
| (待) | bindings production | |
| (待) | bindings preview | |
| (待) | wrangler d1 migrations --remote | |
| (待) | git push trigger deploy | |
| (待) | T18 Rate Limiting Rule 1+2 | |
