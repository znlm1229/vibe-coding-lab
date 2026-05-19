---
title: "vibe-coding-lab"
summary: "用九步 AI 原生开发工作流跑通的个人项目仓库。你正在浏览的这个网站就是它的第一个端到端实战产物。"
tech: ["Astro", "Tailwind CSS", "TypeScript", "Cloudflare Pages", "Markdown"]
githubUrl: "https://github.com/znlm1229/vibe-coding-lab"
status: "active"
pubDate: 2026-05-19
featured: true
order: 1
---

## 项目背景

[vibe-coding-lab](https://github.com/znlm1229/vibe-coding-lab) 是我用来沉淀 vibe coding 学习经验、踩坑笔记和实战项目的公开仓库。第一个端到端项目就是你现在看到的这个网站。

## 用九步工作流做了什么

**九步流程**：Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★（★ = 人工关卡，AI 不得绕过用户确认推进）

每个阶段都有可见的 markdown artifact 沉淀在仓库里，可追溯：

- **Stage 1 Brainstorm** — 列 5 个个人网站方向（A 极简 / B 博客 / C 作品集 / D 综合 / E SaaS 寄生），不评胜者
- **Stage 2 Grill Me** — 调 `grill-me` skill 跑 10 轮拷问，覆盖动机、受众、时间线、内容、栈、托管、设计、维护、非目标等决策分支
- **Stage 3 Prototype** — 跳过（无遗留不确定性）
- **Stage 4 SPEC ★** — 13 条可测试 AC（含 AC10 邮箱不明文等）
- **Stage 5 Plan** — 9 phase 实施计划
- **Stage 6 Tasks ★** — 拆成 19 个 atomic task
- **Stage 7 Implementation** — 按 task 推进，每个 commit 映射一个 task
- **Stage 8 / 9** — Human QA + Acceptance（人工关卡）

## 关键技术取舍

- **astro-paper starter + 二次开发**：内容用 Astro Content Collections，posts + projects 双 collection
- **Cloudflare Pages 部署**：纯静态、国内可达、零运维
- **邮箱混淆**：base64 + 客户端 atob 解码，view-source 零明文（满足 AC10）
- **零 JS by default**：Astro 默认产出静态 HTML，加载快、Lighthouse 友好
- **暗黑模式 + 系统字体**：不引 web font，首屏更快

## 完整 artifact 链路

从 brainstorm 到上线的全部 9 个阶段 artifact 都在 [仓库的 workflow 目录](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/personal-website/workflow/001-personal-website)。
