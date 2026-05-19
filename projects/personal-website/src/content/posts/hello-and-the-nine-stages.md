---
title: "Hello — 用九步工作流搭这个网站"
description: "本站第一篇博客。记录我用 vibe-coding-lab 的九步 AI 原生开发工作流从零搭出这个站的过程。"
pubDatetime: 2026-05-19T10:00:00+08:00
author: "李旺"
tags: ["vibe-coding", "workflow", "meta"]
featured: true
---

如果你恰好刷到这篇，欢迎你 —— 这是这个站第一篇博客。

## 为什么有这个站

我在做 [vibe-coding-lab](https://github.com/znlm1229/vibe-coding-lab)，想用一个真实的端到端项目把九步 AI 原生开发工作流跑通。"做一个属于自己的个人网站"刚好够大也够小，第一个项目就是它。

## 九步流程速览

整套九步：

> Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★

★ = 人工关卡，AI 在没拿到我明确确认前不能跨越。这是整个工作流最关键的地方 —— 防止 AI 充满自信地构建了错的东西，或者构建对了但没人检查过。

## 我做了什么

- **Brainstorm**：让 AI 列了 5 个个人网站方向（极简一页 / 博客驱动 / 作品集驱动 / 综合站 / SaaS 寄生），我选「极简 + 作品集」两个方向推进
- **Grill Me**：调用 `grill-me` skill 跑 10 轮拷问，从动机、受众、维护频率到非目标全部理清
- **SPEC**：13 条可测试 AC，包括"HTML 不含明文邮箱"这种隐私守则
- **Plan + Tasks**：拆成 9 个 phase、19 个 atomic task
- **Implementation**：每个 task 一个 commit，目前进行中

## 技术栈

Astro 6 + Tailwind CSS + [astro-paper](https://github.com/satnaing/astro-paper) starter + Cloudflare Pages 部署。

## 完整 artifact

如果你想看从 brainstorm 到上线的完整记录，[去仓库](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/personal-website/workflow/001-personal-website) 看 01–09 的 markdown artifact。

第一次写「博客」。欢迎反馈 —— [发邮件](/about/#联系方式) 或在 [项目仓库](https://github.com/znlm1229/vibe-coding-lab) 提 issue。
