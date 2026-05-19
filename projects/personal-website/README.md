# personal-website

vibe-coding-lab 的第一个实战项目：**用户的个人网站**。目的是借这个端到端的真实项目跑通九步 AI 原生开发工作流。

## 当前状态

🟢 **进行中** —— 项目定位「个人网站」已明确；具体范围（极简名片 / 博客 / 作品集 / 混合 / SaaS 寄生等定位）待 Stage 2 `grill-me` 拷问后定型。

- 当前任务：[`workflow/001-personal-website/`](./workflow/001-personal-website/) — Stage 1 Brainstorm

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

| # | 任务 | 状态 | 当前阶段 |
|---|---|---|---|
| 001 | [`001-personal-website`](./workflow/001-personal-website/) | 进行中 | **Stage 8 Human QA ★** ｜ 上线 [lw-personal.pages.dev](https://lw-personal.pages.dev/) |
