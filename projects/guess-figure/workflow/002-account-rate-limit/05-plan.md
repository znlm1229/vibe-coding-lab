# Stage 5 ｜ Plan 计划

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-5--plan-计划)
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)
>
> **要点**：从已确认的 SPEC v1.0 出发，回答「怎么做」与「按什么顺序」。**不在本阶段拆 task**（Stage 6 的工作，独立人工关卡）。

---

# Plan: 002 账号系统 + 双层限流 + LLM 成本兜底

依据 [04-spec.md](./04-spec.md) v1.0（2026-05-22 已确认）。

## Approach

**总体策略**：在现有 SvelteKit + Pages Functions 单体应用上**就地改造**，不引入新框架 / 新服务。所有持久化在 Cloudflare 边缘原生设施内：D1 存关系数据（user + games），Workers KV 存计数器与短期缓存（限流配额 + LLM 结果）。鉴权用最简单的 HMAC 签名 cookie，**不引入 server-side session 表**（session 状态就是 cookie 本身）。

**关键架构决策与替代方案对比**（呼应 Stage 1-2）：

| 决策 | 选 | 否决方案 | 选择理由 |
|---|---|---|---|
| 账号深度 | A 匿名持久 cookie | B Magic Link / C OAuth / D Clerk | "完全可选"语境 + MailChannels 2024 终止 + 想做端到端自建 |
| 持久化 | D1 + users/games 两表 | KV blob / 仅 cookie | 未来排行榜要 SQL join；预留 003 邮箱迁移最简 |
| Cookie | HMAC signed UUID | JWT / iron-session 加密 | one-shot user_id，HMAC 最轻；签名而非加密 |
| 限流主线 1 | P + Q 双层 | Q only / P only / DO | 防御纵深保 Workers 配额；Q 顺手做 user 维度 |
| 限流主线 2 | U + V + X | 仅 V / 仅 U / DO 强一致 | 三件套互补；W blocklist 暂不做留扩展 |
| LLM cache key | 含 aliases_hash | 仅 figure_id | grill 出"prompt 含 aliases" → 必须按 aliases 失效 |
| pipeline | server 重跑 match-exact | 信任 client | 防脚本绕 client 直打 server 流血 |
| Prototype | 仅 LLM 计费实测 | 跳过 / 全面 spike | grill Q11 拍定：钱袋子是最大未知，实测必做；其他 Web Crypto / D1 已知工作不浪费时间 |

## Phases

按依赖排序，**8 个 phase**。每个 phase 自身是一个 coherent 进度块，不是单个 task（Stage 6 才拆 task）。

### Phase 1 — 基础设施搭建（D1 + KV + env vars）

**交付**：
- `wrangler.toml` 加 D1 binding + 两个 KV namespace binding（`GF_RATELIMIT` + `GF_LLM_CACHE`）
- `migrations/0001_init_users_and_games.sql`：建 `users` 表（id, email NULL UNIQUE, merged_from_user_id NULL, created_at）+ `games` 表（id, user_id, figure_id, won, revealed_count, score, given_up, played_at）+ INDEX (user_id, played_at DESC)
- `.env.example` 加入 5 个 env vars 占位（LLM_BUDGET_DAILY=8000, LLM_BUDGET_PER_USER=50, RATE_LIMIT_PER_IP_DAILY=200, RATE_LIMIT_PER_USER_DAILY=200, AUTH_HMAC_SECRET=...）
- `src/app.d.ts` 扩展 `App.Platform.env` 类型声明 D1 + KV binding + env vars

**为什么排第一**：所有后端代码都依赖 schema + KV 存在；migrations 入 git 是不可逆动作，先订；env vars 名字定下来才能在后续 phase 引用，避免后期 rename 满地。

**风险**：D1 创建后 schema 锁定，rollback 需要明确路径（migration 文件双向）。

### Phase 2 — 共享 lib 抽取 + cookie 鉴权层

**交付**：
- `src/lib/match-exact.ts` 已存在，**保持原位**作为 client/server 共享 ES module；server 端 `+server.ts` 直接 `import { normalize, matchExactly } from "$lib/match-exact"` 即可
- 新增 `src/lib/server/auth.ts`：导出 `getUserId(request, env): Promise<{user_id, set_cookie?}>` —— 读 cookie → 验签 → 若新用户则 INSERT D1 user 表 + 返回 Set-Cookie header
- 新增 `src/hooks.server.ts`（SvelteKit hook）：所有 `/api/*` 请求前调 `getUserId`，把 user_id 挂到 `event.locals`，把 Set-Cookie 挂到响应

**为什么排这里**：是所有 endpoint 改动的前置；cookie 鉴权统一在 hook 层做，endpoint 内部就只用 `event.locals.user_id`，不重复鉴权逻辑。

**风险**：
- HMAC secret 在 local dev 与 production 必须不同（local 用 `.env`，prod 用 CF dashboard env vars）—— 部署 checklist 必含
- SvelteKit hook 在 CF Pages adapter 下行为与 Node adapter 略有差异，需 wrangler local 实测一次
- `Secure` flag 在 `wrangler dev` http://localhost:XXXX 模式下被浏览器忽略 —— SPEC AC1 的本地验证要用 `--ip 0.0.0.0 --local-protocol https` 或接受本地 Secure flag 缺失

### Phase 3 — 限流 + LLM 缓存中间件

**交付**：
- 新增 `src/lib/server/rate-limit.ts`：导出 `checkRateLimits(env, user_id, ip, kind: "request" | "llm")` —— 按需读 4 个 KV counter（IP 日总 / user 日总 / LLM 全局日 / LLM 单点日）；返 `{ok: true} | {ok: false, reason: "rate-limit-ip" | "rate-limit-user" | "budget-global" | "budget-user"}`
- 新增 `src/lib/server/llm-cache.ts`：导出 `cacheKey(figure, normalizedInput): string` + `cacheGet(env, key): Promise<CacheValue | null>` + `cacheSet(env, key, value, ttl=2592000)`
- INCR counter 辅助函数（带 TTL 26h 自动过期）

**为什么排这里**：建在 Phase 2 cookie 上（需要 user_id 做 user 维度限流）；与 Phase 4 解耦——pipeline 用 import 调用，不混在 endpoint 里。

**风险**：
- KV 是最终一致：跨边缘 counter 可能短暂偏差几个数。SPEC C8（failure open）已规约接受
- TTL 26h：保证跨 UTC 0:00 切换不漏档；但**第一次写入**的 TTL 不能用 INCR 重设——要用 `put + INCR` 两步或 KV 不存在时显式初始化

### Phase 4 — `/api/check-answer` 改造

**交付**：
- 改写 [`src/routes/api/check-answer/+server.ts`](../../src/routes/api/check-answer/+server.ts)：
  - 请求体改为 `{input, figure_id}`（server 按 figure_id 查 aliases，不再信任 client 传 target）
  - 加 server-side `normalize` + `matchExactly` 短路（Phase 2 共享 lib）
  - 加缓存查（Phase 3 helper）
  - 加限流 + LLM 预算检查（Phase 3 helper）
  - 调 LLM 成功后写缓存 + INCR LLM 计数
  - 响应增字段：`cached?: boolean` / `degraded?: true` / `network_error?: true`
- 改 [`src/lib/check-answer-client.ts`](../../src/lib/check-answer-client.ts)：请求 body 改为 `{input, figure_id}`；响应解析适配新字段

**为什么排这里**：Phase 2/3 都是前置；本 phase 是 SPEC G1/G2/G3/G6/G7 的核心实现。

**风险**：
- 请求体 schema 变了（target → figure_id），需保证前端调用方同步改；本 phase 内同时改 server + client 避免 inconsistency
- LLM cache write 失败必须 silent（不阻塞响应）
- LLM 调用本身的现状超时/容错逻辑（line 52-95 的 try/catch + JSON 容错）**完整保留**

### Phase 5 — 新 endpoints（/api/me + /api/game/finish）

**交付**：
- 新增 `src/routes/api/me/+server.ts`：GET，从 D1 查 user 战绩汇总 + recent 5 局
- 新增 `src/routes/api/game/finish/+server.ts`：POST，校验 + 幂等 INSERT games 表

**为什么排这里**：只依赖 Phase 1 (D1) + Phase 2 (cookie)，**与 Phase 4 可并行**——两端没有共享代码改动。

**风险**：
- `/api/me` 在新用户首次访问时 user 表可能刚 INSERT，需注意 Phase 2 hook 是先 INSERT 再走 endpoint
- game_id 客户端生成（SPEC OQ5）`crypto.randomUUID()` 在所有浏览器都已 ES2021 支持，OK
- D1 INSERT OR IGNORE 在主键冲突时静默成功（幂等），但 INSERT 失败的其他原因（连接异常）需 catch → 返 500 但前端不阻塞 UI（SPEC B3 已规约）

### Phase 6 — 前端改造（client / UI / game-state 接缝）

**交付**：
- 改 [`src/lib/check-answer-client.ts`](../../src/lib/check-answer-client.ts)：识别 `network_error: true` / `degraded: true`，二者都**不**调 `game.consumeOnWrongAnswer()`，弹相应提示
- 改 [`src/lib/components/AnswerInput.svelte`](../../src/lib/components/AnswerInput.svelte) 或调用方：加 loading state（200ms 后 spinner，5s 后强提示）
- 在 game 结束时（won/gaveUp/exhausted）调 `/api/game/finish` POST 战绩
- 在合适入口（如 layout / play 页）调一次 `/api/me`（可选展示个人战绩，002 范围内可极简：仅在 console.log 或藏一个 debug 区，UI 完整展示留 003）
- 文案占位：SPEC OQ2/OQ3 是 taste 类，先用占位文案，**等用户改后再 commit**

**为什么排这里**：依赖 Phase 4 / Phase 5 的响应 schema 定义；前后端联调测试在此阶段开始。

**风险**：
- 现状 [`game-state.svelte.ts:85-94`](../../src/lib/game-state.svelte.ts) 的 `consumeOnWrongAnswer()` 在答错时被调；我们要确保前端**只在 `correct: false && !network_error && !degraded`** 时才调它 —— 这是 G7 / AC8 / AC9 的核心，必须有 unit 测试覆盖
- AnswerInput.svelte 现有 loading state 实现可能要重构；查代码避免重复造轮子

### Phase 7 — CF dashboard P 规则集 + 部署 / env vars 配置

**交付**：
- CF dashboard → guess-figure 项目 → Security → Rate Limiting Rules 配 2 个规则（SPEC C6 已文档化数值）
- CF dashboard → guess-figure → Settings → Environment Variables 配 5 个 env vars（production 与 preview 各一份；AUTH_HMAC_SECRET 用 `openssl rand -hex 32` 生成 64 字符）
- CF dashboard → guess-figure → Functions → D1 database bindings 绑定 D1
- CF dashboard → guess-figure → Functions → KV namespace bindings 绑定 GF_RATELIMIT + GF_LLM_CACHE
- 执行 D1 migration：`wrangler d1 migrations apply guess-figure-db --remote`

**为什么排这里**：所有代码就绪后才一次性配 production；dashboard 配置**不入 git**但 SPEC C6 已是 source of truth，本 phase 的 commit 也在 implementation note 写明确切配置。

**风险**：
- secret 配错 → 全站 500（已在 AC4 验证）；建议先在 preview env 测一遍再切 production
- D1 migrations apply --remote 是不可逆动作（建好 prod 表后 schema 变更要走新 migration，不能改 0001）
- P 规则集在 dashboard 配错不会 break 站，但会让 AC5 失败——上线后 AC 验证时复核

### Phase 8 — AC 验证 / Stage 8 准备

**交付**：
- 22 条 AC 的 AI 验证脚本汇总（写 `scripts/verify_ac.sh` 或类似）：curl / wrangler d1 execute / unit test 执行链
- wrangler dev local 跑通"模拟 V/X 触发"的测试 env（临时把 LLM_BUDGET_PER_USER=2 复现 AC6）
- Stage 8 人工 QA 清单：列出 22 条 AC 各自的人工验证操作步骤（截图位置 / 浏览器步骤）
- **强制**：转 Stage 8 前调 `verification-before-completion` skill（workflow-spec v1.2）

**为什么排这里**：所有 implementation 完成后再统一跑 AC；这是 Stage 7 收尾 → Stage 8 入场的最后一道关。

**风险**：
- AC10 / AC15 的人工验证较弱（已在 SPEC 中标注"留单元测试 / wrangler dev 复现"）—— 单元测试覆盖必须确实存在
- 上线后 LLM 缓存命中率（AC11）要 1-2 周积累才能验，**SPEC 接受为 follow-up 观测**而非 Stage 9 阻塞 AC

## Dependencies

依赖图（→ = "前者交付后后者才能开始"）：

```
P1 (基础设施)
 │
 ├──→ P2 (共享 lib + cookie 层) ───┐
 │                                 ├──→ P3 (限流缓存中间件) ──→ P4 (check-answer 改造) ──┐
 │                                 │                                                       │
 │                                 └────────────────────→ P5 (/api/me + /api/game/finish) ─┴──→ P6 (前端) ──→ P7 (dashboard + 部署) ──→ P8 (AC 验证)
```

**关键观察**：
- **P4 与 P5 可并行**（依赖完全独立——P4 是中间件接入 + endpoint 改造，P5 是新建端点；联调要 P6 阶段）
- **P2 阻塞所有下游**——cookie 是几乎所有 endpoint 的前提
- **P3 仅 P4 阻塞，不阻塞 P5**——P5 不调用限流（`/api/me` 与 `/api/game/finish` 无 LLM 调用 + 入口防滥用靠 P1 已生效）
- **P7 不可与 P6 并行**——dashboard 配错可能 break 站，要在前端联调完后才碰
- **P8 是收尾**，不重叠任何 Phase

**外部依赖 / 外部输入**：
- 云雾 API 在 Stage 3 实测期可用；如 Stage 7 阶段挂掉需保 LLM_TIMEOUT_SEC 不变 + 让 network_error 路径正常工作
- CF Pages 当前部署 webhook（git push 自动 deploy）保持不变
- 用户回填 OQ2/OQ3 taste 文案 —— 阻塞 Phase 6 的 commit（不阻塞实现，可先占位）

## Risks

按严重度排序：

### 高风险（必须主动管控）

1. **D1 migrations 在 production 不可逆**。0001 init 一次过，后续任何 schema 变更要新 migration（如 003 加邮箱）。**缓解**：Phase 1 的 schema 必须严格按 SPEC C5 写 nullable email + merged_from_user_id，**不**留到 003 再 ALTER（虽然 SQLite 也允许，但本任务 SPEC 已要求 002 预留）。
2. **HMAC secret 一次性事件**。配错或泄露后果严重。**缓解**：SPEC C4 已规约；Phase 7 加 runbook 文档化"如何生成 secret + 如何配 dashboard + 永远不入 git"。
3. **request body schema 变更（target → figure_id）**。Phase 4 必须 server + client 一起改；否则线上 client 调旧 server 或反之均报错。**缓解**：Phase 4 内严格同步；保留旧 schema 支持一周 deprecation 不做（成本不划算，002 是一次性切换）。

### 中风险（已有计划缓解）

4. **wrangler dev 与 production 行为差异**（Secure cookie / D1 远端连接 / KV 边缘一致性）。**缓解**：Phase 2 / Phase 4 各做一次 `wrangler dev --local` + `wrangler dev --remote` 双跑验证；AC 中标注哪些只能 remote 验。
5. **KV TTL 跨日切换**。LLM_BUDGET_DAILY 是按 UTC 日计数；UTC 23:59 与 UTC 00:01 不属同一 key；用户在跨日点附近的体验可能突变。**缓解**：SPEC G1 接受"配额按 UTC 日"语义；上线后观察日切的真实流量分布。
6. **LLM 调用 5% 失败率**（Stage 3 实测）。SPEC AC8 已规约 network_error 处理。**缓解**：Phase 6 的 check-answer-client 改造必须有 unit test 覆盖 network_error 分支（不消耗线索 + 提示重试）。

### 低风险 / 已知妥协

7. **cache 冷启动期命中率为 0**（Stage 3 已识别）。前 1-2 周 LLM 调用量等同改造前。**缓解**：SPEC C8 接受，监控期把握。
8. **OQ2/OQ3 文案 taste 类**。AI 占位先实现；用户审阅 commit message 时回看；Stage 8 同步改。**缓解**：Phase 6 commit 前明确标注 "OQ2/OQ3 待用户改"。

### 已通过 Stage 3 Prototype 解决的风险

- ✅ 云雾 LLM 单次调用成本（实测 ¥0.000526）→ V/X 阈值已定
- ✅ LLM 单次调用 token 用量稳定（prompt 233 / completion 38）→ 缓存 key normalize 后字数稳定
- ✅ LLM 调用 p95 延迟（7.8s）→ UI loading 200ms/5s 双阶段已规约

## Test strategy

### 单元测试（vitest，本仓库未配但 SvelteKit 模板自带支持 — Phase 1 顺手加 `pnpm add -D vitest @vitest/ui`）

| 覆盖 | 测试什么 | Phase |
|---|---|---|
| `normalize()` | 现有行为不退化 + 新增 server 端复用 | P2 |
| `matchExactly()` | 已有覆盖（client）+ server 调用复用 | P2 |
| `auth.ts` HMAC sign/verify | 合法 cookie 验签通过 / 伪造 fail / secret 改后旧 cookie fail | P2 |
| `rate-limit.ts` | counter < 阈值时 ok / >= 阈值时拒 / KV 不可用时 failure open（除 LLM budget close） | P3 |
| `llm-cache.ts` cacheKey | 同 (figure, input) 同 key / aliases 改后 key 不同 / clues 改不影响 key | P3 |
| `check-answer-client.ts` | 4 个响应分支（correct / wrong / degraded / network_error）调用 game state 正确（前两个消耗，后两个不消耗） | P6 |

### 集成测试（wrangler local + miniflare）

| 覆盖 | 测试什么 | Phase |
|---|---|---|
| `/api/check-answer` 完整 pipeline | cookie 颁发 → match-exact 短路 → LLM 缓存命中 → LLM 调用 → 缓存写 → 限流计数 → 降级触发 | P4 |
| `/api/game/finish` 幂等 | 同 game_id POST 两次 → D1 只 1 行 | P5 |
| `/api/me` 字段完整 | 多局游戏后查询 → total_games / total_wins / total_score_30d / recent_games 都对 | P5 |
| 跨 endpoint cookie 一致 | 隐身环境多次 / 不同 endpoint user_id 稳定 | P2 + P5 |

### E2E 测试（Playwright，本仓库未配；Phase 8 视情况）

- 完整玩一局（赢 / 输 / 放弃）+ F5 后 `/api/me` 反映新战绩
- 提交按钮 loading state 200ms / 5s 双阶段实际看到（Slow 3G 模拟）

### 留 Stage 8 Human QA（必须真人操作）

| AC | 为什么留人工 |
|---|---|
| AC1 / AC2 / AC3 | DevTools 直观看 cookie 颁发 / 续期 / 伪造行为 |
| AC5 | dashboard 数据复核 P 规则触发 |
| AC8 / AC9 | DevTools Network Throttle Offline 是人工动作 |
| AC11 | 浏览器手动复测 cached 响应"瞬间感" |
| AC12 | 改题库 deploy → 再测之前用过的 input 是否走 LLM |
| AC14 | 真玩一局看 D1 行数变化 |
| AC18 / AC19 / AC20 | UI loading 体感 |
| AC21 / AC22 | 隐身窗口 + 完整 001 行为回归 |

### Verification-before-completion 关卡（v1.2 强制）

Phase 8 转 Stage 8 之前调 `verification-before-completion` skill，确保每条 AC 的 "PASS" 都有对应命令输出 / 截图证据；防止"字面 AC PASS 但行为 PASS 存疑"——v1.2 失败模式专治。
