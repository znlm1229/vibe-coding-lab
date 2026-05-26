# 003-v3-content-refresh

> 内容维护任务:加 guess-figure 003(线索 pipeline 重构 + 题库 50→65)的复盘博客 + 更新 guess-figure 项目卡 V3 section + 润色现有 3 篇博客。

## 任务规模

跟 [002-blog-and-projects](../002-blog-and-projects/) 同款 — 内容更新,无技术变更。**按规模伸缩跳过 Stage 1-6 + 8-9**,仅 Stage 7 落实际工作。

## 触发

[guess-figure 003-clue-optimization](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure/workflow/003-clue-optimization) 2026-05-26 用户验收通过(15/18 AC PASS + 3 偏差 explicit accept = SPEC v1.1)。题库 50→65 / 3 步 LLM pipeline / quality_check 95.4% / ¥2.61 / 123 测全 pass。需要在个人网站反映 V3 状态 + 写复盘博客。

## 跳过的阶段 + 理由

| Stage | 跳过理由 |
|---|---|
| 1 Brainstorm | 内容维护单一方向,无需发散 |
| 2 Grill Me | 同上,无设计决策需拷问 |
| 3 Prototype | 不适用 |
| 4 SPEC | 范围由本 README 列出即可,无需正式 SPEC |
| 5 Plan | 单一步骤,无需 phase 排序 |
| 6 Tasks | 见 07 内的"具体动作"表 |
| 8 Human QA | 内容更新由用户在 PR/上线后浏览器看(in-chat review) |
| 9 Acceptance | 同上,用户简短 sign-off 即可 |

## 具体动作(详见 [07-implementation.md](./07-implementation.md))

| # | 动作 | 输出文件 |
|---|---|---|
| 1 | 写 003 复盘博客(类似 002 那篇) | `src/content/posts/guess-figure-003-clue-optimization.md`(新) |
| 2 | 更新 guess-figure 项目卡加 V3 section | `src/content/projects/guess-figure.md`(改) |
| 3 | 润色现有 3 篇博客(taste-driven,用户先 review 方向再实施) | `src/content/posts/*.md`(改) |
| 4 | 更新本项目 README 任务台账 +003 行 | `projects/personal-website/README.md` |

## Done when

- 1 个新博客 .md + 1 个项目卡更新 + 3 篇旧博客润色完成
- commit 推 main → CF Pages auto deploy
- 访问 https://lw-personal.pages.dev/posts/guess-figure-003-clue-optimization/ 看到新博客
- 项目卡 V3 section 显示正确(题库 65 / 3 步 pipeline / 95.4% / ¥2.61)
