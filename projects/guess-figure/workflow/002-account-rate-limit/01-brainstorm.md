# Stage 1 ｜ Brainstorm 头脑风暴

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-1--brainstorm-头脑风暴)
>
> **要点**：发散 3–5 个方向；每个配一句核心思路 + 一句主要权衡；**不评判出胜者**（由用户决定）。

## 任务

给已上线的 [guess-figure.pages.dev](https://guess-figure.pages.dev) 增加两个能力（合并为单一 SPEC，因二者强耦合）：

1. **账号系统**：注册 / 登录 / session / 用户标识。
2. **API 限流**：保护 `/api/check-answer` 与 `/api/daily`（以及未来的账号相关接口）。

**已锁定的前置约束**（用户已确认 / 项目现状）：

- 技术栈停留在 **Cloudflare 生态**：CF Pages + Pages Functions + 可选 D1 / KV / Durable Objects / Workers Email；不引入 Vercel / Supabase / Neon 等离开 CF 的服务。
- **账号"完全可选"**：匿名也能玩、能看题、能提交答案；登录只是为了存档、个人战绩、未来排行榜。**直接含义**：限流默认按 IP 起步，账号上线后可叠加 user 维度（已登录用户拿更高额度或专属池）。
- 现状无任何用户态；题库在 git（`figures-batch*.json`）；前端是 SvelteKit 5 + adapter-cloudflare。
- 用户群是**非技术休闲玩家**（中国历史人物猜谜），不是开发者社区——这条会偏置某些方向的可用性评分。

---

## 方向 — 账号系统

### A — 匿名持久 ID（cookie-only，无真账号）

- **核心思路**：首次访问生成 UUID 写入 HttpOnly cookie；server 用 KV 或 D1 以 UUID 为 key 存战绩。用户的"账号"=这个 cookie 持有者，无密码、无邮箱、无任何凭证。
- **主要权衡**：零摩擦（用户根本不知道自己"登录"了）、零运营成本；但 cookie 丢/换设备/清理浏览器 → 身份永久丢失；限流绕过门槛极低（清 cookie 即重置）；不能视为真正的"账号"功能交付。

### B — 邮箱 Magic Link（passwordless）

- **核心思路**：用户填邮箱 → 后端发一封含一次性 token URL 的邮件 → 用户点链接 → server 校验 token，颁发 session。D1 存 `users(email, created_at, ...)` + 短期 `magic_tokens` 表。发件用 MailChannels（Cloudflare 边缘集成）或 Resend。
- **主要权衡**：体验佳（无密码、跨设备）+ 用户群接受度高（"输邮箱"是国民认知）；但 **CF 生态无原生邮件发送**——MailChannels 2024 起政策有变（不再对所有 Workers 免费），实际可能要 Resend / SendGrid 等外部 SMTP，违反"留在 CF 生态"的精神（**或**重新定义"CF 生态"是否含 MailChannels 配额内的边缘邮件）。

### C — GitHub OAuth（单一社交登录）

- **核心思路**：用 GitHub OAuth 2.0；在 Pages Functions 处理 `/auth/github/callback`；D1 存 `users(github_id, login, avatar_url, ...)`。无注册流程，1 click 进。
- **主要权衡**：1-click + 零密码运营成本 + CF Pages 上有 [`@auth/sveltekit`](https://authjs.dev/) 类似 lib 可直接复用；但用户群是**非技术休闲玩家**，GitHub 账号普及率低（< 10%？需印证），强行 GitHub 会过滤掉绝大部分潜在用户；产品定位偏移成"码农玩的猜历史"。

### D — 托管认证（Clerk / Auth.js + 多 provider）

- **核心思路**：接 Clerk（或自部署 Auth.js）做多 provider（Google / GitHub / Apple / 邮箱）统一入口；前端用 SDK，后端只校验 JWT；user profile 在 Clerk，本地 D1 仅存 game-data（战绩、用户名映射）。
- **主要权衡**：1 周内出活、UI 都送、provider 自由切换；但引入**外部依赖**（Clerk 服务挂 → 站点登录挂）+ **离开 CF 生态边界**（虽然 Clerk 提供 edge SDK，但用户数据归 Clerk）+ 月活破阈值后收费；对 vibe-coding-lab 这种"端到端自建"练手项目，托管方案会让 Stage 4–7 的内容变薄。

### E — WebAuthn / Passkey（被动登录）

- **核心思路**：浏览器原生 passkey（Touch ID / Face ID / Windows Hello / 1Password 等）；在 Workers 用 `@simplewebauthn/server` 跑注册 + 断言流程；D1 存 `users(id, credential_id, public_key, ...)`。
- **主要权衡**：未来感强、零摩擦（一次面部识别）、零密码运营成本、CF 边缘原生；但**用户教育成本高**——猜历史的玩家很可能不知道 passkey 是什么、看到弹窗会犹豫；需配 fallback（哪种？又回到 A/B/C/D 之一）；与休闲游戏的定位不太匹配。

### F — 用户名 + 密码（传统）

- **核心思路**：自管 D1 的 `users(username, password_hash, salt, ...)`；用 bcrypt/scrypt 哈希；session cookie；忘记密码需邮件链路（回到 B 的发件问题）。
- **主要权衡**：玩家最熟悉的认知模型；但 2026 年自管密码已是反模式——密码泄露责任、找回流程必须有邮件能力（=方向 B 的依赖）、合规要求（弱密码检测、撞库防护、暴破限流）、UX 反而最差。**Likely YAGNI**：除非你想体验"做认证"的全栈，否则功能价值密度低。

---

## 方向 — 限流系统

### P — Cloudflare Rate Limiting Rules（dashboard 配，无代码）

- **核心思路**：在 Pages 项目的 Cloudflare dashboard 配 Rate Limiting Rules——按 IP × Path × 时窗自动 429。零代码、零部署。
- **主要权衡**：边缘原生、零运维；但 Pages 免费 plan 的 rate limiting rule 数量有上限（需印证当前 2026 政策）、规则灵活度有限、**无法按 user 维度限流**（dashboard 不知 session）→ 账号上线后必须再叠加方向 Q/R。

### Q — Workers KV 计数器（在 Functions 里手写）

- **核心思路**：每次 `/api/check-answer` / `/api/daily` 调用，按 `ratelimit:<ip-or-user>:<endpoint>:<window>` 在 KV 做 INCR，超阈值返 429。窗口实现可选 fixed window / sliding window log。
- **主要权衡**：完全可控（按 IP / user / endpoint 灵活分桶）、易理解、与账号方案天然兼容（已登录则用 user，未登录用 IP）；但 **KV 是最终一致**——计数跨边缘有延迟，高并发下漏判；KV 写入有成本（每次请求 = 1 写）；50 人题库的小项目这点 cost 可忽略。

### R — Durable Objects（强一致 token bucket / sliding window）

- **核心思路**：每个 IP / user 路由到唯一的 DO 实例做 token bucket 或精确 sliding window；DO 内的 storage 强一致，counter 不会有 race。
- **主要权衡**：限流精确度最高、可做复杂策略（如逐 endpoint 多桶）；但 DO 有 invocation cost + 冷启动 + 实现复杂度——对 50 人题库 + 单人小项目是**过度工程**；DO storage 也按读写计费，长尾 IP 会撑出垃圾对象需 TTL 清理。

### S — Cloudflare Turnstile（人机验证替代限流）

- **核心思路**：在 `/api/check-answer` 前要求合法 Turnstile token（前端透明渲染 → 提交时附带），server 校验通过才放行。理论上挡住机器人后限流压力下降。
- **主要权衡**：防自动化滥用最强、用户体感几乎无感（Turnstile 大多 invisible challenge）；但**不是传统时窗限流**——单个人类用户疯狂手动点也能打爆配额，需要叠加 Q/R 才完整；Turnstile 也有调用成本与 CF 端配额。**与 P/Q/R 不互斥，是补强**。

### T — Cloudflare WAF Custom Rules（域名级边缘规则）

- **核心思路**：在 Pages 自定义域名（V1 没自定义域名，是 `*.pages.dev` 子域）的 WAF 上配 custom rules，如"同 IP 30 秒内 > N 次 POST `/api/*` 拒绝"。
- **主要权衡**：边缘拦截、SQL 注入 / 常见攻击规则一并享受；但 **WAF custom rules 主要在 Pro / Business plan 上**（免费 plan 仅 managed rules），且 `*.pages.dev` 子域受 CF 全局 WAF 管，自己加规则受限；任务 003-自定义域名之前优先级排不上。

---

## 给用户的建议下一步（Stage 2 Grill Me 拷问哪一组）

不评胜者，但有一组「**最值得在 Stage 2 拷问到底**」的候选：

- **账号侧的高频候选**：**B（Magic Link）** + **A（匿名持久 ID）**——B 是真账号的低摩擦版（最符合"完全可选"语境），A 可作 B 还没登录前的 fallback；两者可**并存**而非互斥。
- **限流侧的高频候选**：**P（CF 原生 Rules，先开起来）** + **Q（KV 计数，给 API 层精细控制）**——P 是当下零代码兜底，Q 是为 user 维度（账号上线后）做准备。

**Stage 2 Grill Me 重点要拷问的开放问题（先列出来，由 `grill-me` skill 在下一阶段正式驱动）**：

1. 匿名持久 ID 与真账号的**数据迁移**：用户匿名玩了 30 天积累战绩 → 决定注册 → 战绩怎么"接续"过去？冲突怎么办？
2. **MailChannels 在 2026 年的实际可用性**——是不是仍可在 Workers/Functions 免费发邮件？如果不行，方向 B 是否需要降级到 A 或换 Resend（牺牲"CF 生态"约束）？
3. **限流的具体阈值与窗口**：`/api/check-answer` 一局正常 5-10 次提交，恶意刷可达 1000+/分钟，阈值定在哪？误伤合法重玩用户的成本是多少？
4. 限流**触发后的 UX**：429 直接弹错误？还是冷却倒计时？还是降级模式（只能看不能提交）？
5. **session 存哪、TTL 多长**：cookie 直接放 signed token（无服务端 session 表）vs server 端 session 表（D1 / KV）—— 这影响登出、强制下线、跨设备会话管理。
6. 账号与现有 **`game-state.svelte.ts`（客户端 reactive state）的接缝**：登录后状态怎么 reconcile？匿名期的进度上传策略？
7. **PII 与隐私**：邮箱算 PII，CF 数据驻留地点 / 是否需要隐私声明 / 是否触发 GDPR（项目无 EU 地区屏蔽）？
8. **限流"按 user"前的过渡**：账号上线第一天，老的匿名 IP-based 限流要不要立刻替换？还是叠加运行一段时间？切换风险？

这些问题不要在本阶段回答——**Stage 2 由 `grill-me` skill 驱动**逐条拷问。

---

## skill 调用记录

- **本阶段 skill**：`brainstorming`（v1.2 推荐）
- **调用方式**：通过 Skill 工具加载 `C:\Users\61780\.claude\skills\brainstorming` 的指令上下文，借用其"一次一个 clarifying 问题 + 多方向发散"框架。
- **校准说明**：brainstorming skill 默认会驱动「发散 → design doc → 调用 writing-plans」端到端流程；与 vibe-coding-lab workflow-spec v1.2 的「Stage 1 仅发散，Stage 2 用 grill-me 拷问，Stage 4 才写 SPEC」冲突。本次只采用 skill 的发散框架，**不**写 design doc 到 `docs/superpowers/specs/`，**不**自动调用 writing-plans——这些动作由 workflow-spec 的后续阶段在自己的关卡处理。
- **唯一 clarifying 问题**：账号强制度（完全可选 / 半强制 / 全强制 / 不确定）。用户答：**完全可选**——直接锁定限流默认按 IP，账号方案需支持匿名上手。
