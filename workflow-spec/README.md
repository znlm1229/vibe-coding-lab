# workflow-spec — AI 原生开发工作流程

这是一套面向**团队成员**和 **AI 编码代理**的九步工作流程，核心理念：

> **代码之前先对齐，完成之前先验证。**

九个阶段：

```
Brainstorm → Grill Me → Prototype → SPEC → Plan → Tasks → Implementation → Human QA → Acceptance
                                      ★                  ★                       ★
                                                                ★ = 人工关卡
```

## 文件索引

| 文件 | 版本 | 面向 | 用途 |
|---|---|---|---|
| [`specification.md`](./specification.md) | **v1.2**（正本） | 团队成员 | 标准规范的可读 Markdown 版（推荐起点） |
| [`specification.docx`](./specification.docx) | v1.0（滞后） | 客户 / 团队分享 | 同上的 Word 原件；分发前确认是否要按 md 重新生成 |
| [`SKILL.md`](./SKILL.md) | v1.2 | AI 编码代理 | 可被 Claude Code 等 agent 自动加载的 skill 文件 |
| [`references/spec-template.md`](./references/spec-template.md) | — | 写 SPEC 时参考 | 阶段 4 SPEC 文档模板与可测试验收标准写法 |
| [`references/plan-and-tasks.md`](./references/plan-and-tasks.md) | — | 拆 Plan/Tasks 时参考 | 阶段 5 / 6 的结构与任务拆分准则 |
| [`references/tooling.md`](./references/tooling.md) | v1.2 | 选工具时参考 | 每个阶段的现成工具推荐（含 v1.2 superpowers 系列） |

> **v1.1 → v1.2 主要变化**（2026-05-19，触发于 vibe-coding-lab 任务 001 复盘）：
> - 扩展 4 个 stage-skill 绑定：Stage 1 `brainstorming` / Stage 5 `writing-plans` / Stage 7→8 强制 `verification-before-completion` / Stage 8 `requesting-code-review`
> - AC 双通道验证约定（每条 AC 显式 AI 验证 + 人工验证）
> - OQ 类型标记（technical / taste）
> - bug 回路 commit 用 `fix(TX):` 前缀
> - Auto-mode 不可凌驾人工关卡
> - 2 条新失败模式（字面 AC ≠ 行为 AC、SPEC 早于栈选定）
> - SKILL.md 加 frontmatter 元数据、中文 trigger phrases、anti-trigger
>
> 详见 [`specification.md#8-更新记录`](./specification.md#8-更新记录) 和 [`SKILL.md#changelog`](./SKILL.md#changelog)。
>
> **v1.0 → v1.1**：Stage 2 Grill Me 绑定强制 skill `grill-me`。

## 怎么用

### 团队成员第一次看

1. 读 [`specification.md`](./specification.md) 第 1–4 节，理解理念、九个阶段、三个人工关卡。
2. 第 5 节按阶段细看；遇到要写 SPEC / Plan / Tasks 时查对应的 `references/`。
3. 真的要落地时，参考 [`references/tooling.md`](./references/tooling.md) 选合适的工具。

### AI 编码代理

把 [`SKILL.md`](./SKILL.md) 放进你的 agent skill 目录（例如 Claude Code 的 `~/.claude/skills/` 或项目内的 `.claude/skills/`），让 agent 在编码任务上自动遵循九步流程。SKILL.md 的 frontmatter 里写了触发条件，agent 会自行识别。

### 在新项目落地

1. 在新项目仓库根目录建 `CLAUDE.md`（或 `AGENTS.md`），写明：本项目遵循 `workflow-spec/` 流程，并贴上九步速览。
2. 把 `workflow-spec/` 整个目录拷过去，或在 `CLAUDE.md` 里指向本仓库的 URL。
3. 第一个真任务从 Stage 1 (Brainstorm) 走起。

## 关于来源

文档原始作者整理了完整的九步流程规范 + 模板 + 工具推荐，本目录将这套文档收录到 vibe-coding-lab，并：

- 把 docx 转成可读 Markdown（保留原件以便分享）
- 按 SKILL.md 自身的引用结构（`references/`）组织目录
- 将中文文件名换成英文（避免 GitHub URL 编码与搜索问题）
- 补充本 README 串联所有文档

任何修改都应反映在 [`specification.md`](./specification.md)；docx 仅在大版本发布时同步更新。
