# Stage 5 ｜ Plan 计划

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-5--plan-计划)
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)
>
> **要点**：从已确认的 SPEC 出发，回答「怎么做」与「按什么顺序」。
>
> **基于**：[04-spec.md](./04-spec.md) v1.0（用户 2026-05-21 确认）+ [03-prototype.md](./03-prototype.md) 实测结论 + [02-grill-me.md](./02-grill-me.md) 9 决策

---

## Approach

### 总体技术策略

**前端密集 + 轻后端 + 题库即代码**：

- **前端密集**：SvelteKit 5 SSR + Svelte 5 runes 状态，**所有游戏逻辑跑在前端**（计分、线索状态机、求救分支、localStorage、分享按钮）。无需后端持久化用户数据。
- **轻后端**：CF Pages Functions（`+server.ts`）只做 2 件事 ——「LLM 模糊匹配代理」+「daily 路由」。无 DB、无 session、无长驻进程。
- **题库即代码**：50 人物 × 7 线索 JSON-in-git（`src/lib/data/figures.json`），跟代码一起 bundle 部署。增量加题 = Python 脚本生产 → 人工审核 → `git push` → CF Pages 自动 redeploy。
- **LLM 极简调用**：运行时仅在「玩家提交答案 + 异称表精确匹配失败」时调云雾 LLM 一次（预估 95% 玩家命中异称表无需 LLM）。
- **玩法形态**：方向 B+D 合并 —— B 是底层（5 标准 + 2 求救 + 玩家随时自由输入），daily 是 B 的内容投放变体（同游戏组件、不同入口和限次）。

### 关键架构决策（呼应 Stage 1/2/3）

| # | 决策 | 选 | 不选 | 理由 |
|---|---|---|---|---|
| C1 | 前端框架 | SvelteKit 5 + Svelte 5 runes | Astro/Next/SolidJS | Stage 2 决策 9 用户偏好 |
| C2 | 部署平台 | Cloudflare Pages | Vercel/Netlify | 沿用 personal-website 经验 |
| C3 | LLM 模型 + 提供商 | gemini-3.1-flash-lite via 云雾中转 | Claude/DeepSeek/GLM | Stage 3 prototype A 实测 4 维领先 |
| C4 | 数据存储 | JSON-in-git | DB（PG/SQLite/D1）| 决策 9b，V1 无用户数据 |
| C5 | 内容生产路径 | 爬虫为主（维基中文+Wikidata+百度补盲）+ LLM 二次加工 | 纯 LLM 生成 / 纯人工手写 | 决策 2/3，Prototype A 验证可行 |
| C6 | 题库 schema | `{id, name, aliases[3-5], clues[7]{text, difficulty 1-7}, source, wiki_url}` | 简化或扩展 | Prototype A 跑通且 LLM 严格遵循 |
| C7 | LLM 模糊匹配 prompt | 沿用 Prototype B 的草案 + Stage 7 补 30-50 用例集 finalize | 完全重写 | Prototype B 实测 OK，SPEC OQ3 确认 |
| C8 | 反作弊 | localStorage 防同浏览器复玩 | IP/cookie/账号 | Stage 2 决策 8，V1 软漏洞接受 |

## Phases

> 8 个有序 phase，总工程量约 16 工作日（学习 SvelteKit / Svelte 5 时间另算）。每个 phase 完成后可见、可验证、可单独 commit。

### Phase 1 — 项目初始化 + CI/CD 链路全通（~1 天）

**交付**：
- `projects/guess-figure/src/` 下完整 SvelteKit 5 项目骨架（独立于 `workflow/.../prototype/B-deploy/`，作为正式生产代码）
- `package.json` / `svelte.config.js` / `vite.config.ts` / `tsconfig.json` / `app.html` / 占位首页 `+page.svelte`
- `pnpm install` + `pnpm dev` 本地通、`pnpm build` 通
- CF Pages dashboard 创建 production project `guess-figure-proto`（或正式名）+ Root directory 配置 + 第一次 `git push` 触发 auto deploy 成功（占位页能上线）

**为什么排第一**：所有后续 phase 都依赖部署链路存在；越早通就越早暴露 CI/CD 坑。Prototype B 已经踩过一遍（pnpm allowBuilds、`$env/dynamic/private`、CF Pages Root directory），第二次会快。

### Phase 2 — 内容 pipeline 生产化 + 50 人题库（~3 天）

**交付**：
- `projects/guess-figure/scripts/generate_figures.py`（从 prototype A 的 `proto_generate.py` + `batch_generate.py` 提升到生产质量：错误重试、log、命令行参数 `--names "a,b,c"` 或 `--batch N`）
- `scripts/merge.py`（合并新批次到主题库、去重、按 id 排序）
- `scripts/quality_check.py`（自动校验 figures.json：schema 合规、异称数 3-5、难度 1-7 齐、难度 1-5 不含异称、难度 1 不含朝代）—— 改进 prototype A 的 `quality_score` 函数（修复"春秋"/"明（发明）"的 false positive）
- `src/lib/data/figures.json` —— **50 个中国史人物 × 7 条线索**，由你审核通过
- 50 人按 SPEC OQ2 推荐准则覆盖朝代 + 类型 + 知名度分布

**为什么排第二**：内容是核心资产，50 人需要边跑边审核（漫长串行工作），尽早开始；后续所有前端 phase 都依赖题库存在（前端可以先用 mock 5 人临时跑）。

**子步骤**（分 5 批 × 10 人推荐：先秦+汉 / 三国+晋 / 唐 / 宋+元 / 明清+近代）：每批 LLM 生产 → 你审核改错 → merge → commit `task-T2.N: 题库 +10 人物（朝代 X）`

### Phase 3 — 核心游戏组件（日常模式）（~3 天）

**交付**：
- 路由 `/play` —— 日常模式游戏页
- 线索状态机（Svelte 5 runes）：当前展示几条、玩家可点"再来一条"或随时输入
- 输入框 + 提交按钮（中文 IME `compositionstart`/`compositionend` 事件正确处理）
- 异称表精确匹配（前端、无 LLM）：规范化（去空格 / 繁→简 / 全→半角 / 去标点）+ 比对
- 调 `POST /api/check-answer`（fallback 用 mock 响应先开发）→ 显示对/错 + 计分
- 计分公式：标准猜中 `(6-k)*20` = 100/80/60/40/20

**为什么排第三**：游戏页是产品核心。先做单模式（日常）跑通再扩 daily 模式；先用 mock 响应隔离前端开发节奏（不依赖后端 Phase 5 完成）。

### Phase 4 — 求救机制 + 失败 / 放弃路径（~1 天）

**交付**：
- 5 条线索用完触发"求救模式"：UI 显示"再要 2 条线索（求救，最高 10 分）" + "放弃看答案"双按钮
- 求救流程：点击 → 显示线索 6 → 再次输入或要 7 → 猜中得 10 分
- 7 条用完未猜中 → 自动显示答案
- 失败 / 放弃显示：人物名 + 一句话简介（来自 figures.json 的字段或单独从 Wikidata description）+ 维基链接（点击新窗口打开）+ "再玩一局"按钮
- 计分：求救猜中 10，放弃/7 条用完 0

**为什么排第四**：求救是核心机制但比基础游戏次要；先把基础游戏跑顺再加分支，避免组件状态机过早复杂化。

### Phase 5 — 后端 API（~1 天）

**交付**：
- `/api/check-answer` `+server.ts`：接收 `{input, target}`，prompt 沿用 Prototype B 草案完整版 + 边界规则；调云雾 LLM；JSON 解析容错；返回 `{correct, reason}`
- `/api/daily` `+server.ts`：按 UTC 16:00 切换今日题 ID（= 北京 0:00）；返回 `{figure_id, date}`
- 30-50 用例集 `tests/llm-fuzz.test.ts`：覆盖`孔明`/`卧龙`/`诸葛丞相`/`诸葛梁`/`曹操`/`亮`/`诸葛`/繁简/错字
- 错误降级：HTTP 5xx → 502；超时 10s → 504；非 JSON → `{correct:false, reason:"判定异常"}`；写后端日志

**为什么排第五**：可以跟 Phase 3-4 并行（前端用 mock 测）；但建议 Phase 1（部署链路验证）之后做，避免遇到 CF Pages Functions runtime 问题阻塞核心开发。

### Phase 6 — daily 模式（~1 天）

**交付**：
- 路由 `/daily` —— 复用 Phase 3-4 游戏组件 + 加 localStorage 防复玩
- localStorage key `daily_played_YYYYMMDD=true`，玩前检查
- 已玩过 → 显示"今日已完成：X 分" + 分享按钮 + 倒计时下次换题
- 分享按钮：复制文字到剪贴板（`navigator.clipboard.writeText`），格式 `猜历史人物 #N\n❓❓❓✅ 用了 X 条线索\nhttps://<domain>`（标准 ✅ / 求救 🆘 / 失败 ❌）
- daily 题耗尽降级（SPEC OQ1 已决）：figure_id 超过题库长度时进入"经典回顾"轮播，UI 显示"今日：经典回顾 第 N 期"

**为什么排第六**：daily 复用 Phase 3-4 组件 + 加少量 UI 包装。放在游戏组件成熟后避免来回改组件状态机。

### Phase 7 — 移动端响应式 + 视觉打磨 + taste OQ 决定（~2 天）

**交付**：
- 移动端响应式（媒体查询 + 320px-2560px 适配）
- 真机测：iOS Safari 中文 IME 输入 + Android Chrome 中文 IME 输入
- 视觉风格定型（SPEC OQ9 选定：极简 / 中国风 / 卡牌风之一）
- 首页文案、Hero、品牌名（SPEC OQ8、OQ11 用户拍板）
- pages.dev 子域名 / 自定义域名（SPEC OQ7）

**为什么排第七**：先功能跑通再打磨外观；taste 类决定推迟到这阶段，不让 taste 阻塞核心功能；真机测在所有功能完成后做更有意义。

### Phase 8 — QA + 上线 + 缓冲（~3 天）

**交付**：
- 15 条 AC（SPEC v1.0）逐条验证（AI 通道自动测 + 人工通道真机操作）
- LLM 边界用例 30-50 个跑通过
- 移动端真机 bug 修复
- 题库错误用户报错 / 你抽查修正（fix(TX): commit）
- 最终上线 URL 稳定 24 小时（CF Pages 稳定性观察）

**为什么排第八**：必须留 buffer 处理 LLM 边界用例 / 移动端真机问题 / 内容生产二次修正。Stage 7→8 强制调 `verification-before-completion` skill（v1.2）。

## Dependencies

### Phase 间依赖（阻塞顺序）

```
P1 (初始化) ──────────────────────────────────────────────
                ↓
P2 (内容)  ────┬─→ P3 (游戏)  ──┬─→ P4 (求救)  ──┐
                │                ↓                  ↓
                └─→ P5 (API)  ───→ ... ─→ P6 (daily) ─→ P7 (UI 打磨) ─→ P8 (QA)
```

- **P1 阻塞所有**：没部署链路，所有后续 phase 无法验证 "线上行为正确"
- **P2 阻塞 P3 真实玩**：但 P3 可用 mock 5 人 fixture 并行开发，最终接入真题库
- **P5 阻塞 P3 真实判定**：但 P3 可用 mock LLM 响应并行开发，最终接入真后端
- **P6 依赖 P3+P4 完整**：daily 复用游戏组件，组件不能再改状态机
- **P7 依赖功能 phase 全完**：先功能再外观，否则改外观又改功能容易反复
- **P8 依赖一切**

### 触碰共享 / 脆弱代码

- **题库 schema 是核心契约**：P2 定下后，P3/P5/P6 所有 phase 都按此读写。改 schema = 回 P2 重生产 50 人题库。**P2 完成前必须确认 schema 不变。**
- **LLM 模糊匹配 prompt**：P5 定下后，前端调用契约不能改（输入/输出 schema）；prompt 内部可调
- **`src/lib/data/figures.json`**：所有 phase 读，仅 P2/P8 可写（增量加题或 bug 修）；改这个文件等于改契约
- **`+server.ts` 文件**：CF Pages Functions 运行时跟 SvelteKit 主线程不同（edge runtime），不能依赖 Node 特有 API

### 需要外部输入

- **CF Pages dashboard**：P1 创建 project + Root directory；P5 加 env vars；P7 自定义域名（可选）
- **云雾 API key**：所有 phase 共用，配额监控
- **维基中文 / Wikidata API**：P2 内容生产时依赖，离线脚本挂了 P2 暂停
- **GitHub repo**：所有 phase 推送，CF Pages 监听 push 自动 deploy

## Risks

按 grill-me §高危风险 + Prototype 未验证项排序：

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| **R1** | 50 人 LLM 加工质量不稳定（事实错误 / 难度违规 / 异称缺漏）| 高 | 高 | **P2 增量小批（每次 5-10 人）跑完审完再下一批，不一次性产 50**；`quality_check.py` 自动检测违规；你审核兜底事实错误 |
| **R2** | LLM 边界用例失误（"诸葛丞相"判 NO，"曹操"判 YES）| 中 | 中 | **P5 配 30-50 用例集** 自动测；Prompt 引入"边界规则示例"明示典型对错；Stage 8 真机再过一遍 |
| **R3** | 移动端中文 IME 提交时丢字 | 中 | 高（直接坏体验）| **P3 实现输入框时就处理 compositionend/compositionstart**（不靠 P7 临时补）；P7 真机 iOS Safari + Android Chrome 各 1 次 |
| **R4** | daily 第 51 天起没题（题库耗尽降级缺失）| 中 | 中 | SPEC OQ1 已决「经典回顾轮播」；**P6 实现这个降级**；P8 测试当天行为；第 40 天起脚本自动告警提醒补题 |
| **R5** | CF Pages Functions cold start 慢导致首次 LLM 判定 > 3s | 低 | 中 | CF Edge cold start ~50ms 不显著；监控 CF AI Gateway 延迟；超额加"warming ping"（V1 不做）|
| **R6** | LLM API 速率限制（云雾 / 上游 Gemini）| 低 | 中 | 单次 LLM ~4s + 95% 玩家命中异称表无 LLM；预估月调用 3-4 万次远未触限；监控 CF AI Gateway 配额 |
| **R7** | 维基中文 / Wikidata API 变更或下线 | 低 | 高（影响 P2 内容生产）| 离线脚本，挂了可手动救场；P2 已记录爬虫源 fallback 顺序（维基 → Wikidata → 百度补盲）|
| **R8** | gemini-3.1-flash-lite 在云雾上被下线 / 改名 | 低 | 高 | 通过云雾控制台关注；备选 `gpt-5.4-nano`（Prototype A 实测可用，质量略弱但能跑）—— 切换只需改 `.env` 一行 |
| **R9** | Svelte 5 runes 新语法 user 学习曲线 | 中 | 中 | P3 实现核心组件前先花 0.5 天看 Svelte 5 runes 官方教程；prototype B 已有 `+page.svelte` 示例参考 |
| **R10** | CF Pages 部署 multi-project 共仓库的 Root directory 配置失误（已在 prototype B 踩过）| 已踩过 | 中 | Prototype B 已验证 Root directory 配置；P1 第一次部署直接复用经验 |

## Test strategy

| 层 | 覆盖什么 | 工具 | 在哪个 phase 实现 |
|---|---|---|---|
| **前端单元** | 计分公式（100/80/60/40/20/10/0）/ 异称表精确匹配 / 输入规范化 / 线索状态机 / IME composition 处理 | **Vitest**（SvelteKit 内置）| P3 / P4 写代码时一起 |
| **后端单元** | LLM 响应 JSON 解析容错 / daily 路由按 UTC 16:00 切换 / API 错误降级 | Vitest | P5 |
| **集成测试**（端到端）| 完整游戏 flow（日常 + daily）；点击交互；分享按钮；移动响应式 | **Playwright** | P8（晚一点，所有 UI 稳后才有意义）|
| **LLM 边界用例集**（30-50 用例）| `诸葛亮` / `孔明` / `卧龙` / `诸葛丞相` / `诸葛梁` / `曹操` / `亮` / `诸葛` / 繁简 / 全半角 / 错字 | `tests/llm-fuzz.test.ts` 单独跑（需 LLM key）| P5 |
| **题库 schema 校验** | aliases 数 / clues 数 / 难度齐 / 难度 1-5 不含异称 / 难度 1 不含朝代 | `scripts/quality_check.py` 跑 `figures.json` | P2 每批合并前 |
| **Stage 7→8 过渡（v1.2 强制）**| `verification-before-completion` skill：每个 task done-when 必须有验证证据（跑命令出 PASS/FAIL，不能字面 PASS） | skill 调用 | Stage 7 → 8 过渡时 |
| **Stage 8 Human QA** | 真机移动端 / 多浏览器 / SPEC 15 条 AC 人工验证路径 / 内容 spot check（随机抽 10 人审）| 浏览器 + iOS/Android 真机 | Stage 8 |
| **Stage 9 Acceptance** | SPEC 15 条 AC 逐条 PASS 核对（AI 通道 + 人工通道两边都 PASS）| SPEC AC 表 | Stage 9 |

### 不覆盖（明示）

- **第三方库行为**：SvelteKit / Vite / OpenAI SDK 假设正确，不写测试
- **CF Pages 平台行为**：edge runtime / env vars / 部署，Prototype B 已验证
- **维基爬虫 mock**：mock 维基响应反而比真实响应更脆，prototype A 已验证可行
- **跨浏览器自动化**：V1 仅 Playwright 一种 runtime（Chromium）；其他浏览器留人工 QA

---

## 下一步

按 workflow-spec：

1. 用户 review 本 Plan（不是人工关卡，但建议过一眼）
2. 进 **Stage 6 Tasks（人工关卡 ★）**：把 8 个 Phase 拆成具体 task 列表（每个 task 含 Touches / Done when / Depends on，按 `plan-and-tasks.md` 规范）
3. 用户确认 Tasks → 进 Stage 7 Implementation
