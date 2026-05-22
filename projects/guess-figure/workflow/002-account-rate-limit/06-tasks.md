# Stage 6 ｜ Tasks 任务 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-6--tasks-任务人工关卡)
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)
>
> **要点**：每个任务**可独立完成**；标 Touches / Done when / Depends on；**用户未确认前不得进入 Stage 7**。
>
> **v1.2 commit 前缀**：`task-TX:` 首次实现 / `fix(TX):` Bug 回路 / `stage-N:` 阶段产出 / `chore:` 治理 / `docs:` 文档

---

# Tasks: 002 账号 + 限流 + LLM 成本兜底

依据 [04-spec.md](./04-spec.md) v1.0 + [05-plan.md](./05-plan.md) 8 Phase 拆分。共 **20 个 task**，分配到 8 Phase。

## 任务清单

### Phase 1 — 基础设施（T1-T3）

- [ ] **T1 — D1 binding + migration 0001 创建 users / games 表**
  - Touches: `wrangler.toml`、`migrations/0001_init_users_and_games.sql`（新建）
  - Done when:
    - `wrangler d1 create guess-figure-db` 成功 + `wrangler.toml` 含 `[[d1_databases]]` block 含 binding `GF_DB`
    - `wrangler d1 execute guess-figure-db --local --command "PRAGMA table_info(users)"` 返回 4 字段（id, email, merged_from_user_id, created_at），其中 email/merged_from_user_id 的 `notnull` 列为 0
    - `wrangler d1 execute guess-figure-db --local --command "PRAGMA table_info(games)"` 返回 8 字段，含 INDEX (user_id, played_at DESC)
  - Depends on: nothing

- [ ] **T2 — 配两个 KV namespace bindings（GF_RATELIMIT + GF_LLM_CACHE）**
  - Touches: `wrangler.toml`
  - Done when:
    - `wrangler kv:namespace create GF_RATELIMIT` + `wrangler kv:namespace create GF_LLM_CACHE` 各返一个 ID
    - `wrangler.toml` 两个 `[[kv_namespaces]]` block，binding 名分别是 `GF_RATELIMIT` 与 `GF_LLM_CACHE`
    - `wrangler dev --local` 启动无 KV binding 错误（grep 启动 log "Using KV Namespaces"）
  - Depends on: nothing

- [ ] **T3 — env vars 占位 + app.d.ts 类型声明**
  - Touches: `.env.example`、`.env`（gitignore，仅本地）、`src/app.d.ts`
  - Done when:
    - `.env.example` 含 5 行：`LLM_BUDGET_DAILY=8000`、`LLM_BUDGET_PER_USER=50`、`RATE_LIMIT_PER_IP_DAILY=200`、`RATE_LIMIT_PER_USER_DAILY=200`、`AUTH_HMAC_SECRET=<32-char-random>`
    - `src/app.d.ts` 的 `App.Platform.env` interface 含 D1Database 类型的 `GF_DB`、KVNamespace 类型的 `GF_RATELIMIT` 与 `GF_LLM_CACHE`、以及 5 个 env vars 的字符串类型
    - `pnpm check` (svelte-check) 通过，无 type error
  - Depends on: T1, T2

### Phase 2 — 共享 lib + cookie 鉴权（T4-T6）

- [ ] **T4 — 验证 match-exact.ts 可被 server 端 import（共享 lib 接缝）**
  - Touches: `src/lib/match-exact.ts`（确认 export）、新建 `src/lib/match-exact.test.ts`（vitest）
  - Done when:
    - 不修改 match-exact.ts 业务逻辑（除非 export 不齐全需补）
    - `src/lib/match-exact.test.ts` 含 6 个测试 case（来自现有 jsdoc 例子：诸葛亮 / 孔明 / 带空白 / 错字不容忍等）全过
    - 在临时 `src/routes/api/_test_import/+server.ts` 或 vitest 中验证 `import { normalize, matchExactly } from "$lib/match-exact"` 编译通过
  - Depends on: T3

- [ ] **T5 — 实现 src/lib/server/auth.ts（HMAC sign / verify / D1 insert）**
  - Touches: 新建 `src/lib/server/auth.ts`、`src/lib/server/auth.test.ts`
  - Done when:
    - export `getUserId(request, env): Promise<{user_id, set_cookie?}>`
    - export `signCookie(uuid, secret): string`、`verifyCookie(cookie, secret): {valid, uuid?}` 两个纯函数
    - 单测 9 case 通过：合法 cookie 验签 PASS / 篡改 uuid FAIL / 篡改 hmac FAIL / 不同 secret FAIL / 无 cookie 新建 user / 已存 user 复用 / D1 INSERT OR IGNORE 幂等 / cookie 格式非法 FAIL / secret 缺失抛 500
    - `pnpm test src/lib/server/auth.test.ts` 全通过
  - Depends on: T1, T3

- [ ] **T6 — 实现 src/hooks.server.ts 统一鉴权 hook**
  - Touches: 新建 `src/hooks.server.ts`、`src/app.d.ts`（加 `App.Locals.user_id` 类型）
  - Done when:
    - hook handle 函数：对所有 `/api/*` 请求调 `getUserId`，挂到 `event.locals.user_id`，必要时把 Set-Cookie 加到响应 headers
    - `curl -sI http://localhost:5173/api/daily` 响应含 `Set-Cookie: gf_uid=...` + 三个 flag（HttpOnly/Secure/SameSite=Lax）
    - 第二次同 cookie 请求，响应 Set-Cookie 仍存在但 `Max-Age=31536000`（滚动续期）
    - 静态资源 `/_app/*` 不受 hook 影响（不发 Set-Cookie）
  - Depends on: T5

### Phase 3 — 限流缓存中间件（T7-T9）

- [ ] **T7 — 实现 src/lib/server/rate-limit.ts**
  - Touches: 新建 `src/lib/server/rate-limit.ts`、`src/lib/server/rate-limit.test.ts`
  - Done when:
    - export `checkRateLimits(env, user_id, ip, kind: "request" | "llm"): Promise<{ok, reason?}>`
    - export `incrementCounter(env, key, ttl_seconds=93600)` helper（93600 = 26 hours）
    - 单测 7 case：counter < 阈值 ok / >= 阈值 reject / KV.get 失败 failure open / LLM budget KV 失败 failure close（视作上限）/ 不同 user_id 互不影响 / 不同 IP 互不影响 / UTC 日切 key 不同
    - `pnpm test src/lib/server/rate-limit.test.ts` 全通过
  - Depends on: T2, T3

- [ ] **T8 — 实现 src/lib/server/llm-cache.ts**
  - Touches: 新建 `src/lib/server/llm-cache.ts`、`src/lib/server/llm-cache.test.ts`
  - Done when:
    - export `cacheKey(figure_id, aliases: string[], normalizedInput): string` 返回 `llm-cache:v1:<figure_id>:<sha256(aliases.sort().join("|"))>:<sha256(normalizedInput)>` 形态
    - export `cacheGet(env, key)` / `cacheSet(env, key, value, ttl=2592000)`（30 天）
    - 单测 5 case：同 figure+aliases+input 同 key / aliases 改后 key 不同 / aliases 顺序不同但 sort 后同 key / cacheSet 后立即 cacheGet 命中 / KV.put 失败 silent（cacheSet 返 ok=false 但不抛）
    - `pnpm test src/lib/server/llm-cache.test.ts` 全通过
  - Depends on: T2, T3

- [ ] **T9 — vitest 配置 + CI（如未配则配；若已配跳过）**
  - Touches: `package.json`（加 `vitest` devDep + `test` script）、`vite.config.ts`（如需）
  - Done when:
    - `pnpm add -D vitest @vitest/ui` 装上
    - `pnpm test` 命令存在且能跑 T4/T5/T7/T8 所有单测全过
    - GitHub Actions `.github/workflows/test.yml`（若仓库有 CI）含 `pnpm test` 步骤；如仓库无 CI 文件，本任务**跳过 CI 配置**只装本地工具
  - Depends on: T3

### Phase 4 — /api/check-answer 改造（T10-T11）

- [ ] **T10 — check-answer request body 改为 {input, figure_id} + server normalize/match-exact 短路**
  - Touches: `src/routes/api/check-answer/+server.ts`、`src/lib/check-answer-client.ts`
  - Done when:
    - server 端从 figure_id 查 figure（`import figures from "$lib/data/figures.json"` + 找出对应 figure）；不再信任 client 传的 target
    - server 端调用 `normalize(input)` + `matchExactly(input, figure)`；命中 → 返 `{correct: true, reason: "精确匹配"}`，**完全不调 LLM、不写缓存、不增 LLM 计数**
    - client `check-answer-client.ts` 调用方改为传 `{input, figure_id}`
    - 在浏览器实测：提交"诸葛亮"或"孔明"（exact match），DevTools Network 见响应 < 100ms 且 `cached` 字段不存在；`reason: "精确匹配"`
    - 现有单测 + 一个新增"server match-exact short-circuit"集成测试通过
  - Depends on: T4

- [ ] **T11 — check-answer 接入限流 + 缓存 + 降级 / network_error 字段**
  - Touches: `src/routes/api/check-answer/+server.ts`
  - Done when:
    - server pipeline 顺序：限流检查（请求级）→ match-exact 短路 → LLM 缓存查 → LLM 预算检查 → 调 LLM → 写缓存 + INCR LLM counters
    - 响应 schema 含可选字段 `cached?: true` / `degraded?: true` / `network_error?: true`
    - 临时把 `LLM_BUDGET_PER_USER=2` 后用同 cookie 连发 3 次非 exact match 输入；第 3 次响应含 `degraded: true`
    - mock 云雾 504 / network error 时响应含 `network_error: true` + 当次**不**调 INCR LLM counter
    - 同一 input 第二次提交（缓存命中）响应含 `cached: true` 且延迟 < 200ms（wrangler local 实测）
  - Depends on: T6, T7, T8, T10

### Phase 5 — 新端点（T12-T13）

- [ ] **T12 — 实现 /api/me（user 战绩汇总）**
  - Touches: 新建 `src/routes/api/me/+server.ts`
  - Done when:
    - GET 返 `{user_id, total_games, total_wins, total_score_30d, recent_games: [...最近 5 局]}`
    - 响应 header `Cache-Control: private, max-age=10`
    - 无 cookie 访问时，hook 已颁发 cookie，新 user 的 total_games=0 / total_wins=0 / recent_games=[]
    - 玩 3 局（D1 直接 INSERT 模拟）后 `curl -H "Cookie: gf_uid=..." /api/me` 返回 total_games=3
  - Depends on: T6

- [ ] **T13 — 实现 /api/game/finish（幂等写战绩）**
  - Touches: 新建 `src/routes/api/game/finish/+server.ts`
  - Done when:
    - POST body `{game_id, figure_id, won, revealed_count, score, given_up}`；用 `INSERT OR IGNORE`
    - 无 cookie 返 401
    - body 缺字段 / figure_id 不在题库 / revealed_count 越界 返 400
    - 同 game_id 连 POST 2 次，D1 `SELECT COUNT(*) FROM games WHERE id = ?` = 1
    - 写成功返 `{ok: true, game_id}`；返回的 game_id == 请求传入的（保证幂等下回 client 知道哪个）
  - Depends on: T6

### Phase 6 — 前端改造（T14-T16）

- [ ] **T14 — check-answer-client.ts 识别 degraded / network_error 不消耗线索**
  - Touches: `src/lib/check-answer-client.ts`、`src/lib/check-answer-client.test.ts`
  - Done when:
    - 调用方在收到响应后：`network_error: true` → **不**调 `game.consumeOnWrongAnswer()` + 抛特定异常 / 返回特定 flag 让 UI 处理；`degraded: true` 同上；`correct: false` 无两 flag → 调 `consumeOnWrongAnswer()`；`correct: true` → 调 `markWon()`
    - 单测 4 case 覆盖四种响应分支，game state mock 验证 `consumeOnWrongAnswer` 调用次数
    - `pnpm test src/lib/check-answer-client.test.ts` 全通过
  - Depends on: T11

- [ ] **T15 — UI loading state（200ms / 5s 双阶段提示）**
  - Touches: `src/lib/components/AnswerInput.svelte`（或调用 check-answer 的组件）
  - Done when:
    - 提交后立即禁用按钮 + spinner
    - 200ms 后显示文字"AI 裁判中..."（用 setTimeout）
    - 5s 后切换为"AI 正在思考较复杂的输入..."
    - 收到响应或 timeout 后恢复（清 timer + 启用按钮）
    - Chrome DevTools → Network → Slow 3G 实测：提交时见 200ms 后短文字 + 5s 后长文字
  - Depends on: T11

- [ ] **T16 — 游戏结束自动调 /api/game/finish + 集成 /api/me（轻量）**
  - Touches: `src/routes/+page.svelte`、`src/routes/play/+page.svelte`、`src/routes/daily/+page.svelte`、`src/lib/game-state.svelte.ts`（如需在 state 暴露 `game_id` 字段）
  - Done when:
    - 游戏 `finished` 状态变 true 时（won / gaveUp / exhausted），自动 POST `/api/game/finish` body 含 client `crypto.randomUUID()` 生成的 game_id
    - POST 失败不阻塞 UI（仅 console.warn，玩家结算 UI 已渲染）
    - 浏览器玩完一局后 `/api/me` 返回的 total_games 增 1
    - 002 范围内 `/api/me` UI 仅最小展示（layout footer 或 console.log），完整 UI 留 003
  - Depends on: T12, T13

### Phase 7 — Dashboard + 部署（T17-T18）

- [ ] **T17 — CF dashboard 配 env vars + D1 / KV bindings + 跑 production migration**
  - Touches: 无代码改动（dashboard 操作）；在 [`workflow/002-account-rate-limit/`](./) 新建 `deployment-notes.md` 记录步骤截图 + 时间
  - Done when:
    - CF dashboard → guess-figure → Settings → Environment Variables → 5 个 env vars 都填（production + preview）；AUTH_HMAC_SECRET 通过 `openssl rand -hex 32` 生成
    - dashboard → Functions → 绑定 D1 database `GF_DB` + 两个 KV namespaces
    - 本地跑 `wrangler d1 migrations apply guess-figure-db --remote`，看到 "Applied 1 migration"
    - production `curl -sI https://guess-figure.pages.dev/api/daily` 响应含 `Set-Cookie: gf_uid=...`
    - `deployment-notes.md` 记录每一步 + 截图
  - Depends on: T6, T11, T12, T13（实现完成后才能部署）

- [ ] **T18 — 配 CF dashboard Rate Limiting Rules（SPEC C6 表）**
  - Touches: dashboard 操作 + 更新 `deployment-notes.md`
  - Done when:
    - dashboard → Security → Rate Limiting → 2 个 rules 启用：
      - Rule 1: IP 60s 内 POST `/api/check-answer` > 60 次 → 阻断 5 分钟
      - Rule 2: IP 60s 内任意 `/api/*` > 200 次 → 阻断 5 分钟
    - 手动压测 70 次（脚本 + curl）触发 Rule 1，最后几次 HTTP 429
    - dashboard Analytics → Rate Limiting 触发计数 > 0
    - `deployment-notes.md` 补充
  - Depends on: T17

### Phase 8 — AC 验证 / Stage 8 准备（T19-T20）

- [ ] **T19 — 写 scripts/verify_ac.sh + 跑 22 条 AC 的 AI 通道**
  - Touches: 新建 `scripts/verify_ac.sh`（bash 或 .ps1 Windows 友好）
  - Done when:
    - 脚本含 22 条 AC 各自的 AI 验证命令（curl / wrangler / pnpm test 组合）
    - 跑一次脚本输出"X / 22 PASS"格式；至少 18 / 22 PASS（AC11 / AC15 / AC18-20 类 UI 体感的留人工）
    - 失败的 AC 编号 + 失败命令输出明确列出
  - Depends on: T17, T18

- [ ] **T20 — 调 verification-before-completion skill + 写 Stage 8 入场报告**
  - Touches: `workflow/002-account-rate-limit/07-implementation.md`（汇总 implementation 进度）+ 准备 Stage 8 入场材料
  - Done when:
    - `verification-before-completion` skill 调用记录写到 07-implementation.md
    - skill 输出"X 条 PASS 断言均有命令证据"或具体指出哪几条 AC 缺证据
    - 07-implementation.md 含 22 条 AC 的 PASS/PENDING 状态 + 每条对应的 commit hash + 证据位置（命令输出 / 截图）
  - Depends on: T19

---

## Task 依赖图（视觉版）

```
T1 ─┬─→ T3 ─┬─→ T4 ──→ T10 ──→ T11 ───┬──→ T14 ──┐
    │      │                          │           │
T2 ─┘      ├─→ T5 ──→ T6 ──┬──→ T12 ──┤           ├──→ T16 ──→ T17 ──→ T18 ──→ T19 ──→ T20
           │              └──→ T13 ──┤           │
           └─→ T7,T8,T9 ──────────────┘           │
                                                  └──→ T15 ────────────────────┘
```

**关键并行机会**：
- T4 / T5 / T7 / T8 / T9 可大体并行（只共享 T3 前置）
- T12 / T13 可并行（都只依赖 T6）
- T14 / T15 可并行（都依赖 T11）

**阻塞 critical path**：T1/T2/T3 → T5 → T6 → T11 → T16 → T17 → T18 → T19 → T20

---

## Task 规模估算（粗略，仅供节奏参考）

| Task | 估时 |
|---|---|
| T1, T2, T3 (基础设施) | 各 30-60 分 |
| T4, T5, T6 (auth) | T4 30 分 / T5 2-3 小时 / T6 1 小时 |
| T7, T8 (中间件) | 各 1-2 小时 |
| T9 (vitest 配) | 30-60 分 |
| T10 (check-answer body) | 1 小时 |
| T11 (check-answer 完整) | 2-3 小时（含集成测试） |
| T12, T13 (新端点) | 各 1-2 小时 |
| T14, T15 (前端改造) | 各 1-2 小时 |
| T16 (集成) | 2-3 小时 |
| T17, T18 (dashboard) | 各 30-60 分 |
| T19, T20 (验证) | 各 1-2 小时 |
| **总计** | **~ 25-35 小时**（含联调与单测） |

---

## 用户确认

- ☑ **已确认** — 确认时间：2026-05-22 ｜ 备注：通过 AskUserQuestion "确认 20 个 task, 进 Stage 7 Implementation"

> 一旦确认，本清单成为 Stage 7 的进度追踪单位。改范围请显式回到本阶段。
