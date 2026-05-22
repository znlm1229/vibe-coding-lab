---
title: "guess-figure — 猜历史人物"
summary: "用九步 AI 原生开发工作流 2 天端到端做出的公开上线 Web 游戏。50 个中国历史人物 × 7 条线索，玩家自由输入答案，LLM 判定异称匹配。"
tech: ["SvelteKit 5", "Svelte 5 Runes", "TypeScript", "Cloudflare Pages", "Cloudflare Functions", "gemini-3.1-flash-lite", "Python", "Markdown"]
githubUrl: "https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure"
status: "active"
pubDate: 2026-05-22
featured: true
order: 2
---

## 项目背景

[guess-figure](https://guess-figure.pages.dev) 是 vibe-coding-lab 的第二个端到端实战项目。延续 personal-website 验证的九步工作流，这次目标更复杂 —— **公开上线的 Web 游戏**（含游戏交互 / 状态机 / 50 人题库 / 内容生产 pipeline / LLM 调用 / daily 时间机制 / 移动响应式），看 v1.2 工作流是否在更高复杂度上仍能成立。

**总跨度：2 天**（vs personal-website 的 3 天 — 第二次跑工作流明显提速）。

## 玩法

- **日常游戏**：从 50 个中国历史人物随机抽题
- **今日挑战**：全球同题 / 每日 1 次 / 可分享得分
- 系统按难度从难到易给出 5 条标准线索 + 可选 2 条求救线索
- 玩家自由输入答案 → 异称表精确匹配（"诸葛亮"="孔明"="卧龙"）→ 失败 fallback 到 LLM 模糊匹配
- 计分：标准猜中 100/80/60/40/20，求救猜中 10，放弃 0
- 答错自动消耗一条线索（Stage 8 SPEC v1.1 修订）

## 关键架构

- **前端密集 + 轻后端**：所有游戏逻辑跑在前端（状态机 / 计分 / localStorage），后端 CF Pages Functions 只做 2 件事 — LLM 模糊匹配代理 + daily 路由
- **题库即代码**：50 人物 × 7 线索 JSON-in-git（`src/lib/data/figures.json`），跟代码一起部署 / 增量加题 = git push
- **LLM 极简调用**：95% 玩家命中异称表无需 LLM；仅 5% 走 fallback（月成本 < $5）
- **内容生产 pipeline**：Python 脚本 — 维基中文 + Wikidata + 百度补盲 → LLM 加工 7 条线索 + 难度 + 异称 → 人工审核 → 入库

## Stage 3 prototype 的多模型 benchmark 救场

V1 内容生产模型选型走了一段弯路：grill-me 阶段锚定 DeepSeek V3，但云雾上没有这个模型，实际可用是 `deepseek-v4-pro` / `deepseek-v4-flash` —— 两者都是 reasoning model，在严格 JSON 输出任务上 60% 失败率。

如果硬上 V1，会发现"上线慢 + 不稳"才回头改。但 Stage 3 prototype 阶段写了一个 `benchmark_models.py`，一次并行测 6 个模型 + 4 维数据（时间 / token / 成本 / 质量），10 分钟内挑出 **gemini-3.1-flash-lite**（4 秒 / 5/5 质量 / $0.00141）。模型选型从"假设 + 上线后才知道"变成"实测 + 决策前定"。

## Stage 8 Human QA 抓到的 3 个隐蔽 bug

工作流 v1.2 加的 `verification-before-completion` skill 在 Stage 7→8 强制跑命令验证，直接抓到：

1. **`/api/daily` 返回 `day_index: -1`** — LAUNCH_DATE_UTC 写错 1 天，AI 通道（HTTP 200 + JSON 返回）看不出来，typical "字面 AC PASS / 行为 AC FAIL"
2. **LLM `reason` 字段在前端泄露答案** — 玩家输"诸葛亮"猜错时 LLM 友好地回复"诸葛亮与朱熹并非同一人物" → **暴露答案"朱熹"**。AI 默认 helpful 行为 vs 游戏对抗场景的信息泄露面冲突
3. **SPEC v1.0 → v1.1 行为修订** — 用户 Stage 8 提"答错应自动消耗一条线索"，减少试探薅羊毛，触发 SPEC 修订并实测通过

## 完整 artifact

从 brainstorm 到上线的全部 9+1 阶段 artifact（含 Stage 10 复盘）在 [仓库的 workflow 目录](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure/workflow/001-guess-figure)。

第二次跑九步工作流的复盘见 [博客](/posts/guess-figure-retrospective/)。
