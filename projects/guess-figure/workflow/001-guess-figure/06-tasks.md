# Stage 6 ｜ Tasks 任务 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-6--tasks-任务人工关卡)
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)
>
> **要点**：每个任务**可独立完成**；标 Touches / Done when / Depends on；**用户未确认前不得进入 Stage 7**。
>
> **v1.2 commit 前缀约定**：
> - `task-TX:` 新 task 首次实现
> - `stage-N:` 阶段产出 / 转换
> - `fix(TX):` 已完成 task 的 bug 修复（Stage 8 回路用）
> - `chore:` / `docs:` / `spec(vX.Y):` 其它治理
>
> **每个 task 的 Done when 必须可验证**（不能写"功能完成"这种主观断言，要写能跑出证据的条件）。
>
> **基于**：[05-plan.md](./05-plan.md) 8 个 Phase 拆分

---

## 任务清单

> 22 个 task 对应 8 个 Phase。粒度约 0.3-1.5 工作日/task。Depends on 标"nothing"的可立即并行启动。

### Phase 1 — 项目初始化 + CI/CD（~1d）

- [x] **T1 — SvelteKit 项目骨架（独立于 prototype/B-deploy）** ✅ 2026-05-21
  - Touches: `projects/guess-figure/package.json`, `svelte.config.js`, `vite.config.ts`, `tsconfig.json`, `pnpm-workspace.yaml`, `app.html`, `app.d.ts`, `src/routes/+page.svelte`（占位首页）, `.env.example`
  - Done when: `pnpm install && pnpm build` 全部通过 + `pnpm dev` 本地访问 http://localhost:5173 看到占位首页 ✅
  - Depends on: nothing

- [x] **T2 — CF Pages production project 创建 + 第一次 deploy** ✅ 2026-05-21
  - Touches: CF Pages dashboard（创建 project `guess-figure`）+ env vars 配置 + Root directory = `projects/guess-figure`
  - Done when: `git push` 触发 CF Pages auto deploy，部署成功 + 访问生产 URL 看到占位首页 + 后续 push 能正确触发新 deploy ✅
  - **上线 URL**：https://guess-figure.pages.dev
  - Depends on: T1

### Phase 2 — 内容 pipeline + 50 人题库（~3d）

- [x] **T3 — 生产化 generate_figures.py + merge.py（从 prototype A 提升）** ✅ 2026-05-22
  - Touches: `projects/guess-figure/scripts/generate_figures.py`, `scripts/merge.py`, `scripts/requirements.txt`, `scripts/README.md`, `.gitignore`
  - Done when: 跑 `python scripts/generate_figures.py --names "诸葛亮,李白"` 输出 2 个完整 figure 到 `figures-new.json` + 跑 `python scripts/merge.py figures-new.json` 合并到 `src/lib/data/figures.json` 成功 ✅
  - 2 人 baseline 入库，质量 5/5（含 _meta 模型 / 时间 / token 用量）
  - 改进：argparse / 重试指数退避 / 增量保存 / log 文件 / finish_reason=length 检测
  - Depends on: nothing（可跟 T1 并行）

- [x] **T4 — quality_check.py + 修复 prototype A 的 false positive** ✅ 2026-05-22
  - Touches: `scripts/quality_check.py`
  - Done when: 跑 `python scripts/quality_check.py src/lib/data/figures.json` 输出每条 figure 的 5 项打分 + 修复"春秋"/"明（发明）"等 false positive ✅
  - 改进：朝代关键词从单字（"春秋"/"明"/"清"）改为精确朝代名（"明朝"/"唐朝"/"三国"等），去掉单字避免子串误匹配
  - 退出码：0 全通 / 1 文件错误 / 2 不合规 + --strict
  - Depends on: T3

- [x] **T5 — 50 人题库批量生产 + 审核 + 入库** ✅ 2026-05-22
  - Touches: `src/lib/data/figures.json`, `scripts/generate_figures.py`（加 process_one 整体 retry）
  - Done when: `jq 'length' src/lib/data/figures.json` = 50 + 50 人按 SPEC OQ2 准则覆盖朝代+类型+知名度 + `python scripts/quality_check.py --strict` 50/50 全过 ✅
  - **执行方式**：T5.1 串行 10 人（先秦+汉）；T5.2 并发 4 batch（三国+晋/唐/宋+元/明清+近代）→ Wikidata 429 + JSON 截断 28 人失败 → 串行 retry → 14/15 → 杨贵妃 fill 1 人 = 50/50
  - 关键改进：generate_figures.py 加 process_one 整体 retry（cover 429 / JSON 格式错误 / 网络间歇），max_retries=3 + sleep 5/10/15s
  - 失败 1 人：安禄山（4 retry 仍 JSON 格式错误，用杨贵妃唐代补位）
  - Depends on: T3, T4

### Phase 3 — 核心游戏组件（~3d）

- [x] **T6 — 路由 /play + 线索状态机** ✅ 2026-05-22
  - Touches: `src/routes/play/+page.svelte`, `src/lib/game-state.svelte.ts`（runes state）, `src/lib/types.ts`
  - Done when: 访问 `/play` 看到随机抽中的人物的第 1 条线索 + 点"再来一条"显示下一条 + 5 条全展示完后按钮 disabled（变成"求救"按钮）✅
  - `pnpm build` 通过 ✅；线上 https://guess-figure.pages.dev/play CF Pages auto deploy 后可访问
  - Depends on: T1, T5

- [x] **T7 — 输入框 + 中文 IME 处理** ✅ 2026-05-22
  - Touches: `src/lib/components/AnswerInput.svelte`, `src/routes/play/+page.svelte`
  - Done when: 输入框监听 `compositionstart` / `compositionend` ✅ + handleKeydown 检查 `composing` 标志才触发 submit ✅；`pnpm build` 通过 ✅
  - **范围调整**：Vitest 自动化测试推到 T15（后端 API task）一起设置 testing infra；T7 用浏览器手动 IME 测试 + Stage 8 Human QA AC14 真机验证兜底
  - Depends on: T6

- [x] **T8 — 异称表精确匹配（前端）+ 输入规范化** ✅ 2026-05-22
  - Touches: `src/lib/match-exact.ts`, `src/routes/play/+page.svelte`
  - Done when: `matchExactly()` 函数覆盖"诸葛亮"/"孔明"/"卧龙"+ normalize 去空白 / 去标点 / 全→半角；"诸葛梁"/"曹操" → false；集成 play page 显示 ✅/❌ 实时反馈 ✅
  - Vitest 自动化测试推到 T15（同 T7）
  - Depends on: T6

- [x] **T9 — 调 /api/check-answer + 集成 play page** ✅ 2026-05-22
  - Touches: `src/lib/check-answer-client.ts`, `src/routes/play/+page.svelte`
  - Done when: 异称匹配失败时调 `POST /api/check-answer` + 前端正确展示 correct/reason；checking 状态显示 + 错误降级 UI ✅
  - 合并 T13 一起做（mock 步骤跳过，直接调真后端）
  - Depends on: T8

- [x] **T10 — 计分显示 + 标准范围 5 条游戏流跑通** ✅ 2026-05-22
  - Touches: `src/lib/score.ts`, `src/lib/game-state.svelte.ts`, `src/routes/play/+page.svelte`
  - Done when: `calculateScore()` 返回 100/80/60/40/20/10/0；game.markWon() / score derived；按钮上显示"用 N 条得 X 分"实时提示 ✅
  - Vitest 单测推到 T15
  - Depends on: T9

### Phase 4 — 求救机制 + 失败 / 放弃路径（~1d）

- [x] **T11 — 求救模式 UI + 状态** ✅ 2026-05-22
  - Touches: `src/lib/game-state.svelte.ts`, `src/routes/play/+page.svelte`
  - Done when: 5 条用完显示"🆘 求救（再要 2 条最高 10 分）"+ "放弃看答案"双按钮 ✅；求救后第 6 条出 / 可再求 1 次出第 7 条 ✅；求救范围内猜中得 10 分（via calculateScore）✅
  - Depends on: T10

- [x] **T12 — 失败 / 放弃显示答案 + 维基链接** ✅ 2026-05-22
  - Touches: `src/lib/components/FailReveal.svelte`, `src/routes/play/+page.svelte`
  - Done when: 7 条用完未猜中 / 点放弃 / 猜中 三种状态都进 FailReveal 组件 ✅；显示人物名 + aliases + 维基链接（target="_blank"）+ "换一个人物再玩"按钮 ✅
  - SPEC OQ5 一句话简介推到 V2（V1 极简版用 name + aliases）
  - Depends on: T11

### Phase 5 — 后端 API（~1d）

- [x] **T13 — /api/check-answer 完整版** ✅ 2026-05-22
  - Touches: `src/routes/api/check-answer/+server.ts`
  - Done when: 调云雾 LLM + prompt 沿用 prototype B + JSON 解析容错（剥 markdown / 抠首 {} 块）+ HTTP 5xx → 502 / 超时 10s → 504（AbortSignal.timeout）/ 非 JSON → `{correct:false, reason:"无法解析"}` 兜底 ✅
  - 跟 T9 合并 commit；部署后从 https://guess-figure.pages.dev/play 直接调真后端验证
  - Depends on: T2

- [x] **T14 — /api/daily 路由（按 UTC 16:00 切换）** ✅ 2026-05-22
  - Touches: `src/routes/api/daily/+server.ts`
  - Done when: `getCurrentDailyDate()` 按 UTC 16:00 切换 ✅；dayIndex 从 LAUNCH_DATE_UTC=2026-05-22 起算 ✅；超过 50 时 `mode: "replay"` 轮播 ✅；返回 `{figure_id, date, day_index, mode}`
  - Depends on: T2, T5

- [ ] **T15 — LLM 边界用例集 30-50 个（推到 Stage 8 QA）**
  - Touches: `tests/llm-fuzz.test.ts`
  - Done when: 跑 `pnpm test tests/llm-fuzz.test.ts`（需 env LLM key）30-50 个用例至少 90% PASS
  - **范围调整**：Stage 7 Implementation 阶段不做（节省时间），推到 Stage 8 Human QA 时人工浏览器测 + 收集失败用例 → V2 加自动化 testing infra
  - Depends on: T13

### Phase 6 — daily 模式（~1d）

- [x] **T16 — /daily 页面 + localStorage 防复玩** ✅ 2026-05-22
  - Touches: `src/routes/daily/+page.svelte`
  - Done when: 访问 `/daily` → 调 `/api/daily` → 拿今日题 + 检查 localStorage ✅；已玩 → 显示"今日已完成 X 分" + 改玩日常链接 ✅；未玩 → 完整游戏 flow + finish 后写 localStorage ✅
  - 倒计时省略（V1 用文字提示"每日 0:00 换新题"代替）
  - Depends on: T12, T14

- [x] **T17 — 分享按钮 + 复制剪贴板** ✅ 2026-05-22
  - Touches: `src/lib/components/ShareButton.svelte`, `src/routes/daily/+page.svelte`
  - Done when: 点分享调 `navigator.clipboard.writeText(text)` ✅；text 格式按 SPEC 决策 7b（标准 ✅ / 求救 🆘 / 失败 ❌）✅；预览展开可见 ✅
  - Depends on: T16

- [x] **T18 — daily 题库耗尽降级 UI** ✅ 2026-05-22
  - Touches: `src/routes/daily/+page.svelte`
  - Done when: `dailyInfo.mode === "replay"` 时 subtitle 显示"📚 经典回顾"badge ✅；仍可正常玩
  - Depends on: T16

- [x] **T19 — 首页双入口** ✅ 2026-05-22
  - Touches: `src/routes/+page.svelte`
  - Done when: `/` 显示「🎮 日常游戏」+「📅 今日挑战」两个 entry card ✅；onMount 调 `/api/daily` + 检查 localStorage 显示"今日已完成 X 分"或"全球同题..." ✅
  - Depends on: T6, T16

### Phase 7 — 移动响应式 + 视觉打磨 + taste OQ（~2d）

- [x] **T20 — 移动响应式 + 真机测** ✅ 2026-05-22
  - Touches: `src/app.css`, `src/app.html`（viewport viewport-fit=cover）, `src/routes/+layout.svelte`
  - Done when: 全局 @media (max-width: 640px) 加按钮/输入框 min-height 44px (iOS HIG) + safe-area-inset 适配全屏 ✅；用户已在手机实测 ✅
  - Depends on: T19

- [x] **T21 — 视觉风格定型 + 实现（OQ8/9/10/11/12 拍板）** ✅ 2026-05-22
  - Touches: `src/app.css`（新建，CSS 变量 + 全局基础）, `src/app.html`（Noto Serif SC + theme-color）, `src/routes/+layout.svelte`（新建，import app.css）, 所有 `.svelte` 颜色硬编码 → CSS 变量
  - Done when:
    - OQ8 品牌名 = "猜历史人物"（保持默认）✅
    - OQ9 视觉 = **中国风**（米色 #f5efe6 + 朱砂红 #b91c1c + Noto Serif SC 标题字体）✅
    - OQ10 分享 emoji = ❓✅🆘❌（保持默认）✅
    - OQ11 Hero = "5 条线索，你能猜出他是谁？"（保持默认）✅
    - OQ12 移动布局 = 垂直流 + 加强移动优化（合并到 T20）✅
  - 6 个 taste OQ 全决策完毕。pnpm build 通过 ✅
  - Depends on: T20

- [x] **T22 — 自定义子域名 / pages.dev 名（OQ7 拍板）** ✅ 2026-05-22
  - Touches: 无（保持当前配置）
  - Done when: OQ7 决定 = 保持 `guess-figure.pages.dev`（已上线 URL）✅；未来上自定义域名可单开品牌化任务
  - Depends on: T2

### Phase 8 — QA + 上线缓冲（~3d）

- [x] **T23 — verification-before-completion skill 跑一遍** ✅ 2026-05-22
  - Touches: `workflow/001-guess-figure/08-qa.md` QA-readiness 摘要节
  - Done when: skill 跑出 7 个命令级证据（V1-V7：pnpm build / git log / quality_check --strict 50/50 / figures.json 127KB 50 id / 3 page HTTP 200 / /api/daily JSON / /api/check-answer POST 孔明）✅；**发现并修 1 个真 bug**（fix(T14): LAUNCH_DATE_UTC day_index=-1 → 0）✅
  - 价值兑现：找到典型"字面 AC PASS / 行为 AC FAIL"案例
  - Depends on: T22

- [x] **T24 — Stage 8 Human QA** ✅ 2026-05-22
  - Touches: 用户实测，artifact [08-qa.md](./08-qa.md) + 修 bug 3 个
  - Done when: SPEC 15 AC 全过（AI ✅ + 人工 ✅）✅；发现 3 个 issue 并修：fix(T14) day_index=-1 / fix(T9+T16) LLM reason 泄露答案 / SPEC v1.1 答错自动消耗线索
  - Depends on: T23

- [x] **T25 — 内容 spot check + 修复** ✅ 2026-05-22
  - Touches: `src/lib/data/figures.json`（Stage 8 期间 spot check）
  - Done when: 用户 Stage 8 期间 spot check 多个 figure 未发现致命错误 ✅（提前发现 2 个异称泄露：秦始皇"始皇帝" / 朱元璋"洪武"，已在 T5.1 / T5 commit 内 inline 修）
  - Depends on: T24

---

## 任务依赖图

```
T1 → T2 ─────────────────────────────────────────────────────────────
       ↓
T3 → T4 → T5 ────┐
                  ↓
T6 → T7 → T8 → T9 → T10 → T11 → T12 → T16 → T17 ──┐
                                  ↑                  ↓
                            T13 → T15               T18
                              ↑                      ↓
                            T14 ──────────────────→ T19
                                                       ↓
                                                     T20 → T21 → T22 → T23 → T24 → T25
```

并行机会：
- T1 / T3 可并行启动（独立）
- T13-T15（后端 API）可跟 T6-T12（前端组件）部分并行（前端用 mock）
- T7 / T8 可并行（输入框 + 异称表）

## 总览

- **22 个 task**，对应 8 个 Phase
- **预计工作量**：~16 工作日（不含 Svelte 5 学习）
- **commit 总数估计**：30-40 个（T5 拆 5 批 / Stage 8 fix 回路若干）
- **强制 skill 触发点**：
  - Stage 7 → 8 过渡：`verification-before-completion`（T23）
  - Stage 8：`requesting-code-review`（T24 推荐）

---

## 用户确认

- ⬜ ~~等待确认~~
- ☑ **已确认** — 确认时间：2026-05-21 ｜ 备注：22 task 全接受，进 Stage 7 Implementation

> 一旦确认，本清单成为 Stage 7 的进度追踪单位。改范围请显式回到本阶段。
