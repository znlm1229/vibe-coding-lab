# 002-blog-and-projects

> **按规模伸缩任务**：内容维护性质，按 workflow-spec 规则一跳过 Stage 1-6 + 8-9 标准流程，仅在 Stage 7 落主体工作。

## 任务范围

加 1 篇博客 + 1 个项目集 entry 介绍刚完成的 [guess-figure](../../../guess-figure/) 项目并发布到 [lw-personal.pages.dev](https://lw-personal.pages.dev)。

## 为什么按规模伸缩

[personal-website README](../../README.md) 明示日常内容维护流程：「直接编辑 `src/content/{posts,projects,pages}/*.md` → git push → CF Pages 自动 deploy」。本任务正是这个工作流的应用，**没有架构 / 路由 / 组件改动**，纯内容创作。

跳过阶段说明：
- **Stage 1-3（Brainstorm / Grill Me / Prototype）**：没有要发散的方向、没要拷问的设计、没要验证的不确定性 — 任务范围用户已明确（加 guess-figure 的项目集 entry + 复盘博客）
- **Stage 4 SPEC**：无可测试 AC（"博客文章 + 项目集 entry 上线可访问"是日常维护默认目标）
- **Stage 5-6（Plan / Tasks）**：单 commit 任务，无需拆 phase / task
- **Stage 8（Human QA）**：上线后用户访问 [lw-personal.pages.dev](https://lw-personal.pages.dev) 看新内容 OK 即可
- **Stage 9（Acceptance）**：用户看到新内容已发布 = 验收通过

## 实际工作

- `projects/personal-website/src/content/posts/guess-figure-retrospective.md` — 博客文章，改写自 [guess-figure stage-10 retrospective](../../../guess-figure/workflow/001-guess-figure/10-retrospective.md)
- `projects/personal-website/src/content/projects/guess-figure.md` — 项目集 entry
- `projects/personal-website/README.md` 任务台账加 002 行

详见同目录 [`07-implementation.md`](./07-implementation.md)。
