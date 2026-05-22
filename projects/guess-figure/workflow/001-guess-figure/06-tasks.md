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

- [ ] **T2 — CF Pages production project 创建 + 第一次 deploy**
  - Touches: CF Pages dashboard（创建 project `guess-figure` 或 `guess-figure-proto-prod`）+ env vars 配置 + Root directory = `projects/guess-figure`
  - Done when: `git push` 触发 CF Pages auto deploy，部署成功 + 访问生产 URL 看到占位首页 + 后续 push 能正确触发新 deploy
  - Depends on: T1

### Phase 2 — 内容 pipeline + 50 人题库（~3d）

- [ ] **T3 — 生产化 generate_figures.py + merge.py（从 prototype A 提升）**
  - Touches: `projects/guess-figure/scripts/generate_figures.py`, `scripts/merge.py`, `scripts/requirements.txt`, `.env.example`
  - Done when: 跑 `python scripts/generate_figures.py --names "诸葛亮,李白"` 输出 2 个完整 figure 到 `figures-new.json` + 跑 `python scripts/merge.py figures-new.json` 合并到 `src/lib/data/figures.json` 成功
  - Depends on: nothing（可跟 T1 并行）

- [ ] **T4 — quality_check.py + 修复 prototype A 的 false positive**
  - Touches: `scripts/quality_check.py`
  - Done when: 跑 `python scripts/quality_check.py src/lib/data/figures.json` 输出每条 figure 的 5 项打分 + 修复"春秋"/"明（发明）"等 false positive（朝代检测按词边界，标志事件加 per-figure 黑名单）+ 至少 90% 测试用例打分准确
  - Depends on: T3

- [ ] **T5 — 50 人题库批量生产 + 审核 + 入库（5 批 × 10 人）**
  - Touches: `src/lib/data/figures.json`
  - Done when: `jq 'length' src/lib/data/figures.json` ≥ 50 + 50 人按 SPEC OQ2 准则覆盖朝代+类型+知名度 + `python scripts/quality_check.py` 全部通过
  - Depends on: T3, T4
  - 子里程碑：每批 10 人单独 commit `task-T5.N: 题库 +10 人物（朝代 X）`

### Phase 3 — 核心游戏组件（~3d）

- [ ] **T6 — 路由 /play + 线索状态机**
  - Touches: `src/routes/play/+page.svelte`, `src/lib/game-state.svelte.ts`（runes state）
  - Done when: 访问 `/play` 看到随机抽中的人物的第 1 条线索 + 点"再来一条"显示下一条 + 5 条全展示完后按钮 disabled
  - Depends on: T1, T5（最少 1 人题库测试，5 人 fixture 更好）

- [ ] **T7 — 输入框 + 中文 IME 处理**
  - Touches: `src/lib/components/AnswerInput.svelte`, `src/routes/play/+page.svelte`
  - Done when: 输入框监听 `compositionstart` / `compositionend` + 测试用例覆盖 IME 未结束时按 Enter 不触发提交（Vitest 单元测试 PASS）
  - Depends on: T6

- [ ] **T8 — 异称表精确匹配（前端）+ 输入规范化**
  - Touches: `src/lib/match-exact.ts`, `src/lib/components/AnswerInput.svelte`
  - Done when: 单元测试覆盖"诸葛亮"/"孔明"/"卧龙"/"  孔明  "/"孔 明"/"孔明（誤入空格）"全 PASS；"诸葛梁"/"曹操"全 FAIL
  - Depends on: T6

- [ ] **T9 — 调 /api/check-answer + mock fallback**
  - Touches: `src/lib/check-answer-client.ts`, `src/routes/play/+page.svelte`
  - Done when: 异称匹配失败时调 `POST /api/check-answer`（mock：fetch 返回固定 JSON）+ 前端正确展示 correct/reason；真后端 T13 完成后切到真调用
  - Depends on: T8

- [ ] **T10 — 计分显示 + 标准范围 5 条游戏流跑通**
  - Touches: `src/lib/score.ts`, `src/routes/play/+page.svelte`
  - Done when: 单元测试 `score(usedClues, isRescue)` 返回 100/80/60/40/20/10/0；浏览器实测 1 条线索猜中显示 100、2 条 80、...、5 条 20
  - Depends on: T9

### Phase 4 — 求救机制 + 失败 / 放弃路径（~1d）

- [ ] **T11 — 求救模式 UI + 状态**
  - Touches: `src/lib/game-state.svelte.ts`, `src/routes/play/+page.svelte`
  - Done when: 5 条标准用完未猜中显示"再要 2 条线索（求救）" + "放弃看答案"双按钮 + 点求救显示线索 6 + 可再点显示线索 7 + 求救范围内猜中得 10 分
  - Depends on: T10

- [ ] **T12 — 失败 / 放弃显示答案 + 维基链接**
  - Touches: `src/lib/components/FailReveal.svelte`, `src/routes/play/+page.svelte`
  - Done when: 7 条全用完未猜中或点"放弃" → 显示人物名 + Wikidata description 一句话 + 维基链接（点击新 tab 打开维基中文）+ "再玩一局"按钮可重置游戏
  - Depends on: T11

### Phase 5 — 后端 API（~1d）

- [ ] **T13 — /api/check-answer 完整版**
  - Touches: `src/routes/api/check-answer/+server.ts`
  - Done when: 调云雾 LLM（gemini-3.1-flash-lite）+ prompt 沿用 prototype B 草案 + JSON 解析容错 + HTTP 5xx → 502 / 超时 10s → 504 / 非 JSON → 兜底返回 `{correct:false}` + 部署后从前端调用真实生效
  - Depends on: T2（生产环境 env vars 已配）

- [ ] **T14 — /api/daily 路由（按 UTC 16:00 切换）**
  - Touches: `src/routes/api/daily/+server.ts`
  - Done when: 多次调 `GET /api/daily` 在 UTC 16:00 前同一天内返回相同 `{figure_id, date}` + 跨过 UTC 16:00 返回不同 figure_id；超过题库长度时进入"经典回顾"轮播（返回 `{figure_id, date, mode: "replay"}`）
  - Depends on: T2, T5

- [ ] **T15 — LLM 边界用例集 30-50 个**
  - Touches: `tests/llm-fuzz.test.ts`
  - Done when: 跑 `pnpm test tests/llm-fuzz.test.ts`（需 env LLM key）30-50 个用例至少 90% PASS；含「孔明 ✅」「卧龙 ✅」「诸葛丞相 ✅」「诸葛梁 ❌」「曹操 ❌」「诸葛 ❌」「亮 ❌」「孔  明（双空格）✅」「繁简：諸葛亮 ✅」等
  - Depends on: T13

### Phase 6 — daily 模式（~1d）

- [ ] **T16 — /daily 页面 + localStorage 防复玩**
  - Touches: `src/routes/daily/+page.svelte`, `src/lib/daily-state.svelte.ts`
  - Done when: 访问 `/daily` 调 `/api/daily` 拿今日题 + 复用 T6-T12 游戏组件 + 玩完写 localStorage key `daily_played_YYYYMMDD` + 已玩过显示"今日已完成：X 分" + 倒计时下次换题
  - Depends on: T12, T14

- [ ] **T17 — 分享按钮 + 复制剪贴板**
  - Touches: `src/lib/components/ShareButton.svelte`, `src/routes/daily/+page.svelte`
  - Done when: 点分享按钮调 `navigator.clipboard.writeText(text)` + text 格式 `猜历史人物 #N\n❓❓❓✅ 用了 3 条线索\nhttps://<domain>`（标准 ✅ / 求救 🆘 / 失败 ❌）+ 浏览器粘贴到记事本验证格式正确
  - Depends on: T16

- [ ] **T18 — daily 题库耗尽降级 UI**
  - Touches: `src/routes/daily/+page.svelte`
  - Done when: 当 `/api/daily` 返回 `mode: "replay"` 时前端显示"今日：经典回顾 第 N 期"提示 + 仍可正常玩
  - Depends on: T16

- [ ] **T19 — 首页双入口**
  - Touches: `src/routes/+page.svelte`
  - Done when: `/` 显示"日常游戏"+"今日挑战"两个按钮 + daily 入口显示"今日已玩"/"今日未玩"状态（依据 localStorage）
  - Depends on: T6, T16

### Phase 7 — 移动响应式 + 视觉打磨 + taste OQ（~2d）

- [ ] **T20 — 移动响应式 + 真机测**
  - Touches: 所有 `*.svelte` 文件的 `<style>` 块、global CSS
  - Done when: Chrome DevTools 模拟 iPhone 12 + Galaxy S20 布局不爆 + 真机 iOS Safari 输入"孔明"按确认提交无丢字 + 真机 Android Chrome 同
  - Depends on: T19

- [ ] **T21 — 视觉风格定型 + 实现（OQ8/9/10/11/12 拍板）**
  - Touches: 全局 CSS、`src/routes/+page.svelte`、`app.html`
  - Done when: 用户拍板品牌名（OQ8）+ 主色风格（OQ9）+ 首页 Hero 文案（OQ11）+ 分享 emoji 格式（OQ10）+ 移动布局风格（OQ12）+ UI 落地这些决定
  - Depends on: T20

- [ ] **T22 — 自定义子域名 / pages.dev 名（OQ7 拍板）**
  - Touches: CF Pages dashboard 配置
  - Done when: 用户拍板域名（如 `guess-figure.pages.dev` 或 `lw-figure.pages.dev`）+ CF Pages 重命名 project 或配自定义域名 + 新 URL 生效
  - Depends on: T2

### Phase 8 — QA + 上线缓冲（~3d）

- [ ] **T23 — verification-before-completion skill 跑一遍**
  - Touches: 所有已完成的 task，跑 skill 校验每个 task 的 done-when 有验证证据
  - Done when: skill 输出 22 个 task 中所有 done-when 都有跑命令/截图/log 作为证据 + 标 PASS 的不存在"字面通过行为破洞"
  - Depends on: T22（所有功能 task 完成）

- [ ] **T24 — Stage 8 Human QA（移动真机 + LLM 边界用例真测 + 15 AC 双通道）**
  - Touches: 用户实测，artifact 在 [08-qa.md](./08-qa.md)
  - Done when: SPEC 15 条 AC 全部 PASS（AI 通道 + 人工通道两边都 PASS）+ 发现的 bug 全部进 `fix(TX):` commit 修复
  - Depends on: T23

- [ ] **T25 — 内容 spot check + 修复**
  - Touches: `src/lib/data/figures.json`（如需修）
  - Done when: 随机抽 10 人 review 事实准确性 + 难度梯度 + 异称完整度 + 错误用 `fix(T5.N):` commit 修复
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
