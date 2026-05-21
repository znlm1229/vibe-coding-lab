# guess-figure

vibe-coding-lab 的第二个实战项目：**猜历史人物程序** —— 玩家根据 AI 给出的若干条线索猜出目标人物。

## 当前状态

🟡 **Stage 1 Brainstorm 启动中** —— 形态（Web / CLI / Chat / 移动端）、机制（LLM 实时生成 vs 预设题库 vs 混合）、技术栈待 Brainstorm + Grill Me 后定。

- **AI 行为约束入口**：[`CLAUDE.md`](./CLAUDE.md) —— 项目级 AI 指令，规则派生自 workflow-spec，本目录工作时 Claude Code 自动加载
- **进行中任务**：[`workflow/001-guess-figure/`](./workflow/001-guess-figure/)
- 任务级薄骨架：[`workflow/_template/`](./workflow/_template/)（仅占位字段）
- **模板权威源**：[`../../workflow-spec/`](../../workflow-spec/) v1.2 —— 细则、SPEC/Plan/Tasks 完整范式、commit 约定单点更新源

## 工作流（必须遵循）

```
Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★
```

★ = 人工关卡，未经用户确认不得跨越。完整规范见 [`workflow-spec/specification.md`](../../workflow-spec/specification.md)。

## 任务台账

<!-- 完成或进行中的任务列在这里，按编号倒序 -->

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| 001 | [`001-guess-figure`](./workflow/001-guess-figure/) | 🟡 **进行中** | Stage 1 Brainstorm 启动 |

## 待办

- [x] 确定项目正式名称（已定 `guess-figure`，目录从 `002` 重命名）
- [x] 项目级 [`CLAUDE.md`](./CLAUDE.md) 已建（派生自 workflow-spec v1.2）
- [ ] 在仓库根 [`README.md`](../../README.md) 的「内容索引」表里登记 guess-figure 项目（建议第一个任务上线后做）
