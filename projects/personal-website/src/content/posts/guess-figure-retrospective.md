---
title: "2 天做出公开上线的猜历史人物游戏 — 第二次跑九步工作流的复盘"
description: "用 vibe-coding-lab 九步 AI 原生开发工作流 v1.2 端到端做出 guess-figure（猜历史人物 Web 游戏）。第二次跑工作流明显提速，但也暴露了 5 个新的失败模式 —— 给下一版 workflow-spec 的反馈。"
pubDatetime: 2026-05-22T20:00:00+08:00
author: "李旺"
tags: ["vibe-coding", "workflow", "retrospective", "sveltekit", "llm", "cloudflare"]
featured: true
---

[guess-figure](https://guess-figure.pages.dev) 上线了 —— 公开可玩的中国历史人物猜谜游戏。从 002 占位目录创建到 ACCEPTED CLOSED **只用了 2 天**（vs 第一次做这个网站时的 3 天）。本文记录第二次跑九步 AI 原生开发工作流的赢点、摩擦点、意外发现，以及给下一版工作流的反馈。

> 如果你不知道九步工作流是什么，先看 [Hello — 用九步工作流搭这个网站](/posts/hello-and-the-nine-stages/)。

## 这次做的项目

**guess-figure** — 50 个中国历史人物 × 7 条线索，玩家根据线索猜人物。两种模式：

- **日常游戏**：随机抽题无限玩
- **今日挑战**：全球同题、每日 1 次、可分享得分

技术栈：SvelteKit 5 + Svelte 5 Runes + Cloudflare Pages + CF Functions + gemini-3.1-flash-lite via 云雾中转 + JSON-in-git 题库 + Python 内容生产脚本。

完整 [项目集 entry](/projects/guess-figure/) | [上线 URL](https://guess-figure.pages.dev) | [源码](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure)

## 工作流验证的 7 个赢点

第一次跑（personal-website）后我们把 workflow-spec 从 v1.1 升到 v1.2，加了 4 个 stage-skill 绑定、AC 双通道、commit `fix(TX):` 前缀等。这次 guess-figure 直接基于 v1.2 跑通，**验证 v1.2 可复制**。

| # | 赢点 | 关键证据 |
|---|---|---|
| 1 | **verification-before-completion skill 救场** | Stage 7→8 过渡时跑 skill 直接抓到 `/api/daily` 返回 `day_index: -1` 的 bug。如果没这个强制 skill，bug 会以"build 通过 + 部署成功"假象进 Stage 8 才被发现，或更糟到上线 24h 后被用户报告 |
| 2 | **4 个 stage-skill 全部触发并产价值** | brainstorming 发散 5 方向 → grill-me 拷问 10 轮 → writing-plans 出 8 phase + 10 风险 → verification 抓 bug → requesting-code-review 推荐用 |
| 3 | **AC 双通道兑现** | SPEC 15 条 AC 全部按"AI 验证 / 人工验证两栏"设计。Stage 9 核对表逐条对照，避免了 personal-website 那次 EmailLink 类型的"字面通过 / 行为破洞" |
| 4 | **commit prefix 6 个全用上** | `task-TX:` 23 个 / `fix(TX):` 3 个 / `stage-N:` 5 个 / `chore:` 2 个 / `docs:` 1 个 / `task-` 复合（如 T9+T13、T10+T11+T12）—— git history 可清晰回溯每一步性质 |
| 5 | **Prototype 阶段的 multi-model benchmark 救场** | 写了个 `benchmark_models.py` 一次并行测 6 个 LLM，10 分钟内挑出 gemini-3.1-flash-lite。**如果没做这次 benchmark，V1 会锁定 reasoning model 才发现慢/不稳，回退成本巨大** |
| 6 | **内容 pipeline 增量小批 + 自动质量校验** | 50 人分 5 批 × 10 人跑，每批 quality_check 校验。单次失败不影响整体 + 自动检测异称泄露 / 朝代名暴露 |
| 7 | **auto mode + 用户战略干预协同高效** | 长 session 一次推完 + 关键节点用户给方向（如"并发跑 batch"）。auto mode 不取代人工关卡 — SPEC / Tasks / QA / Acceptance 4 个都停下确认 |

## 5 个明显的摩擦点

> 给 workflow-spec v1.3 的候选输入。

### 1. LLM 选型反复试错

Grill-me 阶段锚定 DeepSeek V3，但云雾平台上没有 — 实际是 `deepseek-v4-pro` / `deepseek-v4-flash` —— 两者都是 reasoning model，在严格 JSON 输出任务上 60% 失败率（token 预算被 reasoning 吃掉，content 空）。

**4 次切换** 折腾约 1 小时。后来 Prototype A 写了 benchmark_models.py 才一锤定音 gemini-3.1-flash-lite。

> 给 v1.3 的 best practice：**"LLM 模型选型必走 multi-model benchmark，不靠假设"**。

### 2. 外部 API 并发的隐性 rate limit

T5 内容生产 50 人时用户提"并发省时" → 4 个 batch 同时跑 → Wikidata 触发 429 Too Many Requests → 28 人失败需 retry。

> 给 v1.3 的失败模式：**"外部 API 并发的隐性 rate limit / 共享资源争抢"**。并发前必须确认外部依赖能扛。

### 3. Reasoning model 在严格结构化输出任务上不稳定

DeepSeek-v4 系列反复 `content` 字段为空（reasoning 阶段占满 max_tokens 后没切到 output）。8000 max_tokens 也不够。

> 给 v1.3 的失败模式：**"Reasoning model 不适合需要严格 JSON 输出的任务"**。独立列出，跟 v1.2 的"字面 AC vs 行为 AC"并列。

### 4. LLM `reason` 字段在前端泄露答案 ⚠️

**最有意思的一个 bug。**

Stage 8 用户实测时截图：玩家输错"诸葛亮"猜测当前题，UI 显示「❌ 不算「诸葛亮」— 诸葛亮与朱熹并非同一人物」—— LLM 默认友好解释，但**直接暴露答案"朱熹"**。

LLM 默认 helpful 行为 vs 游戏对抗场景的信息泄露面冲突。这跟 personal-website 001 复盘里的"AC 字面通过 / 行为破洞"是同源 —— 都是"AI 默认行为在某些场景下反而是漏洞"。但 personal-website 是**漏判**（AC 写得太字面），guess-figure 是**多判**（LLM 主动多说出原本不该说的）。

> 给 v1.3 的失败模式：**"AI 默认 helpful 行为 vs 游戏 / 对抗场景的信息泄露面"**。适用于任何"用户不应知道真相"的场景（游戏 / 教育 / 推理类）。

修复：`lastResult.reason` 保留在 state（便于 debug）+ 不渲染到 UI + 错误降级用通用文案。

### 5. 日期 / 时区锚定常量隐蔽 bug

`LAUNCH_DATE_UTC = "2026-05-22"`（上线次日）+ 当前 UTC<16:00 时 dailyDate 回退到上线日前 → `day_index: -1`。AC 仍按双通道写但 AI 通道误判（HTTP 200 + JSON 返回都过），行为破洞。

修复：`LAUNCH_DATE_UTC = "2026-05-21"`（上线当日）+ verification skill 也跑过一遍。

> 给 v1.3 的 best practice：**"涉及日期 / 时区的代码 SPEC AC 要把'边界情况下的具体数值'写明"**，不只是"切换正确"。

## 1 个意外发现

**LLM `reason` 字段是游戏类应用的信息泄露面**。

修完后我反思这跟 personal-website 那次 EmailLink 是镜像问题：

- personal-website：AC 字面通过（"HTML 不含明文邮箱" ✓），但 UI 完全坏（脚本没加载）—— **AI 漏判**
- guess-figure：AC 字面通过（"判定返回正确" ✓），但 reason 文字泄露 —— **AI 多判**

强化的原则：**任何输出给玩家/对抗方的 AI 响应，必须审计"它说了什么 ≠ 它应该说什么"**。

## SPEC v1.0 → v1.1 — Stage 8 期间的行为修订

Stage 8 用户提："答错应自动消耗一条线索，让玩家试探有代价"。这是 SPEC 行为层变更（不是简单 bug 修），按 v1.2 规范触发 SPEC 修订 + 重新确认。

- 改 04-spec.md Behavior Flow 1："错→不消耗" 改 "错→自动展示下一条"
- 加 v1.1 修订日志
- 3 处代码改（game-state.svelte.ts 加 consumeOnWrongAnswer + play page + daily page）
- AC 15 条不变（calculateScore 公式不变，只是触发时机变化）

完整链路可见仓库的 [04-spec.md 修订日志](https://github.com/znlm1229/vibe-coding-lab/blob/main/projects/guess-figure/workflow/001-guess-figure/04-spec.md#修订日志)。

## 整体感受

guess-figure 是个**比 personal-website 更复杂的项目**（含游戏交互 / 状态机 / 50 人题库 / 内容 pipeline / LLM 调用 / daily 时间机制 / 移动响应式），但**总跨度从 3 天压缩到 2 天**。

提速来自：
- **v1.2 stage-skill 自动触发** 减少"AI 应该用哪个 skill"的决策成本
- **prototype 阶段的 benchmark** 让选型 1 小时内定（vs 锁错后回退几天）
- **auto mode + 战略干预**：用户长 session 一次推完，关键节点（人工关卡 + taste OQ）介入
- **第二次跑工作流的肌肉记忆**：不必再读 spec 思考"下一步该干啥"

代价：单 session 持续约 10 小时实际工时，token 消耗大；用户参与的"关卡点"较密集（每个 ★ 都要回应）。

## 给下一个项目的提醒

1. LLM 选型不靠假设，必做 benchmark
2. 外部 API 并发前先 ping 一下文档看 rate limit；不行就串行 + retry
3. 避免 reasoning model 做严格结构化输出
4. Stage 8 期间专门测一次"用户故意做错"场景，看 AI 输出是否泄露答案
5. 日期 / 时区锚定常量 SPEC AC 写具体期望数值
6. LLM `reason` / debug 字段保留在 state 但不渲染，错误降级用通用文案

---

去玩玩 → [guess-figure.pages.dev](https://guess-figure.pages.dev)

完整 9+1 阶段 artifact 在 [仓库](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure/workflow/001-guess-figure)（含 stage-10 内部复盘，是本博客的素材源）。
