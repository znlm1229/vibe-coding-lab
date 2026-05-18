# first-project

vibe-coding-lab 下的第一个示例项目，目的是**用九步 AI 原生开发工作流跑通一个真实的端到端项目**。

## 当前状态

🚧 **未启动** —— 项目的具体功能、技术栈、范围都待用户提出。一旦给出第一个任务，AI agent 会按 [`workflow-spec`](../../workflow-spec/) 流程从 Stage 1 开始。

## 工作流（必须遵循）

```
Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★
```

★ = 人工关卡，未经用户确认不得跨越。完整规范见 [`workflow-spec/specification.md`](../../workflow-spec/specification.md)。

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

- *（尚无任务）*
