# Stage 6 ｜ Tasks 任务 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-6--tasks-任务人工关卡)
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)
>
> **要点**：每个任务**可独立完成**；标 Touches / Done when / Depends on；**用户未确认前不得进入 Stage 7**。
>
> **v1.2 commit 前缀约定**：
> - `task-TX:` 新 task 首次实现
> - `stage-N:` 阶段产出 / 转换
> - `fix(TX):` 已完成 task 的 bug 修复（Stage 8 回路用）
> - `chore:` / `docs:` / `spec(vX.Y):` 其它治理
>
> **每个 task 的 Done when 必须可验证**（不能写"功能完成"这种主观断言，要写能跑出证据的条件）。

---

## 任务清单

- [ ] **T1 — Cloudflare 资源与绑定契约**
  - Touches: `wrangler.toml`、`src/app.d.ts`、`.env.example`、`migrations/0002_turtle_rag_manifest.sql`
  - Done when: `wrangler vectorize list`、`wrangler r2 bucket list`、`wrangler d1 execute guess-figure-db --remote --command "SELECT name FROM sqlite_master"` 能看到 004 所需资源；`pnpm run check` 能识别新增 bindings 类型
  - Depends on: nothing

- [ ] **T2 — 本地语料构建与 chunk 校验**
  - Touches: `scripts/build_turtle_corpus.py`、`scripts/turtle_corpus.py`、`scripts/tests/test_turtle_corpus.py`、`scripts/README.md`
  - Done when: 小样本 dry-run 生成包含 `profile/wikipedia/wikisource` 的 build report；测试覆盖 500-800 字 chunk、80-120 overlap、metadata 小于 10KiB
  - Depends on: T1

- [ ] **T3 — Cloudflare 入库链路**
  - Touches: `scripts/build_turtle_corpus.py`、`scripts/turtle_cloudflare.py`、`scripts/tests/test_turtle_cloudflare.py`
  - Done when: `--sample --cloud` 可把原始/清洗语料和 chunk JSONL 写入 R2、向 Vectorize upsert 1024 维向量、向 D1 写入 manifest；失败时生成可恢复 checkpoint 与失败 source 报告
  - Depends on: T1, T2

- [ ] **T4 — RAG 问题校验与缓存核心**
  - Touches: `src/lib/server/turtle-question.ts`、`src/lib/server/turtle-cache.ts`、`src/lib/server/turtle-question.test.ts`、`src/lib/server/turtle-cache.test.ts`
  - Done when: 单测覆盖 invalid 不消耗次数、直接猜名 yes/no 不拦截；缓存 key 含 `figure_id + normalized_question + rag_index_version + prompt_version` 且 TTL 为 30 天
  - Depends on: T1

- [ ] **T5 — RAG 检索、rerank 与三态裁判**
  - Touches: `src/lib/server/turtle-rag.ts`、`src/lib/server/turtle-rag.test.ts`、`src/lib/server/turtle-prompts.ts`
  - Done when: mock 测试覆盖 query expansion、Vectorize topK=20、rerank 后取 4-6 chunks、返回值只允许「是/否/无关」；证据不足返回「无关」，关羽“武圣”维基 fixture 返回「是」
  - Depends on: T2, T4

- [ ] **T6 — 海龟汤问答 API**
  - Touches: `src/routes/api/turtle/question/+server.ts`、`src/routes/api/turtle/question/+server.test.ts`、`src/lib/types.ts`
  - Done when: API 测试覆盖 invalid、cache miss、cache hit、degraded 四条路径；命中缓存时 mock 断言不调用 Vectorize / LLM
  - Depends on: T4, T5

- [ ] **T7 — 答案提交与持久化状态**
  - Touches: `src/routes/api/turtle/answer/+server.ts`、`src/routes/api/game/finish/+server.ts`、`src/lib/server/turtle-session.ts`、`migrations/0003_turtle_sessions.sql`
  - Done when: API 测试覆盖独立模式 3 次答案机会且错误答案不消耗提问次数；嵌入式模式用过海龟汤后 finish payload 和持久化记录固定 `score=0`
  - Depends on: T6

- [ ] **T8 — 极短隐晦汤面数据与校验**
  - Touches: `src/lib/data/figures.json` 或相邻派生数据文件、`scripts/generate_turtle_intro.py`、`scripts/validate_turtle_intro.py`、`scripts/tests/test_turtle_intro.py`
  - Done when: 每个人物都有 `turtle_intro` 且通过长度/禁词/强识别信息校验；抽样报告显示汤面不直接暴露姓名、别名、朝代、职业、作品、典故、亲属、地名
  - Depends on: T2

- [ ] **T9 — 主游戏嵌入式 UI**
  - Touches: `src/lib/game-state.svelte.ts`、`src/routes/play/+page.svelte`、`src/lib/components/TurtleHelpPanel.svelte`
  - Done when: 组件/状态测试覆盖第 1-5 条线索不显示入口、第 6 条后显示入口；嵌入式问答最多 5 问且用过后结算 0 分
  - Depends on: T6, T7

- [ ] **T10 — 独立 `/turtle-soup` 玩法 UI**
  - Touches: `src/routes/turtle-soup/+page.svelte`、`src/lib/components/TurtleSoupGame.svelte`、`src/lib/components/TurtleQuestionList.svelte`
  - Done when: 页面测试覆盖 15 问、3 次答案提交、错误答案不扣提问次数；本地浏览器打开 `/turtle-soup` 能看到 1 条极短隐晦汤面和问答入口
  - Depends on: T6, T7, T8

- [ ] **T11 — AC 验证脚本与 Stage 8 证据包**
  - Touches: `scripts/verify_ac.sh`、`workflow/004-turtle-soup-rag/07-implementation.md`、`workflow/004-turtle-soup-rag/08-qa.md`
  - Done when: `pnpm test`、`pnpm run check`、`pnpm run build`、相关 Python 测试和 AC 资源检查命令都有记录；Stage 8 QA checklist 覆盖 SPEC AC1-AC20 的人工验证路径
  - Depends on: T1-T10

---

## 用户确认

- ⬜ **等待确认**
- ☑ **已确认** — 确认时间：2026-05-27 14:06:51 +08:00 ｜ 备注：用户回复「开始实现」，并要求主 agent 调度子 agent 实现，可并发的任务用多个子 agent

> 一旦确认，本清单成为 Stage 7 的进度追踪单位。改范围请显式回到本阶段。
