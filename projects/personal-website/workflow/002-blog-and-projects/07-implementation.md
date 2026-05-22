# Stage 7 ｜ Implementation 实现

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-7--implementation-实现)

按 [README.md](./README.md) 跳过 Stage 1-6 + 8-9，仅本阶段落实际工作。

## 具体动作

| # | 动作 | 输出文件 |
|---|---|---|
| 1 | 写 guess-figure 项目集 entry | `src/content/projects/guess-figure.md` |
| 2 | 写 guess-figure 复盘博客（改写自 stage-10）| `src/content/posts/guess-figure-retrospective.md` |
| 3 | 更新本项目 README 任务台账 +002 行 | `projects/personal-website/README.md` |
| 4 | commit + push 触发 CF Pages auto deploy | git history + lw-personal.pages.dev 自动发布 |

## 内容设计要点

### 项目集 entry（guess-figure.md）

frontmatter 字段沿用 [`vibe-coding-lab.md`](../../src/content/projects/vibe-coding-lab.md) 同款 schema：
- title / summary / tech[] / githubUrl / status / pubDate / featured / order
- order: 2（vibe-coding-lab 是 order: 1）

内容：项目背景 + 玩法说明 + 关键架构 + Prototype benchmark 救场 + Stage 8 抓到的 3 个 bug + 完整 artifact 链接。

### 博客（guess-figure-retrospective.md）

改写自 [10-retrospective.md](../../../guess-figure/workflow/001-guess-figure/10-retrospective.md)，但**面向公众读者**（不是给自己看的复盘）：
- 弱化对 workflow-spec 内部细节的反馈（v1.3 候选）
- 强化"2 天端到端做出公开上线游戏"故事性
- 保留 5 个赢点 + 5 个摩擦点 + 意外发现 — 这些对 vibe coding 同行有价值
- 加链接到上线 URL + GitHub 源码 + workflow artifact

frontmatter 沿用 [`hello-and-the-nine-stages.md`](../../src/content/posts/hello-and-the-nine-stages.md) 同款 schema。

## Done when

- 2 个 .md 文件 commit 到 main + CF Pages auto deploy 完成
- 访问 https://lw-personal.pages.dev/posts/guess-figure-retrospective/ 看到博客
- 访问 https://lw-personal.pages.dev/projects/guess-figure/ 看到项目集 entry
- /posts/ 和 /projects/ 列表里都能看到新内容
