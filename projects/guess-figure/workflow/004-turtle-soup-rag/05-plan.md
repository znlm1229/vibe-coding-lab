# Stage 5 ｜ Plan 计划

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-5--plan-计划)
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)
>
> **要点**：从已确认的 SPEC 出发，回答「怎么做」与「按什么顺序」。

---

## Approach

本阶段使用 `writing-plans` skill 产出实现计划；计划保存在本任务的 workflow artifact 中，而不是默认 `docs/superpowers/plans/`，因为 guess-figure 项目规定 `workflow/NNN-name/05-plan.md` 是跨会话 source of truth。

总体策略：先把 Cloudflare RAG 基建做成可小样本验证、可重跑、可追溯的离线构建链路，再把线上 RAG 问答封装成独立 server 模块和 API，最后接入两个玩法 UI。这样能把全量二十四史构建的风险和用户玩法状态机解耦。

关键架构决策：

- **Cloudflare 分层**：R2 存全量原始/清洗语料和 chunk JSONL；Vectorize 存 1024 维向量与短正文 metadata；D1 存 corpus/index/build manifest；KV 复用为 RAG 问答缓存和预算计数。
- **RAG 服务边界**：新增 server-side RAG 模块，暴露“校验问题 → 查缓存 → embedding → Vectorize → rerank → LLM 三态 → 写缓存”的单一入口。UI 不直接碰 Vectorize / Workers AI。
- **玩法状态机边界**：主游戏嵌入式海龟汤只扩展现有 `game-state` 和 `/play` UI；独立海龟汤用新路由和独立状态机，避免污染主游戏逻辑。
- **数据生产边界**：全量语料构建脚本放 `scripts/`，支持小样本 dry-run、断点恢复、报告输出；正式全量运行可以晚于代码合并，但 AC 要能用小样本验证所有链路。
- **测试优先**：Stage 7 每个实现任务先写失败测试；全量云资源相关逻辑用接口封装 + mock 单测，小样本集成再用真实 Wrangler/Cloudflare 验证。

## Phases

1. **Cloudflare 资源与类型契约**
   - 交付：`wrangler.toml` 新增 Vectorize / R2 / AI bindings；`src/app.d.ts` 补充 `GF_VECTORIZE`、`GF_CORPUS_R2`、`AI` 等类型；新增 D1 migration 存 corpus/build manifest。
   - 为什么排这里：后续构建脚本、API、测试都依赖 binding 名和 schema；先锁契约可减少后续返工。

2. **语料构建与质量校验脚本**
   - 交付：`scripts/build_turtle_corpus.py`、`scripts/tests/test_turtle_corpus.py`、R2 object key 规范、chunk metadata 校验、构建报告格式；小样本 dry-run 覆盖 profiles / wikipedia / wikisource。
   - 为什么排这里：RAG 质量依赖数据覆盖。Stage 3 已证明只靠 profile + Wikisource 不够，所以先保证维基主条目和 chunk 质量进入管线。

3. **RAG server 核心模块**
   - 交付：`src/lib/server/turtle-rag.ts`、`src/lib/server/turtle-cache.ts`、`src/lib/server/turtle-question.ts`、对应 Vitest；实现 invalid 校验、cache key、query expansion、Vectorize 查询、rerank、三态 LLM prompt、错误降级。
   - 为什么排这里：两个玩法共享 RAG 问答，先做共享层可以避免 UI 层重复实现。

4. **后端 API 与持久化**
   - 交付：`/api/turtle/question`、`/api/turtle/answer`、必要的 game finish 字段/新表、D1 写入路径、API tests；主游戏用过海龟汤后记录 0 分。
   - 为什么排这里：前端状态机需要稳定 API 合同；持久化也决定排行榜和个人记录不会被辅助模式污染。

5. **独立海龟汤数据字段与汤面质量**
   - 交付：为 `figures.json` 或相邻数据文件增加 `turtle_intro`，新增生成/校验脚本，保证极短隐晦且禁强识别信息。
   - 为什么排这里：独立 UI 的第一屏依赖汤面字段；先做校验再接 UI，避免上线后汤面太露骨。

6. **前端玩法接入**
   - 交付：主游戏 `/play` 第 6 条线索后的嵌入式入口和问答面板；新 `/turtle-soup` 独立页面；共享 UI 组件（问答列表、次数计数、答案提交、降级提示）。
   - 为什么排这里：UI 最容易受 API 和状态字段变化影响，放在共享层和数据字段之后。

7. **验收自动化与 Human QA 准备**
   - 交付：AC 验证脚本、Stage 7 证据表、Playwright/手工 QA checklist、构建/类型/单测通过。
   - 为什么排这里：最后统一把 SPEC 20 条 AC 映射到命令和人工操作，准备 Stage 8。

## Dependencies

- Cloudflare R2 当前未启用；Phase 1/2 前需要用户或 agent 在 Cloudflare Dashboard 启用 R2，并创建 bucket。
- Vectorize index 当前不存在；Phase 1 需要创建 1024 维 cosine index，名字建议 `guess-figure-turtle-rag`。
- Workers AI 模型已在 catalog 中可见，但 wrangler 版本是 3.114.17 且提示过期；Phase 1 决定是否升级到 Wrangler 4，避免 Vectorize V2 命令差异。
- Phase 2 依赖 Phase 1 的 R2 / D1 / Vectorize binding 名；Phase 3 依赖 Phase 2 的 chunk metadata 格式。
- Phase 4 API 依赖 Phase 3 RAG 模块和现有 `check-answer` 判定逻辑。
- Phase 6 UI 依赖 Phase 4 API 合同和 Phase 5 `turtle_intro` 字段。
- 现有共享模块触碰点：`src/lib/types.ts`、`src/lib/game-state.svelte.ts`、`src/routes/play/+page.svelte`、`src/routes/api/game/finish/+server.ts`、`migrations/`、`wrangler.toml`。
- Stage 2/3 artifact 是决策依据；如果实现中发现全量二十四史抓取方式不可行，必须回 Stage 4 修 SPEC，不得静默降级成 65 人本传。

## Risks

- **R2 未启用阻塞云端构建**：先用小样本本地 dry-run 和 mock R2 测试脚本；正式 Stage 7 中把 R2 enable 作为 T1 的 Done when。
- **全量二十四史构建耗时/失败点多**：脚本必须支持 checkpoint、source-level retry、失败报告；Stage 7 首先跑小样本，再跑分批全量。
- **Vectorize metadata 超限**：chunk 校验脚本在 upsert 前计算 JSON byte length，超过 10KiB 直接失败并报告。
- **召回跨人物串线**：query expansion 加目标人物 name/aliases；profile/wiki chunk 带 `figure_id` 并 boost；二十四史 chunk 用书/卷/人物名匹配加权；AC6/AC18 专门覆盖。
- **三态 LLM 猜测**：prompt 明确“证据不足返回无关”；测试构造无证据问题，防止把不确定输出成「否」。
- **成本失控**：cache key 含 index/prompt version，30 天 TTL；预算耗尽走 degraded；构建脚本输出 token/Neuron 估算和分批进度。
- **主游戏分数回归**：嵌入式海龟汤用过后固定 0 分，必须在状态机和 `/api/game/finish` 双层测试。
- **汤面太露骨**：生成后用禁词/长度质量检查，人工抽样；taste 类内容允许用户后续手改。

## Test strategy

- 单元测试覆盖：
  - `turtle-question`：yes/no 校验、invalid 不消耗次数、直接猜名不拦截。
  - `turtle-cache`：key 含 figure/question/index/prompt version、TTL、cache hit 不调用后续依赖。
  - `turtle-rag`：query expansion、三态 prompt 解析、证据不足返回无关、Workers AI/Vectorize/LLM error degraded。
  - `game-state`：第 6 条开放嵌入式入口、5 问上限、用过后 0 分。
  - 汤面质量脚本：长度、强识别禁词、字段存在性。
- 集成测试覆盖：
  - 小样本 `build_turtle_corpus.py --sample`：profile + wikipedia + wikisource → chunk report → mock/real R2 object key → D1 manifest。
  - `/api/turtle/question`：invalid、cache miss、cache hit、degraded、Stage 3 失败 case（关羽武圣）补维基后应答「是」。
  - `/api/turtle/answer`：精确匹配、LLM 裁判 fallback、3 次答案机会。
  - Wrangler/Cloudflare 资源检查：Vectorize/R2/D1/AI bindings 可见。
- 留给 Stage 8 Human QA 的部分：
  - 浏览器实际玩主游戏到第 6 条，打开嵌入式海龟汤，问 1-2 个问题，猜中后确认 0 分。
  - 浏览器打开 `/turtle-soup`，确认汤面短且隐晦，15 问/3 答计数正确。
  - 手动测试非 yes/no 问法、直接猜名问题、预算/网络降级提示是否可理解。
  - 人工抽查 5 个 chunk 的正文和来源追溯是否可信，抽查 10 个 `turtle_intro` 是否足够隐晦。
