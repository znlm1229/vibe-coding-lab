# Stage 10 ｜ Retrospective 复盘

> workflow-spec v1.2 暂未把 Stage 10 列为标准阶段（personal-website 001 首创）。本任务 001-guess-figure 用户主动要求做此复盘，喂给工作流自身下一版（候选 v1.3）。
>
> **要点**：诚实记录赢点 + 摩擦点 + 意外发现 + 给下任务的提醒。复盘的产出比"任务完成"本身更长尾。

---

## 复盘对象

任务 **001-guess-figure**（2026-05-22 完成）。详细见同目录 [01–09 artifact](.)。

| 指标 | 数值 |
|---|---|
| 开始日期 | 2026-05-21（项目从 `002` 占位改名为 `guess-figure`，开 Stage 1）|
| 结束日期 | 2026-05-22（用户验收 + CLOSED）|
| 跨度 | ~2 天（含 Stage 1-10 全流程）|
| Commit 总数 | 33+ 个 |
| 总 task | 22 个全完成（T15 LLM 用例集与 Stage 8 Human QA 合并完成）|
| AC 通过率 | 15 / 15 |
| 上线 URL | [guess-figure.pages.dev](https://guess-figure.pages.dev) |

## 1. 工作流验证的 7 个赢点

> v1.2 是 personal-website 001 复盘后的产物（增 4 个 stage-skill 绑定、AC 双通道、commit `fix(TX):` 等）。guess-figure 直接基于 v1.2 跑通，验证 v1.2 可复制性。

| # | 赢点 | 关键证据 |
|---|---|---|
| 1 | **v1.2 verification-before-completion skill 救场** | T23 跑 skill 直接抓 `/api/daily day_index=-1` 真 bug（[fix(T14) dec325c]）。如果没这个强制 skill，bug 会以"build 通过 + 部署成功"假象进 Stage 8 才被发现，或更糟到上线 24h 后被用户报告 |
| 2 | **v1.2 全部 4 个 stage-skill 触发并产价值** | brainstorming (Stage 1 发散 5 方向)→ grill-me (Stage 2 拷问 10 轮)→ writing-plans (Stage 5 出 8 phase + 10 风险)→ verification-before-completion (Stage 7→8 抓 bug)→ requesting-code-review (Stage 8 推荐使用，本次用户主导) |
| 3 | **v1.2 AC 双通道兑现** | SPEC 15 条 AC 全部按"AI 验证 / 人工验证两栏"设计。Stage 9 核对表逐条对照，避免了 personal-website 001 那次 EmailLink 类型 "字面通过 / 行为破洞" |
| 4 | **v1.2 commit prefix 全 6 个前缀用上** | `task-TX:` 23 个 / `fix(TX):` 3 个 / `stage-N:` 5 个 / `chore:` 2 个 / `docs:` 1 个 / `task-` 复合（如 T9+T13、T10+T11+T12）—— git history 可清晰回溯每一步性质 |
| 5 | **Prototype A benchmark 模式直接救场** | benchmark_models.py 一次并行测 6 模型，发现 deepseek-v4-flash 60% 失败率 + 切到 gemini-3.1-flash-lite。**如果没做这次 benchmark，V1 会锁定 reasoning model 才发现慢/不稳，回退成本巨大** |
| 6 | **内容 pipeline 增量小批 + 自动质量校验** | T5 50 人分 5 批 × 10 人跑（实际并发踩 Wikidata 429 后又退回串行 retry），每批 quality_check 校验。**单次失败不影响整体** + 自动检测异称泄露 / 朝代名暴露 false positive |
| 7 | **auto mode + 用户战略干预协同高效** | 长 session（Stage 1→10 一次跑完）+ 关键节点用户给方向（如"并发跑 batch"、"我自己测 / 你接力实现"）。auto mode 不取代人工关卡（SPEC / Tasks / QA / Acceptance 4 个都停下确认）|

## 2. 5 个明显的摩擦点

| # | 摩擦 | 现象 | 改进方向 |
|---|---|---|---|
| 1 | **LLM 选型反复试错** | DeepSeek V3 (Stage 2 grill-me 锚) → deepseek-v4-pro (云雾实际) → deepseek-v4-flash (尝试快版) → benchmark 6 模型 → gemini-3.1-flash-lite (正解)。**4 次切换** 折腾 ~1h | v1.3 加 best practice："LLM 模型选型必走 benchmark + multi-model 横向对比，不靠假设" |
| 2 | **Wikidata 429 rate limit（4 batch 并发触发）** | T5 用户提"并发省时" → 4 batch 同时跑 → Wikidata 429 → 28 人失败需 retry | v1.3 加失败模式："外部 API 并发的隐性 rate limit / 共享资源争抢"；并发前必须确认外部依赖能扛 |
| 3 | **LLM reasoning model 在 strict JSON 任务上不可用** | deepseek-v4-* 系列反复 content 空（reasoning 占满 max_tokens 后没切到 output）。8000 max_tokens 也不够 | v1.3 加失败模式："reasoning model 不适合需要严格结构化输出的任务"（独立列出，跟 v1.2"字面 AC vs 行为 AC"并列）|
| 4 | **LLM `reason` 字段在前端泄露答案** | Stage 8 用户截图：玩家输错 → "诸葛亮与朱熹并非同一人物" → **暴露答案"朱熹"**。LLM 默认 helpful 解释 vs 游戏对抗场景的信息泄露面冲突 | v1.3 加失败模式："AI 默认 helpful 行为 vs 游戏 / 对抗场景的信息泄露"（适用任何"用户不应知道真相"的场景）|
| 5 | **日期 / 时区锚定常量隐蔽 bug** | `LAUNCH_DATE_UTC = "2026-05-22"`（上线次日）+ 当前 UTC<16 时 dailyDate 回退 → `day_index: -1`。AC11 / 14 是双通道，AI 通道仍 PASS（HTTP 200 + JSON 返回）但行为破洞 | v1.3 best practice："涉及日期 / 时区的代码 SPEC AC 要把'边界情况下的具体数值'写明，不只是'切换正确'" |

## 3. 1 个意外发现

**LLM `reason` 字段是游戏类应用的信息泄露面**。

这跟 personal-website 001 复盘里的"AC 字面通过 / 行为破洞"是同源 — 都是"AI 默认行为在某些场景下反而是漏洞"。但 personal-website 是**漏判**（AC 写得太字面），guess-figure 是**多判**（LLM 主动多说出原本不该说的）。

强化的原则：**任何输出给玩家 / 对抗方的 AI 响应，必须审计"它说了什么 ≠ 它应该说什么"**。游戏 / 教育 / 推理类应用尤其。

实际处理：
- `lastResult.reason` 保留在 state 里（便于 debug）
- 不渲染到 UI（不暴露给玩家）
- 错误降级用通用文案（"提交失败，请稍后再试"）替代具体错误细节

## 4. SPEC patch / fix 的成本核算

| 触发 | 阶段 | 工作量 | 性质 | commit |
|---|---|---|---|---|
| LAUNCH_DATE_UTC 早 1 天 | T23 verification skill 期间 | 1 行改 + 1 commit | 行为层 bug，AI 漏判 AC11 | dec325c |
| LLM reason 泄露答案 | Stage 8 用户截图反馈 | 2 处 .svelte 改 + 1 commit | 行为层 bug，SPEC 没规定 reason 渲染策略（隐性假设） | f3002ee |
| 答错应消耗一条线索 | Stage 8 用户 UX 反馈 | 3 处代码 + SPEC v1.0→v1.1 + 1 commit | **行为层 SPEC 修订**，触发用户重新确认 | c263c88 |
| 秦始皇 / 朱元璋 异称泄露 | T5 quality_check 期间 | 2 处 figures.json inline 改 | 内容层 bug，inline 修不单独 commit | (inline in T5 / T5.1)|

**结论**：v1.2 commit 前缀规范让"fix vs feat vs spec 修订"区分清晰。Stage 8 三个回路全用 `fix(TX):` / `task-TX:`（SPEC 修订），git history 看出"哪些是首次实现 / 哪些是修复回路 / 哪些是 SPEC 演化"。

## 5. 给 workflow-spec v1.3 的反馈（建议）

### 新增失败模式（§6 候选）

1. **"AI 默认 helpful 行为 vs 游戏 / 对抗场景的信息泄露面"** — 适用于 LLM reason / debug 信息 / 错误细节等 AI 默认友好但不应展示给玩家的字段。引用本任务的 LLM reason 泄露案例
2. **"Reasoning model 在严格结构化输出任务上不稳定"** — token 预算被 reasoning 阶段耗尽 / content 空；候选解药：prototype 阶段必做 multi-model benchmark
3. **"外部 API 并发的隐性 rate limit / 共享资源争抢"** — 单线程跑没问题，并发跑触发限速；典型例如 Wikidata 429。引用本任务的 T5 并发批量生产案例

### 新增 best practice（§5 候选）

1. **"LLM 选型必走 multi-model benchmark"** — 参考 prototype A benchmark_models.py 模式：6 模型并行跑同一测试 + 4 维数据（时间/token/成本/质量）+ 输出对比文笔
2. **"内容生产 pipeline 增量小批 + 自动质量校验 + retry"** — 不要一次性产 50 全失败；每批跑 + 校验 + 入库
3. **"日期 / 时区锚定常量 SPEC AC 写到具体数值"** — 不只是"按 UTC 切换"，要写"上线当天调 API 应返回 day_index=0"等具体期望

### 验证 v1.2 落地（无需修改 spec）

- ✅ 4 个 stage-skill 全部触发并产生独立价值
- ✅ AC 双通道在 15 条 AC 全部兑现
- ✅ 6 个 commit prefix 全用上
- ✅ auto mode + 人工关卡 4 处停下确认（SPEC v1.0 / Tasks / Human QA / Acceptance）

## 6. 给下任务的 6 条提醒

| # | 提醒 | 来源 |
|---|---|---|
| 1 | LLM 选型不靠假设，必做 benchmark（参考 prototype/A-content/benchmark_models.py）| 摩擦 #1 |
| 2 | 外部 API 并发前先 ping 一下文档看 rate limit；不行就串行 + retry | 摩擦 #2 |
| 3 | 避免 reasoning model 做严格结构化输出（必须时大幅加 max_tokens 且接受不稳定）| 摩擦 #3 |
| 4 | Stage 8 期间专门测一次"用户故意做错"场景，看 AI 输出是否泄露答案 / 不当信息 | 摩擦 #4 + 意外发现 |
| 5 | 日期 / 时区锚定常量 SPEC AC 写具体期望数值（如"上线当天 day_index 应为 0"）| 摩擦 #5 |
| 6 | LLM `reason` / debug 字段保留在 state 但不渲染，错误降级用通用文案 | 意外发现 |

## 7. 整体感受

跟 personal-website 001 比，guess-figure 是个**更复杂的项目**（含游戏交互 / 状态机 / 50 人题库 / 内容 pipeline / LLM 调用 / daily 时间机制 / 移动响应式），但**总跨度从 personal-website 001 的 ~3 天压缩到 ~2 天**。

提速来自：
- **v1.2 stage-skill 自动触发**减少"AI 应该用哪个 skill"的决策成本
- **prototype 阶段的 benchmark** 让选型 1h 内定（vs 锁错后回退几天）
- **auto mode + 战略干预**：用户长 session 一次推完，关键节点（人工关卡 + taste OQ）介入
- **第二次跑工作流**的肌肉记忆（不必再读 spec 思考"下一步该干啥"）

副作用：
- 单 session 持续 ~10h 实际工时，token 消耗大
- 用户参与的"关卡点"较密集（每个 ★ 都要回应），节奏比"完全 hands-off"紧

下次任务（002 / 003 / 004）建议：
- 继续 v1.2 + 可能 v1.3
- 单 session 长度控制 ≤ 6h
- 内容密集型 task（如 002 加账号 + DB schema）单独留个 session
