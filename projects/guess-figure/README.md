# guess-figure

vibe-coding-lab 的第二个实战项目：**猜历史人物 Web 游戏** —— 玩家根据 AI 给出的若干条线索猜出中国历史人物。

## 当前状态

🟢 **V3 上线** —— V1 (001) + 账号+限流+LLM 成本兜底 (002) + 线索 pipeline 重构+题库 65 (003) 全部上线,52/55 AC 累计通过(001 15/15 + 002 22/22 + 003 15/18 + 3 偏差 accept)。

- 公网 URL：https://guess-figure.pages.dev
- 已完成任务：
  - 001 — 用九步工作流端到端搭出猜历史人物 V1（2026-05-22）
  - 002 — 账号 + 双层限流 + LLM 成本兜底（2026-05-25）
  - **003 — 线索 pipeline 重构(3 步 LLM 画像→线索→judge 自动重试)+ 题库 50→65 + quality_check 95.4% 满分率（2026-05-26）**
- 题库：**65 个中国史人物 × 7 条线索**(50 旧 v1+v2 混合 + 15 新皇帝);每人有 `profiles/{id}.md` 8-section 结构化画像(006 候选数据资产)
- 内容维护:**v2 pipeline**: `python scripts/generate_figures.py --names "..." --strong-llm deepseek-v3.2`(三源:维基全文 + Wikidata + 二十四史 Wikisource)→ git push → CF Pages 自动 deploy
- 后续候选任务:004(邮箱 magic link + 排行榜)、005(自定义域名 + 品牌化)、006(补 5 缺失皇帝 + V3 题库扩到 200 人 + 修 3 旧 figure warning)

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
| [`workflow/001-guess-figure/`](./workflow/001-guess-figure/) | ✅ 已完成 2026-05-22，01-10 artifact + prototype A/B |
| [`workflow/002-account-rate-limit/`](./workflow/002-account-rate-limit/) | ✅ 已完成 2026-05-25，01-09 artifact + SPEC v1.0.1 |
| [`workflow/_template/`](./workflow/_template/) | 新任务子目录的模板 |
| [`wrangler.toml`](./wrangler.toml) | CF Pages 配置（D1 + 2 KV bindings + 6 env vars，002 引入）|
| [`migrations/0001_init_users_and_games.sql`](./migrations/0001_init_users_and_games.sql) | D1 初始 schema（002 引入）|

## 任务台账

<!-- 完成或进行中的任务列在这里，按编号倒序 -->

| # | 任务 | 状态 | 备注 |
|---|---|---|---|
| 003 | [`003-clue-optimization`](./workflow/003-clue-optimization/) | ✅ **已完成 2026-05-26** | 用户验收通过(15/18 AC PASS + 3 偏差 accept)。题库 50→65(31 v2 + 19 v1 旧版混合 + 15 新皇帝);prompt+pipeline 重构(3 步 LLM:画像→线索→judge 自动重试);quality_check 95.4% 满分率;成本 ¥2.61。5 缺失皇帝/3 旧 figure warning 留 006 |
| 002 | [`002-account-rate-limit`](./workflow/002-account-rate-limit/) | ✅ **已完成 2026-05-25** | 用户验收通过，22/22 AC 满足。账号 (HMAC signed cookie + D1 user+games) + 双层限流 (CF dashboard P 受 free plan 限制 acknowledge / Workers KV Q 计数器主路径) + LLM 成本兜底 (KV cache 命中 ~3x 快于 LLM / 日预算 V8000+X50 / degraded 不消耗线索)；SPEC v1.0→v1.0.1（free plan 限制 acknowledge）|
| 001 | [`001-guess-figure`](./workflow/001-guess-figure/) | ✅ **已完成 2026-05-22** | 用户验收通过，15/15 AC 满足，上线 [guess-figure.pages.dev](https://guess-figure.pages.dev)；SPEC v1.0→v1.1（答错自动消耗一条线索）|
