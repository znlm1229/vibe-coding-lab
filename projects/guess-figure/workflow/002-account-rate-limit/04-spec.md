# Stage 4 ｜ SPEC 规格 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-4--spec-规格人工关卡)
> 标准模板见 [`spec-template.md`](../../../../workflow-spec/references/spec-template.md)
>
> **要点**：写"做什么"不写"怎么做"；验收标准必须**可测试**；**用户未确认前不得进入 Stage 5**。
>
> **v1.2 关键约定**：AC 双通道（AI + 人工）；OQ 标 `technical` / `taste`；SPEC 修订需版本号 + 修订日志。

---

# SPEC: 002 账号系统 + 双层限流 + LLM 成本兜底

**版本**：v1.0.1（2026-05-25；命名层 patch — AC5/C6 修订，server 行为不变）
**任务**：[`projects/guess-figure/workflow/002-account-rate-limit/`](.)
**依赖产出**：Stage 1 [01-brainstorm.md](./01-brainstorm.md)、Stage 2 [02-grill-me.md](./02-grill-me.md)、Stage 3 [03-prototype.md](./03-prototype.md)

## Summary

为已上线的猜历史人物游戏 [guess-figure.pages.dev](https://guess-figure.pages.dev) 加入**匿名持久 cookie 账号系统**、**入口防滥用限流**（CF Rate Limiting + Workers KV 计数）、**LLM 调用成本兜底**（结果缓存 + 全局日预算 + 单点日上限），让钱袋子被脚本攻击的风险压到 ≤ ¥5/天，并为未来 003（邮箱 + 排行榜）预留 D1 schema。

## Problem

**钱袋子风险**：现状 [`src/routes/api/check-answer/+server.ts`](../../src/routes/api/check-answer/+server.ts) 每次提交都打云雾中转 → gemini-3.1-flash-lite，**无 server 端 LLM 结果缓存**，**无每日预算上限**，**无 user / IP 级限流**。Stage 3 实测云雾单次 ¥0.000526；理论上脚本挂一晚（每秒 1 次 × 86400 秒 ≈ ¥45）即可击穿"个人小项目"的钱袋子。

**身份缺失**：现状无任何用户态 —— 个人战绩不能持久（每次刷新归零）、未来排行榜无依据、单点限流只能按 IP（共享 NAT 下误伤）。

**不做的后果**：上线 1 个月后任何机器人发现 `/api/check-answer` 即可"扣 host 的钱玩"；同时任何"我想看自己玩了多少局"功能都无法实现。

## Goals

1. **G1 钱袋子兜底**：任何 24 小时窗口内 LLM 真实调用次数 ≤ `LLM_BUDGET_DAILY`（默认 8000/天，对应 ¥4.2/天容忍）。超过后 `/api/check-answer` 进入降级模式（仅 exact match），直到 UTC 0:00 配额刷新。
2. **G2 单点抗刷**：任何 24 小时窗口内单个 user_id 或单 IP 的 LLM 真实调用次数 ≤ `LLM_BUDGET_PER_USER`（默认 50/天）。超过后**该用户**进入降级模式。
3. **G3 缓存复用**：`/api/check-answer` 同 `(figure_id, aliases_hash, normalized_input)` 在 30 天 TTL 内第二次命中 **不调 LLM**，直接返回缓存结果。
4. **G4 匿名持久身份**：首次访问 `/api/*` 任意端点的用户获得签名 cookie；后续请求 server 能稳定识别同一用户（除非用户主动清 cookie）。
5. **G5 战绩持久化**：每局游戏结束（`won` / `gaveUp` / 线索耗尽）自动写入 D1 `games` 表；用户可通过 `/api/me` 拿到自己的汇总战绩。
6. **G6 入口防滥用**：CF dashboard 配置的 Rate Limiting Rules（IP × Path × 时窗）在 Workers 调用前拦截极端攻击，保护 Workers 配额；Workers Functions 内的 KV 计数器做细粒度限流。
7. **G7 降级 / 失败不消耗线索**：当 LLM 调用因配额（降级）或网络/超时（失败）未真正完成裁判，前端**不**触发 `consumeOnWrongAnswer()`，玩家线索不被偷。
8. **G8 003 兼容性**：D1 `users` 表 schema 预留 `email TEXT NULL UNIQUE` 与 `merged_from_user_id UUID NULL` 字段，使 003 加邮箱 / merge 流程时**无需 ALTER TABLE**。

## Non-goals

1. **邮箱 magic link / 真账号**——推至 003 任务（账号"完全可选"语境，cookie 持久 ID 已够 002）。
2. **跨设备同步 / 第三方 OAuth / Passkey**——同上，003 处理。
3. **排行榜 UI / 个人详情页 / 战绩详细查询**——后续任务；002 仅落 D1 schema + `/api/me` 汇总端点。
4. **真账号合并代码（merge function）**——schema 预留即可，代码 003 写。
5. **server 端 blocklist 拒绝单字 / 纯姓氏**（限流方向 W）——不做；server `match-exact` 已挡住"客户端绕过"的脚本攻击。
6. **Cloudflare Turnstile / WAF Custom Rules**（方向 S / T）——不做，留作未来加固选项。
7. **繁→简转换 / 拼音兜底**——不引入；cache normalize 沿用 `match-exact.ts` 现状。
8. **PII / GDPR 合规审查**——002 无邮箱，cookie 仅含随机 UUID（不是个人识别信息）；SPEC 自我说明即可。
9. **D1 / KV 容量监控告警**——上线后 1-2 周观察即可，002 不内建。

## Behavior

### B1. cookie 颁发与验证

**Inputs**：任何对 `/api/*` 的请求（首次访问无 cookie 时）。

**Outputs**：响应 `Set-Cookie: gf_uid=<uuid>.<hmac_b64>; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000`（365 天）。

**关键流程**：

1. 请求进入 Workers Function，读 `gf_uid` cookie。
2. **若 cookie 不存在**：server 生成新 UUID v4，用 `HMAC-SHA256(uuid, env.AUTH_HMAC_SECRET)` 算签名，cookie 内容 = `<uuid>.<hmac_b64>`；同时 D1 `INSERT INTO users(id, created_at) VALUES (?, datetime('now'))`。
3. **若 cookie 存在**：server 拆分 `<uuid>.<hmac>`、用同一 secret 重算 HMAC、比较 → 若验签失败，视作新用户走步骤 2。
4. **滚动续期**：每次成功请求都 `Set-Cookie` 续期 365 天（覆盖旧 cookie 的 expires）。
5. 之后请求处理逻辑可通过 `request.user_id` 拿到 uuid。

**Edge cases**：
- HMAC secret 未配置 → server 返 500 + 日志（这是部署错误，不应在生产发生）。
- D1 INSERT 因 race 冲突（同时两请求新建同 user）→ 用 `INSERT OR IGNORE`，第二次写入静默成功。
- cookie 含非法字符（非 `<uuid>.<base64>` 形态）→ 视作新用户。

### B2. /api/check-answer 调用 pipeline

**Inputs**：`{ input: string, figure_id: string }`（注意：从 brainstorm 起约定的 `target: {name, aliases}` 形态，但 server 端需信任题库为 source of truth → 改为 server 端按 figure_id 查 aliases）

**Outputs**：
- 正常：`{ correct: boolean, reason: string }`（与现状兼容）
- 缓存命中：`{ correct: boolean, reason: string, cached: true }`
- 降级：`{ correct: false, reason: "今日 AI 裁判额度已用尽，仅接受精确答案", degraded: true }`
- 失败：`{ correct: false, reason: "AI 响应异常，请稍后重试", network_error: true }`

**关键流程**：

1. **限流检查 1（按 IP）**：`ratelimit:ip:<ip>:<UTC日>` < 阈值 `RATE_LIMIT_PER_IP_DAILY`？
2. **限流检查 2（按 user_id）**：`ratelimit:user:<uid>:<UTC日>` < `RATE_LIMIT_PER_USER_DAILY`？
3. **server normalize + match-exact 短路**：用共享 lib `src/lib/match-exact.ts` 的 `matchExactly(input, figure)`；命中 → 返 `{correct: true, reason: "精确匹配"}`，**不调 LLM，不写缓存**，**不增 LLM 计数**。
4. **LLM 缓存查**：cache key = `llm-cache:v1:<figure_id>:<sha256(figure.aliases.sort().join("|"))>:<sha256(normalize(input))>`，KV 查；命中 → 返 `{...cached_value, cached: true}`，**不调 LLM**。
5. **LLM 预算检查**：`llm-quota:global:<UTC日>` < `LLM_BUDGET_DAILY`？`llm-quota:user:<uid>:<UTC日>` < `LLM_BUDGET_PER_USER`？任一超 → 返 `{correct: false, reason: <降级文案>, degraded: true}`，**不调 LLM**。
6. **调 LLM**：与现状 [`check-answer/+server.ts`](../../src/routes/api/check-answer/+server.ts) 一致（`max_tokens=300`, `temperature=0.1`, `timeout=10s`）。
7. **LLM 成功**：INCR `llm-quota:global:<UTC日>` 与 `llm-quota:user:<uid>:<UTC日>`（TTL 26h，留 buffer）；写入 KV cache（TTL 30 天）；返 `{correct, reason}`。
8. **LLM 失败 / 超时**：**不**增 LLM 计数（云雾不扣失败请求的费）；返 `{correct: false, reason: "AI 响应异常，请稍后重试", network_error: true}`。

**Edge cases**：
- KV cache 写失败 → 调用仍正常返响应（cache 是 best-effort，不阻塞）。
- 限流 KV INCR 失败 → 视作"未超限"继续，**不**阻塞用户（失败 open，避免误伤）。
- LLM 返回非 JSON → 现状容错逻辑（剥 markdown / 抠 `{...}`）保留；最终仍解析失败 → `{correct: false, reason: <bn 解析失败信息>}`，**不**视作 network_error（这是 LLM 内容错误，不重试有用）。

### B3. 游戏结束写战绩

**Inputs**：`POST /api/game/finish` body `{ figure_id, won, revealed_count, score, given_up }`。

**Outputs**：`{ ok: true, game_id }` 或 `{ ok: false, reason }`。

**关键流程**：

1. 校验请求带有效 cookie（`request.user_id` 存在）；否则 401。
2. 校验 body 字段合法（figure_id 在题库内、revealed_count 1-7、score 公式可重算）；否则 400。
3. `INSERT INTO games(id, user_id, figure_id, won, revealed_count, score, given_up, played_at) VALUES (...)`。
4. 返 `{ok: true, game_id: <uuid>}`。

**Edge cases**：
- 同一局重复 POST（前端 retry）→ body 内含 client-generated `game_id` 字段；server 用 `INSERT OR IGNORE`，重复请求返同一 game_id（幂等）。
- D1 INSERT 失败 → 返 500，**前端不阻塞用户**（游戏结束 UI 已渲染，写不上去等下次刷新再 retry，本任务不实现 retry queue）。

### B4. /api/me 汇总战绩

**Inputs**：GET（需有效 cookie）。

**Outputs**：`{ user_id, total_games, total_wins, total_score_30d, recent_games: [{...最近 5 局}] }`。

**关键流程**：

1. 校验 cookie；无效 → 视作 anonymous user 即 INSERT 新 user（与 B1 一致）。
2. `SELECT COUNT(*), SUM(won), SUM(CASE WHEN played_at > date('now', '-30 days') THEN score ELSE 0 END) FROM games WHERE user_id = ?`。
3. `SELECT * FROM games WHERE user_id = ? ORDER BY played_at DESC LIMIT 5`。
4. 返响应；`Cache-Control: private, max-age=10`。

### B5. 降级 / 失败时前端不消耗线索

**Inputs**：`/api/check-answer` 返回响应。

**Outputs**：[`src/lib/check-answer-client.ts`](../../src/lib/check-answer-client.ts) 调用方逻辑：

1. 若 `network_error === true` → 显示"AI 响应异常，请重试"提示；**不**调 `game.consumeOnWrongAnswer()`；提交按钮可立即再点。
2. 若 `degraded === true` → 显示"今日 AI 裁判额度已用尽，仅接受精确答案"提示；**不**调 `game.consumeOnWrongAnswer()`；用户可继续输精确答案。
3. 若 `correct === false` 且无上述字段 → 正常视作答错；调 `game.consumeOnWrongAnswer()`（与现状一致）。
4. 若 `correct === true` → `game.markWon()`（与现状一致）。

### B6. UI loading state

**Inputs**：用户点击提交答案。

**关键流程**：

1. 提交后立即禁用提交按钮 + 显示 spinner。
2. 200ms 后无响应 → 显示"AI 裁判中..."文字（避免感觉卡死）。
3. 5s 后无响应 → 显示更明显的进度提示（如"AI 正在思考较复杂的输入..."）。
4. 收到响应或 timeout → 恢复 UI 状态。

## Constraints

### C1. 留 CF 生态

- 不引入 Vercel / Supabase / Neon / Auth0 / Clerk / Resend / SendGrid。
- 数据存储：CF D1（user + games）+ CF Workers KV（限流计数 + LLM cache）。
- 不引入 Durable Objects（过度工程，KV 最终一致足够）。

### C2. 共享 normalize lib

- `src/lib/match-exact.ts` 的 `normalize()` + `matchExactly()` 必须为 client / server 共享代码——同一份 ES module。
- 不允许 server 重写一份等价但独立的 normalize 逻辑。

### C3. 阈值可调

- 所有限流 / 预算阈值通过 CF Pages env vars 配置，**不许硬编码**：
  - `LLM_BUDGET_DAILY=8000`（每日全局 LLM 调用上限）
  - `LLM_BUDGET_PER_USER=50`（单 user 日 LLM 上限）
  - `RATE_LIMIT_PER_IP_DAILY=200`（单 IP 日总请求上限）
  - `RATE_LIMIT_PER_USER_DAILY=200`（单 user 日总请求上限）
  - `AUTH_HMAC_SECRET=<random 32 字符>`（cookie HMAC 签名密钥，**部署时设置**）

### C4. Cookie 安全

- `gf_uid` cookie 必须 `HttpOnly`, `Secure`, `SameSite=Lax`。
- HMAC secret 一旦设置不轻易轮换（轮换 = 所有匿名 cookie 失效）。
- secret 不入 git / 不入 SPEC / 不入 commit message。

### C5. D1 schema 兼容性

- `users` 表必须含 nullable `email TEXT UNIQUE` 与 `merged_from_user_id UUID NULL` 字段，**即使 002 不使用**。
- migration 工具：CF D1 migrations 文件夹（`migrations/0001_users_and_games.sql`）入 git。
- 不允许在 SPEC 之外定义 schema；任何 ALTER TABLE 必须有对应 migration 文件。

### C6. P 规则集文档化（CF dashboard 不入 git，SPEC 是 source of truth）

dashboard 配置（**v1.0.1 修订**：发现 CF Pages **free plan 不支持** dashboard Rate Limiting Rules — 仅 Workers Paid / Pro 及以上支持。本任务保留 Q 计数器（src/lib/server/rate-limit.ts）作为限流主路径，P 待 Pages 计划升级或自定义域名 + Cloudflare 域名级 WAF 后启用）：

| 规则 | 条件 | 动作 | 状态 |
|---|---|---|---|
| Rule 1: 极端攻击拦截 | 同 IP 60 秒内对 `/api/check-answer` POST > 60 次 | 阻断 5 分钟，返 429 | **🟡 free plan 不支持，待升级**；Q 计数器（RATE_LIMIT_PER_IP_DAILY=200/天）已部分等效覆盖 |
| Rule 2: 探测扫描拦截 | 同 IP 60 秒内对 `/api/*` 任意 endpoint > 200 次 | 阻断 5 分钟，返 429 | **🟡 同 Rule 1**；Q 计数器（RATE_LIMIT_PER_IP_DAILY）已覆盖 daily 维度 |

**等效性说明**：Q 计数器是按日窗口（24h），P 规则是按 60 秒窗口；颗粒度差异 = P 在突发流量下更快拦截。在 free plan 限制下 Q 是 best-effort 替代，不是完美等效。Stage 7 已实测 RATE_LIMIT_PER_IP_DAILY=200 触发 HTTP 429（连续多次 verify_ac.sh 累计 IP 请求达 200 后），证明 Q 真实生效。

部署后由 Stage 8 人工记录 plan 状态到 `deployment-notes.md`；如未来升级到 Workers Paid 或加自定义域名时，启用 P 并同步本 SPEC（升级到 v1.0.2）。

### C7. AC 双通道

- 每条 AC 必须有可脚本化的 AI 验证路径 + 必须有真人操作的人工验证路径。
- 任何"AI 字面 PASS 但行为 PASS 存疑"的 AC（例如"HTML 不含 X"类）必须重写为行为可观察。

### C8. 失败 open / 计费 close

- 限流 / 缓存 / D1 / KV 任一组件失败 → 应用功能**仍可用**（"failure open"原则，避免基础设施小问题导致游戏崩溃）。
- LLM 计费 INCR 失败 → 仍调 LLM（"failure close on billing"，预算可能轻微超出，但游戏可用，user 不被卡）。**例外**：LLM 预算检查时若 KV 不可用，视作"已达上限"进入降级（保险，避免无限烧钱）。

### C9. 性能预算

- `/api/check-answer` 缓存命中场景 p95 < 200ms（KV 读 + 验签）。
- `/api/check-answer` LLM 调用场景 p95 < 10s（含 LLM 延迟）。
- `/api/me` p95 < 100ms（D1 三个 query）。
- 首次 cookie 颁发场景 p99 < 50ms（HMAC 计算 + D1 INSERT 异步）。

## Open questions

> 已锁定的 11 项核心决策见 [02-grill-me.md](./02-grill-me.md) 的"已锁定的 11 项核心决策"表。本表只列 SPEC 阶段**剩余**待用户拍板的 OQ。

| # | 问题 | 类型 | AI 推荐 | 决定 | 阻塞节点 | 备注 |
|---|---|---|---|---|---|---|
| OQ1 | P dashboard 规则集具体阈值（C6 表） | technical | Rule 1: 60次/60s/IP；Rule 2: 200次/60s/IP；阻断 5 分钟 | (待) | Stage 8 配 | 上线后 1 周观察真实流量再微调 |
| OQ2 | 降级模式文案（V 触发 vs X 触发） | taste ⚠️ | V 文案"今日 AI 裁判额度已用尽，仅接受精确答案"；X 文案"你今日额度已用完，仅接受精确答案"；AI 起草仅占位 | (待) | Stage 7 写前端 | taste 类，用户应自己改 |
| OQ3 | LLM 失败提示文案 | taste ⚠️ | "AI 响应异常，请稍后重试"；AI 起草仅占位 | (待) | Stage 7 写前端 | taste 类 |
| OQ4 | `/api/me` 是否在响应中包含 recent_games 详情 | technical | 包含最近 5 局（含 figure_id / won / score / played_at）；详细列表留未来端点 | 推荐采纳 | Stage 7 | 已 grill 拍板 |
| OQ5 | game_id 由谁生成 | technical | client 端 crypto.randomUUID() 生成（幂等所需），server INSERT OR IGNORE | 推荐采纳 | Stage 7 | 幂等 retry |

## Acceptance criteria

> Stage 9 会对照本节逐条核对。每条二选一可判定 + 双通道验证。所有阈值在 production env vars 默认值下测试。

### AC 组 A：账号 / cookie

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC1 | 首次访问 `/api/daily` 后响应含 `Set-Cookie: gf_uid=...; HttpOnly; Secure; SameSite=Lax` | `curl -sI https://guess-figure.pages.dev/api/daily \| grep -i set-cookie` 含 `gf_uid=` + 三个 flag | 用 Chrome 隐身窗口打开 [/play](https://guess-figure.pages.dev/play)，DevTools → Application → Cookies → 见 `gf_uid` 出现 |
| AC2 | cookie 内容形态为 `<uuid>.<base64-hmac>`，server 验签失败的伪造 cookie 被视作新 user | `curl -H "Cookie: gf_uid=fake.fake" /api/me` 返回的 user_id 与新 cookie 一致；伪造的 fake 未被采纳 | DevTools 把 cookie 改为 `gf_uid=00000000-0000-0000-0000-000000000000.tampered`，刷新 [/play](https://guess-figure.pages.dev/play)，不再认得"原战绩" |
| AC3 | 每次请求都续期 cookie expires 365 天 | `curl -sI /api/daily` 两次，间隔几秒，第二次 `Set-Cookie` 的 `Max-Age=31536000` | DevTools 看 cookie expires 时间，刷新页面后该时间右移 |
| AC4 | HMAC_SECRET 未配置时 `/api/*` 返 500 + 日志 | 本地 dev 不设置 env var，启动后 `curl /api/daily` 返 500 | 在 CF Pages 临时清空 `AUTH_HMAC_SECRET`（preview env），访问站点见服务器错误页 |

### AC 组 B：限流 / 钱袋子

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC5 | **(v1.0.1)** Q 计数器（KV）按 IP 日上限触发 429 限流 — RATE_LIMIT_PER_IP_DAILY=200/天 达到后阻断后续请求。原 SPEC 设想的 dashboard P 规则（60s 窗口）已确认 CF Pages free plan 不支持，等效性由 Q 在 daily 维度部分覆盖（C6 已注） | Stage 7 实测：连续多次 verify_ac.sh 累计 IP 请求 > 200 后，下一次 POST `/api/check-answer` 返 HTTP 429（无 cookie 测试中显式观察到） | 待 P 规则启用时（plan 升级 / 自定义域名+WAF）由 Stage 8 dashboard 复验 |
| AC6 | 单 user 日 LLM 真实调用次数达 `LLM_BUDGET_PER_USER`（默认 50）后，该 user 该日后续 `/api/check-answer` 返 `{degraded: true}` 且**不调 LLM**（云雾余额不再减少） | 测试 env vars `LLM_BUDGET_PER_USER=2`；用同一 cookie 连发 3 次非 exact match 输入；第 3 次响应含 `degraded: true` | 测试 env 下用浏览器连提交 3 次"诸葛丞相"（aliases 不含丞相）；第 3 次见"额度已用完"提示 |
| AC7 | 全站日 LLM 调用达 `LLM_BUDGET_DAILY` 后，所有 user 后续调用均降级 | 测试 env vars `LLM_BUDGET_DAILY=2`；两个不同 cookie 各发一次；第三次任意 cookie 调用 → `degraded: true` | 测试 env 下两个隐身窗口各做一次，第三次任一窗口提交都见"额度已用完" |
| AC8 | LLM 网络/超时失败（10s ReadTimeout）响应含 `network_error: true`、`correct: false`，**前端不消耗线索** | mock 云雾 502 或 superficial dev tool 阻断 yunwu.ai → 提交一次 → 响应含 `network_error: true` | 浏览器 DevTools Network → Throttle → Offline；提交"老丞相"；前端见"AI 响应异常"+ 线索数不变 |
| AC9 | 降级模式（`degraded: true`）下前端**不消耗线索** | 同 AC6 的脚本测试 + 检查游戏状态：`game.revealedCount` 提交前后相等 | 测试 env 触发降级后，看左侧线索区数字保持不变 |
| AC10 | 限流 KV 不可用时，**应用仍可用**（failure open for rate limit），但 LLM 预算检查失败时**进入降级**（failure close for billing） | 模拟 KV 断开（mock `c.env.GF_RATELIMIT.get` 抛错）→ 限流跳过继续；模拟 LLM quota KV 断 → 响应含 `degraded: true` | 不易在生产模拟，留 Stage 8 用本地 wrangler dev 复现 |

### AC 组 C：缓存 / 性能

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC11 | 同 `(figure_id, aliases_hash, normalized_input)` 在 30 天内重复请求 95%+ 不调 LLM（cache hit） | 上线后 2 周用 KV `cf-kv list --prefix llm-cache:v1:` 统计 cache 命中率 > 60%（first 2 weeks 冷启动目标） + 单元测试覆盖同 input 第二次返 `cached: true` | 浏览器手动提交一次"老丞相"（触发 LLM）→ 响应延迟 ~3s；立刻再提交同一 input → 响应延迟 < 200ms + 响应含 `cached: true` |
| AC12 | 题库改 figure.aliases 后，旧 cache key 不再被命中（aliases_hash 变） | 单元测试：mock figure aliases ['A', 'B'] 调用一次写 cache → 改 aliases 为 ['A', 'B', 'C'] → 同 input 再调，cache key 不同（不命中） | 修改 `figures.json` 某个 figure 的 aliases；deploy；先前手动测过的"老丞相"再提交时走 LLM 而非缓存 |
| AC13 | `/api/check-answer` 缓存命中场景 p95 < 200ms | `curl -w "%{time_total}" /api/check-answer ...` 100 次（保证全命中），p95 < 0.2 | 浏览器手动提交同一 input 10 次，DevTools Network 面板看响应时间分布 |

### AC 组 D：战绩持久化

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC14 | 一局游戏结束后自动 POST `/api/game/finish` 并 INSERT 到 D1 games 表 | `wrangler d1 execute guess-figure-db --command "SELECT COUNT(*) FROM games"` 跑游戏前后差 1 | 浏览器玩完一局赢/输/放弃；DevTools Network 面板见 `/api/game/finish` 200；F5 后 `/api/me` 返回的 `total_games` +1 |
| AC15 | 同一 game_id 重复 POST 幂等（不出双行）| 脚本同 game_id 发两次 `/api/game/finish` → D1 表只 1 行 | 不易复现，留单元测试覆盖 |
| AC16 | `/api/me` 返回当前用户的 `total_games / total_wins / total_score_30d / recent_games` | `curl -H "Cookie: gf_uid=..." /api/me` 返回的字段完整 | 浏览器 DevTools Console 跑 `fetch('/api/me').then(r => r.json()).then(console.log)`；见 4 个字段 |
| AC17 | `users` 表含 nullable `email` + `merged_from_user_id` 字段（即使 002 不写） | `wrangler d1 execute ... "PRAGMA table_info(users)"` 含两字段且 not null = 0 | 用任何 SQLite GUI 工具看 users 表 schema |

### AC 组 E：UX / loading state

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC18 | 提交答案后 200ms 内显示"AI 裁判中..."占位 | Playwright/Cypress E2E 测试模拟点击 + 200ms 后断言"AI 裁判中"DOM 存在 | 浏览器 Chrome DevTools Network → Slow 3G；提交"老丞相"；200ms 后见旋转提示 |
| AC19 | 提交 5 秒后无响应显示更明显进度提示 | 同上但 5s 后断言新提示 DOM 存在 | DevTools Network → Slow 3G + Throttle 5s；见进度提示 |
| AC20 | 缓存命中场景下用户感知"近乎瞬间"（响应 < 200ms） | 同 AC13 | 浏览器手动复测同 input；体感"立刻返回" |

### AC 组 F：未登录态向后兼容

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC21 | 完全不带 cookie 直接 POST `/api/check-answer` 也能工作（首次访问时 server 自动发 cookie） | `curl -X POST -H "Cookie:" /api/check-answer ...` 返 200 + 含 Set-Cookie | 隐身窗口直接打开页面玩，不显式登录也能完整玩一局 |
| AC22 | 现有 001 任务的功能完全保留（daily / play / 答错消耗线索 / 求救线索） | 现有 E2E 测试套全过 | 完整玩一局 daily 模式，AC1-AC15 / 001 任务全部行为不变 |

---

## 用户确认

- ☑ **已确认** — 确认时间：2026-05-22 ｜ 备注：通过 AskUserQuestion "确认 v1.0, 进 Stage 5 Plan"

> 一旦确认，本 SPEC 即为契约。后续修改需显式重新确认（不允许静默漂移）。

## 修订日志

| 版本 | 日期 | 触发 | 变更 |
|---|---|---|---|
| v1.0 | 2026-05-22 | 初版（Stage 4） | Stage 1-3 锁定的全部决策 + Stage 3 实测数据回填阈值 |
| v1.0.1 | 2026-05-25 | Stage 7 收尾 / T20 verification-before-completion 发现 | C6 + AC5 修订：CF Pages free plan 不支持 dashboard Rate Limiting Rules（属外部基础设施限制，非 SPEC 漂移）。验证路径转移到 Workers KV 计数器（Q），daily 维度部分覆盖；待 plan 升级 / 自定义域名 + WAF 时启用 P。命名层 patch，server 行为不变，不触发 re-confirm。用户 2026-05-25 通过 chat 明示"free plan 真不支持 可以容忍"接受 |
