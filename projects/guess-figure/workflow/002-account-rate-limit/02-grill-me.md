# Stage 2 ｜ Grill Me 质询拷问

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-2--grill-me-质询拷问)
>
> **强制工具**：调用 `grill-me` skill 驱动本阶段（v1.1+）。skill 会逐条审问用户的方案 / 设计，覆盖决策树的每个分支。
>
> **要点**：暴露隐藏假设、边界、失败模式、集成风险；每条具体到可执行。

## Skill 调用记录

- **Skill**：`grill-me`（v1.1+ 强制）
- **调用时间**：2026-05-22
- **交互轮数**：12 轮（Q1–Q12，其中 Q12 是 wrap-up）
- **预先 desk research**（不占用户轮次）：
  1. `WebSearch` 查证 MailChannels 在 2026 的可用性 → 2024-08 已终止 CF 免费集成，新 API 100 封/天免费，结论影响 Q1（账号范围选择）
  2. 读 [`src/lib/game-state.svelte.ts`](../../src/lib/game-state.svelte.ts)：确认纯客户端状态、零持久化，任何账号方案都需新增持久化层 → 影响 Q2 / Q3
  3. 读 [`src/lib/match-exact.ts`](../../src/lib/match-exact.ts)：现有 normalize 不做繁简、不容错字 → 影响 Q4 / Q5
  4. 读 [`src/routes/api/check-answer/+server.ts`](../../src/routes/api/check-answer/+server.ts)：发现 LLM prompt **包含 figure.aliases 列表** → 修正自己的 Q9 推荐（cache key 必须含 aliases hash）
- **覆盖的关键决策分支**：
  - 002 任务范围（账号 day-1 上线深度）
  - 持久化介质与 schema（D1 / KV / 不存）
  - cookie 鉴权机制（签名 / 加密 / 不签）
  - LLM 缓存 normalize 策略与 invalidate 触发
  - `/api/check-answer` server pipeline 顺序与是否引入 W
  - 限流主线 1 防御深度（P / Q / 双层）
  - 限流主线 2 阈值定法（实测 vs 拍数）
  - 限流触发 UX（429 / 倒计时 / 降级）
  - 003 邮箱迁移路径在 002 SPEC 的 schema 预留度
  - Stage 3 Prototype 范围
- **被搁置的分支与理由**：
  - V 与 X counter 检查顺序（顺序 / 并行 KV read）— 理由：implementation 细节，Stage 5 Plan 决；SPEC 写"两个 counter AND 条件"足够
  - 重度合法玩家 X 阈值具体边界 — 理由：需 Stage 3 实测 + 上线观测真实数据
  - 滚动续期 cookie 的 anti-fingerprint 实现细节 — 理由：implementation 细节
  - 邮箱 PII / GDPR — 理由：Q1 锁 A 范围（不含邮箱）后，002 无 PII，自我说明一句即可

## 拷问对象

来自 Stage 1 的两组候选方向（被锁定为 002 实现范围）：

- **账号**：方向 A（匿名持久 cookie ID + D1 战绩持久化），**不含**方向 B（邮箱 Magic Link）— B 推到 003
- **限流主线 1**（入口防滥用）：方向 P（CF dashboard Rate Limiting Rules）+ 方向 Q（Workers KV 计数器）双层防御
- **限流主线 2**（LLM 成本控制）：方向 U（KV 缓存 LLM 结果）+ 方向 V（每日全局 LLM 预算 + 降级）+ 方向 X（单 user/IP 日 LLM 上限）。方向 W（server blocklist）**不做**，留 SPEC 未来扩展

---

## 高危风险（必须先解决，已在本阶段拷问后给出处理动作）

- [x] **LLM 计费完全未知**（grill 出来的最大风险）。云雾中转 gemini-3.1-flash-lite 单次调用费用我都不知道；不实测就拍 V/X 阈值 = "SPEC 早于栈选定"失败模式翻版。**处理**：Stage 3 Prototype 必做"调云雾 100 次看账单"实测，回填 SPEC。
- [x] **LLM 缓存 key 必须含 aliases hash**。`/api/check-answer` 的 prompt 实际把 figure.aliases 列表喂给了 LLM，aliases 改变 → LLM 输出可能变 → 缓存按 figure_id 单维隔离会产生不一致结果。**处理**：cache key = `llm-cache:v1:<figure_id>:<sha256(aliases.sort().join("|"))>:<sha256(normalize(input))>`。
- [x] **降级期答错不应消耗线索**。SPEC v1.1 行为是"答错自动 nextClue"；若 LLM 调用因配额触发降级返 `correct: false`，会偷线索。**处理**：响应增加 `degraded: true` 字段；`check-answer-client.ts` 必须识别该字段，degraded 时**不**触发 `consumeOnWrongAnswer()`。SPEC AC 必须有一条专门验证此行为。
- [x] **client/server normalize 必须同一份代码**。Q5 锁定 server pipeline 含 match-exact 后，如果 client 和 server normalize 漂移，会出现 "client 判 true，server 重判 false" 诡异回归。**处理**：`match-exact.ts` 抽到 `src/lib/` 作为 client/server 共享 lib；SPEC constraint 显式声明。
- [x] **cookie 鉴权用 HMAC 防伪**。不签名的 cookie 让任何人都能伪造他人 user_id 读写战绩。**处理**：cookie = `<uuid>.<hmac_b64>`，HMAC secret 放 CF Pages env vars；server 验签通过才用 uuid 查 D1。

## 中危风险（已暴露 / 已记入 SPEC OQ，可暂缓但要承担）

- [ ] **HMAC secret 轮换 = 所有匿名用户身份归零**。准永久配置，泄露后果严重。SPEC 必须文档化：secret 轮换是一次性"剧本"，不能日常做；考虑写 runbook。
- [ ] **共用 NAT 下 IP-based 限流误伤**。学校 / 公司 NAT 下多用户共享 IP，触发主线 1 的 Q（按 IP）会互相挤额度。SPEC 接受："上轻量账号后 X 按 user_id 限"是缓解方案 — 这正是 002 在做的。
- [ ] **Workers free plan 配额被刷爆**。Q（KV 计数）的限流发生在 Workers 调用后；恶意刷 Workers 调用本身就会消耗 100k requests/天 免费额度。SPEC 必须写 P + Q 双层逻辑：P 在边缘拦截极端攻击保 Workers 配额、Q 做精细控制。
- [ ] **P 规则集是 dashboard 配置 ≠ git 源代码**。配置漂移风险。SPEC 必须把 P 的具体规则集（IP × Path × 时窗）写进 markdown 当 source of truth；dashboard 是镜像而非真理。
- [ ] **cookie 1 年到期 → 老用户战绩丢**。1 年没回的用户下次访问 cookie 过期，server 视作新用户。SPEC 锁滚动续期（每次请求续 expires）；接受"恶意脚本看似永久 cookie"为可接受 trade-off。
- [ ] **冷启动期缓存命中率为 0**。U 的 60-80% 命中率假设需要 1-2 周积累；冷启动期是 V/X 才是真兜底。SPEC 必须显式接受这个事实。
- [ ] **D1 免费 plan 限额可能撞**。2026 doc 说 5GB 存储 / 5M 读/天 / 100k 写/天（待 SPEC 阶段印证）。50 人 × 1000 日活 × 1 局 = 5万行写/天，三个月后可能撞限额。SPEC 写"撞限额时升级 paid plan / 收敛 schema" 的应急。
- [ ] **重度合法玩家被 X 限流误伤**。我推荐的 X=30/单 user/日 是占位；可能误伤"一天 10 局自由模式"的核心玩家。Stage 3 实测后定，env vars 可调。

## 低危 / 已知妥协

- [x] **不引入繁简转换**。沿用 client `normalize()` 不做繁简，繁体用户会让缓存 key 多一份。低优先级，影响小。
- [x] **不引入 server blocklist**（方向 W）。单字 / 纯姓氏 / 乱码这种低成本骚扰目前不防；server match-exact 已能挡住"客户端绕过 client match-exact 直打 server"的脚本攻击。
- [x] **不引入 Cloudflare Turnstile**（方向 S）。002 范围内不防机器人；脚本攻击的钱袋子风险由 X 单点 LLM 上限兜住。Turnstile 留作未来加固选项。
- [x] **client 不再纯客户端持有 user_id**（HttpOnly cookie）。前端需新增 `/api/me` 类端点拿用户信息。架构变化，SPEC 写明。

## 待用户回答的开放问题（OQ）

> 所有 11 个本阶段拷问的核心决策**已经在 grill 过程中由用户拍板**。下表是 Stage 4 SPEC 实际还需要填的 OQ（即"grill 已锁定方向但 SPEC 阶段需具体定数 / 定文案"的）：

| # | 问题 | 类型 | AI 推荐 | 决定 | 备注 |
|---|---|---|---|---|---|
| OQ1 | LLM 单次调用云雾计费具体单价 | technical | Stage 3 Prototype 实测后回填 | (待 Stage 3) | 决定 V/X 阈值 |
| OQ2 | V 日全局 LLM 预算具体值 | technical | 占位 5000/日；实测后定 | (待 Stage 3) | env vars `LLM_BUDGET_DAILY` 可调 |
| OQ3 | X 单 user/IP 日 LLM 上限 | technical | 占位 30/日；实测后定 | (待 Stage 3) | env vars `LLM_BUDGET_PER_USER` 可调 |
| OQ4 | P 在 dashboard 配的具体规则集（IP × Path × 时窗） | technical | 占位：同 IP 60s 内 > 60 次任何 `/api/*` 阻断 5 分钟；具体值 SPEC 决 | (待 SPEC) | dashboard 配置必须在 SPEC markdown 当 source of truth |
| OQ5 | 降级提示文案（V 触发 vs X 触发） | taste ⚠️ | V 文案"今日服务额度已用尽，仅接受精确答案"；X 文案"你今日额度已用尽，仅接受精确答案"；AI 起草仅占位 | (待用户改) | taste 类，必须用户改 |
| OQ6 | cookie maxAge | technical | 365 天 + 滚动续期（每次请求续到 365 天） | 推荐采纳 | SPEC 内拍板 |
| OQ7 | 是否在 `/api/me` 返回完整 games 历史 vs 仅汇总 | technical | 仅汇总（total_games, total_wins, recent_30d_score）；详情按需另端点 | 推荐采纳 | 减小响应体 |
| OQ8 | `/api/me` 的 cache 策略 | technical | `Cache-Control: private, max-age=10`；战绩更新后立刻失效（前端 invalidate） | 推荐采纳 | 平衡延迟与一致性 |

> `technical` = 客观技术决策（栈选、依赖版本、协议、性能预算等），AI 推荐 + 用户拍板即可
> `taste` = 主观偏好（文案、配色、命名风格、视觉调性），AI 推荐**只是占位**，**必须在 SPEC 中显式标注「用户应自己改写」**

## 已锁定的 11 项核心决策（grill 过程拍板，喂给 Stage 4 SPEC）

| Q | 决策 | 答案 | OQ 类型 |
|---|---|---|---|
| Q1 | 002 任务范围 | 完整限流 + 轻量 cookie 账号（不含邮箱） | taste |
| Q2 | 账号持久化 | D1 + `users(id, email NULL, merged_from_user_id NULL, created_at)` + `games(id, user_id, figure_id, won, revealed_count, score, played_at)` + INDEX (user_id, played_at DESC) | technical |
| Q3 | cookie 签名 | HMAC signed UUID（`<uuid>.<hmac_b64>`）+ HttpOnly/Secure/SameSite=Lax + 365天滚动续期 | technical |
| Q4 | LLM cache normalize | 沿用 `match-exact.ts` 的 `normalize()`，不繁简、不拼音；前缀 `llm-cache:v1:` 保留升级路径 | technical |
| Q5 | server pipeline | `server normalize → server match-exact → KV cache → LLM`；`match-exact.ts` 抽为共享 lib | technical |
| Q6 | 限流阈值 | Stage 3 实测后定，env vars 可调 | taste |
| Q7 | 降级 UX | 响应增 `degraded: true` 字段；前端 `check-answer-client.ts` 识别后**不消耗线索** + 弹明显提示 | taste+technical |
| Q8 | 主线 1 形态 | P + Q 双层防御（P dashboard 拦极端 + Q 在 Functions 按 IP/user 精细） | technical |
| Q9 | cache invalidate | key = `llm-cache:v1:<figure_id>:<sha256(aliases.sort().join("|"))>:<sha256(normalize(input))>` | technical |
| Q10 | 迁移预留 | D1 `users` 表加 nullable `email TEXT UNIQUE` + `merged_from_user_id UUID NULL`；不写 merge 代码 | technical |
| Q11 | Stage 3 范围 | 仅 LLM 计费实测脚本（调云雾 100 次 + 看账单 + 回填 SPEC） | taste |

## 用户可接受暂时搁置的问题

- [x] V 与 X counter 检查顺序（顺序 vs 并行 KV read）— Stage 5 Plan 决
- [x] 滚动续期 cookie 的 anti-fingerprint 实现细节 — implementation 细节
- [x] 缓存冷启动期实际成本 — 上线后 1-2 周观测，SPEC 写明
- [x] 邮箱 PII / GDPR — 002 无邮箱，无 PII；SPEC 自我说明"cookie 仅 UUID，无个人识别信息"即可
- [x] 003 邮箱迁移路径 — 由 003 的 SPEC 处理
- [x] `match-exact.ts` 抽共享 lib 的 import 形态 — Stage 5 Plan 决
