# guess-figure

vibe-coding-lab 的第二个实战项目：**猜历史人物 Web 游戏** —— 玩家根据 AI 给出的若干条线索猜出中国历史人物。

## 当前状态

🟢 **上线运行中** —— V1 已上线 [guess-figure.pages.dev](https://guess-figure.pages.dev)，15/15 AC 通过用户验收（2026-05-22）。

- 公网 URL：https://guess-figure.pages.dev
- 已完成任务：001 — 用九步工作流端到端搭出猜历史人物 V1
- 进行中任务：002 — 账号 + 限流（合并 SPEC，Stage 1 Brainstorm 中）
- 题库：50 个中国史人物 × 7 条线索（5 标准 + 2 求救）
- 内容维护：`python scripts/generate_figures.py --names "..."` + `python scripts/merge.py` → git push → CF Pages 自动 deploy
- 后续候选任务：003（线索调优）、004（自定义域名 + 品牌化）、005（V2 题库扩展到 200 人）

## 工作流（必须遵循）

```
Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★
```

★ = 人工关卡，未经用户确认不得跨越。完整规范见 [`workflow-spec/specification.md`](../../workflow-spec/specification.md)。

## 目录结构

| 路径 | 说明 |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | AI agent 项目级指令（Claude Code 自动加载） |
| [`src/`](./src/) | SvelteKit 5 实现（routes / lib / api）+ 题库 `lib/data/figures.json` |
| [`scripts/`](./scripts/) | 内容生产 pipeline（generate_figures.py / merge.py / quality_check.py） |
| [`workflow/`](./workflow/) | 每个任务的 artifact 集合，按 `NNN-name/` 划分 |
| [`workflow/001-guess-figure/`](./workflow/001-guess-figure/) | ✅ 已完成，01-10 artifact + prototype A/B |
| [`workflow/_template/`](./workflow/_template/) | 新任务子目录的模板 |

## 任务台账

<!-- 完成或进行中的任务列在这里，按编号倒序 -->

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| 002 | [`002-account-rate-limit`](./workflow/002-account-rate-limit/) | 🟡 **进行中（2026-05-22 启动，Stage 1 Brainstorm）** | 第二期需求：账号 + 限流（合并为一个 SPEC，因二者方案选择强耦合）。线索调优拆出独立任务 003 |
| 001 | [`001-guess-figure`](./workflow/001-guess-figure/) | ✅ **已完成 2026-05-22** | 用户验收通过，15/15 AC 满足，上线 [guess-figure.pages.dev](https://guess-figure.pages.dev)；SPEC v1.0→v1.1（答错自动消耗一条线索）|
