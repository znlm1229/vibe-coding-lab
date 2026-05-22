# personal-website

vibe-coding-lab 的第一个实战项目：**用户的个人网站**。目的是借这个端到端的真实项目跑通九步 AI 原生开发工作流。

## 当前状态

🟢 **上线运行中** —— 首版 MVP 已上线 [lw-personal.pages.dev](https://lw-personal.pages.dev/)，13/13 AC 通过用户验收（2026-05-19）。

- 已完成任务：001 — 用九步工作流端到端搭出个人网站
- 内容维护：直接编辑 `src/content/{posts,projects,pages}/*.md` → git push → CF Pages 自动 deploy
- 后续候选任务：002（UX 收尾）、003（品牌化），用户提议时再开

## 工作流（必须遵循）

```
Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★
```

★ = 人工关卡，未经用户确认不得跨越。完整规范见 [`workflow-spec/specification.md`](../../workflow-spec/specification.md)。**Stage 2 强制调用 `grill-me` skill**（v1.1+）。

## 目录结构

| 路径 | 说明 |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | AI agent 项目级指令（Claude Code 自动加载） |
| [`workflow/`](./workflow/) | 每个任务的 artifact 集合，按 `NNN-name/` 划分 |
| [`workflow/_template/`](./workflow/_template/) | 新任务子目录的模板 |
| `src/` | 实际代码（待第一次 SPEC 后定义结构与技术栈） |

## 开启一个新任务（最小手册）

1. 用户给出任务描述
2. AI 按规模评估，提议走哪些阶段、跳过哪些、为什么 → 等用户确认
3. AI 复制 `workflow/_template/` 到 `workflow/NNN-task-name/`
4. AI 按阶段填 artifact，**每个人工关卡（★）停下等用户确认**
5. 实现代码进 `src/`，每个 commit 映射到一个 task
6. Stage 8 / 9 由用户实测验收

## 任务台账

<!-- 完成或进行中的任务列在这里，按编号倒序 -->

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| 002 | [`002-blog-and-projects`](./workflow/002-blog-and-projects/) | ✅ **已完成 2026-05-22** | 按规模伸缩跳过 Stage 1-6 + 8-9；加 1 篇博客（guess-figure 复盘）+ 1 个项目集 entry（guess-figure），发布到 [lw-personal.pages.dev](https://lw-personal.pages.dev/) |
| 001 | [`001-personal-website`](./workflow/001-personal-website/) | ✅ **已完成 2026-05-19** | 用户验收通过，13/13 AC 满足，上线 [lw-personal.pages.dev](https://lw-personal.pages.dev/) |
