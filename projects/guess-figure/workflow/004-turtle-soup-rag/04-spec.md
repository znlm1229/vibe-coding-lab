# Stage 4 ｜ SPEC 规格 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-4--spec-规格人工关卡)
> 标准模板见 [`spec-template.md`](../../../../workflow-spec/references/spec-template.md)
>
> **要点**：写"做什么"不写"怎么做"；验收标准必须**可测试**；**用户未确认前不得进入 Stage 5**。
>
> **v1.2 关键约定**：
> - **AC 必须分两栏 AI 验证 / 人工验证**（两边都 PASS 才算 PASS）—— 见下方表格模板
> - **OQ 必须标 type**：`technical`（客观）vs `taste`（主观，AI 推荐仅占位）
> - SPEC 修订需显式版本号 + 修订日志，不许静默漂移

---

## Summary

为 guess-figure 增加第 4 种玩法「海龟汤模式」和共享 RAG 史料库。玩家围绕隐藏目标人物提问，AI 只回答「是 / 否 / 无关」；系统通过 Cloudflare 上的全量二十四史、维基、现有人物画像等语料召回证据，再由 LLM 做三态判断。

## Problem

现有 guess-figure 玩法主要是线索递进式猜人物，玩家只能被动接受线索。004 要增加主动提问型玩法，让玩家通过 yes/no 问题探索目标人物，同时把 003 形成的 profile 数据资产升级为可复用的史料 RAG 基建。

如果不做 RAG，仅靠长上下文或模型记忆回答，会出现事实不可追溯、证据不足时误答「否」、后续扩题难复用的问题。Stage 3 原型还证明，仅 profile + Wikisource 本传不足以覆盖「后世尊号 / 文化影响」类问题，因此维基主条目也必须进入语料。

## Goals

- **G1 史料基建**：构建 Cloudflare 托管的 RAG 史料库，覆盖现有 profiles、维基主条目、全量二十四史清洗语料；全量语料进入 Cloudflare 存储体系，不进入 git。
- **G2 三态问答**：提供面向目标人物的 RAG 问答能力，合法 yes/no 问题只返回「是 / 否 / 无关」，证据不足时必须返回「无关」。
- **G3 子模式 1**：在主游戏第 6 条线索展示后开放嵌入式海龟汤求救，最多 5 问，用过后该局固定 0 分。
- **G4 子模式 2**：新增独立海龟汤入口，开局给 1 条极短隐晦汤面，玩家最多 15 问、最多 3 次答案提交，猜中目标人物即胜利。
- **G5 构建可追溯**：每次语料构建有 corpus version / index version / build report，可断点恢复并能回溯 chunk 来源。
- **G6 成本兜底**：RAG 问答复用 002 的限流 / LLM 预算思想，并增加 RAG 缓存；缓存命中不重复查 Vectorize、不重复消耗 LLM 预算。

## Non-goals

- 不要求玩家还原完整故事或解释理由；最终答案只判是否猜中目标人物。
- 不展示 RAG 证据给玩家；证据只用于调试、QA 和后续质量分析。
- 不把全量原始/清洗语料提交到 git。
- 不在用户请求时抓取、清洗、embedding 或写入大批语料；线上只做查询。
- 不在 004 中扩充人物题库到 200 人；该方向留给 006。
- 不引入百度百科 / CN-DBpedia 等额外来源；首版数据源限定为 profiles、维基主条目、二十四史、必要的现有 figures 元数据。
- 不让嵌入式海龟汤参与排行榜高分竞争；用过即 0 分。
- 不绕过 Stage 6 人工确认直接实现 UI 或后端。

## Behavior

- **Inputs**:
  - 语料构建输入：`src/lib/data/profiles/*.md`、现有 `figures.json` 人物元数据、目标人物维基主条目、Wikisource 二十四史全量清洗文本。
  - RAG 问答输入：`figure_id`、用户问题、当前模式、`rag_index_version`、`prompt_version`。
  - 答案提交输入：`figure_id`、用户最终答案、当前模式、剩余答案次数。
- **Outputs**:
  - RAG 问答返回给玩家的可见输出只允许为「是」「否」「无关」或 invalid 提示。
  - 调试输出可包含 evidence chunk ids、scores、cache hit、index version，但不得展示给玩家。
  - 独立海龟汤输出开局汤面、剩余提问次数、剩余答案次数、胜负结果和揭晓答案。
  - 嵌入式海龟汤输出当前求救问答记录，并在游戏结束时记录该局用过海龟汤且得分为 0。
- **Key flows**:
  1. **离线构建**：抓取/读取语料 → 清洗 → 500-800 中文字 chunk + 80-120 overlap → Workers AI embedding → upsert Vectorize → R2 保存原始/清洗语料和 chunk JSONL → D1 写 manifest / version / statistics。
  2. **RAG 问答**：校验 yes/no 问法 → 查 KV 缓存 → 隐藏 query expansion 注入目标人物姓名/别名 → Vectorize topK=20 → rerank → 取 4-6 个 chunk → LLM 三态判断 → 写缓存 → 返回三态。
  3. **嵌入式海龟汤**：主游戏显示第 6 条线索后出现入口 → 玩家最多问 5 个 yes/no 问题 → 玩家继续在主游戏提交答案 → 猜中可通关但该局得分固定 0。
  4. **独立海龟汤**：进入 `/turtle-soup` → 随机目标人物 → 显示极短隐晦汤面 → 玩家最多问 15 问、最多提交 3 次答案 → 猜中胜利，否则失败并揭晓。
  5. **最终答案判定**：复用现有姓名识别链路，先精确匹配本名/别名，再用现有 LLM 裁判；不走 RAG，不判解释。
- **Edge cases**:
  - 非 yes/no 问法返回 invalid，不消耗提问次数，不进入 RAG / LLM。
  - 直接问本名、姓氏、别名、朝代、职业等问题允许；按三态规则回答。
  - 证据不足、不确定、问题过宽或和目标人物无清晰关系时返回「无关」。
  - 缓存命中时直接返回缓存答案，但必须受 `rag_index_version` 和 `prompt_version` 约束。
  - 独立模式错误答案只消耗答案提交次数，不消耗提问次数。
  - 15 问用完或 3 次答案都错后失败并揭晓答案。
  - RAG 资源未配置、R2 未启用、Vectorize index 缺失、Workers AI 调用失败时必须可降级，不得让页面白屏。
- **Error handling**:
  - 请求限流超出时返回可理解错误，不扣提问次数。
  - LLM / Workers AI 网络错误返回重试提示，不把错误记作「否」。
  - RAG 预算耗尽时进入降级：允许最终答案提交，但暂停 RAG 问答或返回额度提示。
  - 构建脚本失败必须写 build report，标出成功/失败 source 和可恢复 checkpoint。

## Constraints

- 技术栈沿用 SvelteKit 5 + adapter-cloudflare + Cloudflare Pages Functions + D1 + KV。
- RAG 新增 Cloudflare Vectorize V2、Workers AI、R2；首版 embedding 主模型为 `@cf/qwen/qwen3-embedding-0.6b`，1024 维，cosine；`@cf/baai/bge-m3` 仅作 A/B 备选。
- Vectorize chunk metadata 必须控制在 10KiB 内；chunk 正文建议 500-800 中文字，overlap 80-120 字。
- R2 是全量语料主存储；D1 不存全量正文，只存 manifest / version / build statistics。
- 全量语料、chunk JSONL、构建中间产物不入 git；脚本、schema、manifest 样例、报告可入 git。
- RAG 缓存 key 必须包含 `figure_id + normalized_question + rag_index_version + prompt_version`，TTL 30 天。
- Stage 3 的 mock embedding 结果不能作为生产验收；Stage 7 必须跑真实 Workers AI embedding + Vectorize 集成验证。
- Cloudflare 当前状态：Vectorize 可访问但尚无 index，R2 尚未启用；实现前必须创建/启用对应资源。
- 所有新脚本和代码注释使用中文；所有文件 UTF-8 no BOM。
- 修改必须保证 `pnpm test`、`pnpm run check`、`pnpm run build` 可通过；涉及 Python 构建脚本需提供对应运行/验证命令。

## Open questions

> 每条 OQ 标 type（v1.2）：`technical` vs `taste`。taste 类必须显式标"AI 起草仅占位"。

| # | 问题 | 类型 | AI 推荐 | 决定 | 阻塞节点 | 备注 |
|---|---|---|---|---|---|---|
| OQ1 | 首版入库范围 | technical | 先做 65 人相关材料 | **全量二十四史入库** | 已决 | 用户要求全量 |
| OQ2 | Cloudflare 存储落点 | technical | R2 全量语料，Vectorize 短正文 metadata，D1 manifest | **确认** | 已决 | D1 不存全文 |
| OQ3 | embedding 主模型 | technical | Workers AI `@cf/qwen/qwen3-embedding-0.6b` + 1024 + cosine | **确认** | 已决 | BGE-M3 备选 |
| OQ4 | chunk 策略 | technical | 500-800 中文字，80-120 overlap | **确认** | 已决 | metadata < 10KiB |
| OQ5 | 是否 rerank | technical | Vectorize topK=20 后 rerank，取 4-6 chunk | **确认** | 已决 | Workers AI reranker |
| OQ6 | 证据不足策略 | technical | 返回「无关」 | **确认** | 已决 | 不猜「否」 |
| OQ7 | 子模式 1 入口 | technical | 第 6 条线索后开放，最多 5 问 | **确认** | 已决 | 求救区入口 |
| OQ8 | 子模式 1 计分 | technical | 用过海龟汤固定 0 分 | **确认** | 已决 | 不污染高分 |
| OQ9 | 子模式 2 轮次 | technical | 15 问 + 3 次答案提交机会 | **确认** | 已决 | 错误答案不消耗提问 |
| OQ10 | 汤面风格 | taste ⚠️ | 12-28 字，极短隐晦，可完全不提生平 | **确认** | Stage 7 生成文案前 | AI 起草仅占位，用户可人工改写 |
| OQ11 | 最终答案判定 | technical | 只判是否猜中人物，不判解释 | **确认** | 已决 | 复用现有姓名判定 |
| OQ12 | 直接猜名问题 | technical | 不禁止，只拦截非 yes/no | **确认** | 已决 | 玩法允许策略性提问 |
| OQ13 | invalid 问法 | technical | 不消耗次数，不进 RAG/LLM | **确认** | 已决 | 返回格式提示 |
| OQ14 | RAG 缓存 | technical | 30 天，key 含 figure/question/index/prompt version | **确认** | 已决 | 命中不查 Vectorize |
| OQ15 | 语料是否入 git | technical | 全量语料不入 git，但进入 Cloudflare 存储 | **确认** | 已决 | R2 主存储 |
| OQ16 | Stage 3 失败 case 处理 | technical | 补维基主条目语料，不放宽三态规则 | **确认** | Stage 7 前 | 来自 prototype 14/15 |

## Acceptance criteria

> Stage 9 会对照本节逐条核对。每条必须二选一可判定，且**必须分 AI 验证 + 人工验证两栏**（v1.2）。
>
> 好：「未登录用户访问 /dashboard 被重定向到 /login。」
> 差：「认证工作得很好。」

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC1 | Cloudflare 环境包含 1024 维 cosine Vectorize index、R2 语料 bucket、D1 manifest 表，且配置记录在项目中 | `pnpm exec wrangler vectorize list`、`pnpm exec wrangler r2 bucket list`、`pnpm exec wrangler d1 execute ... --command "SELECT name FROM sqlite_master"` | 用户在 Cloudflare Dashboard 能看到对应 Vectorize / R2 / D1 资源 |
| AC2 | 离线构建脚本能生成 corpus version、index version、build report，并把原始/清洗语料与 chunk JSONL 放入 R2 | 运行构建 dry-run / 小样本命令，检查 report JSON 含 version、source counts、R2 object keys | 用户查看构建报告，能理解本次构建成功/失败来源和下一步处理 |
| AC3 | git 中不包含全量原始语料、清洗语料或大体量 chunk JSONL | `git ls-files projects/guess-figure | rg "corpus|chunk|wikisource|r2-cache"` 并核对无大体量语料文件 | 用户查看 PR/diff，确认没有把全量语料塞进仓库 |
| AC4 | 构建后的 corpus 覆盖 profiles、维基主条目、全量二十四史三类来源 | 检查 build report 中 `source_type` 覆盖 `profile/wikipedia/wikisource`，且二十四史每部书都有 processed / failed 统计 | 用户抽查报告，确认不是只构建 65 人本传或只构建 profile |
| AC5 | chunk 策略满足 500-800 中文字主体范围、80-120 字 overlap，metadata 包含来源追溯字段且小于 10KiB | 对 chunk JSONL / Vectorize metadata 抽样运行校验脚本 | 用户抽看 5 个 chunk，能看到正文完整、来源可追溯、没有明显断裂 |
| AC6 | RAG 问答检索 query 会注入目标人物姓名和别名，并对同人物 profile/wiki chunk 做过滤或 boost | 单测或集成日志断言 query expansion 含 `figure.name` 和 aliases；测试跨人物污染 case | 用户玩一局时问代词问题（如“他是不是皇帝？”），答案围绕当前目标人物而非其他人物 |
| AC7 | 合法 yes/no 问题的可见回答只可能是「是」「否」「无关」三者之一 | API 测试断言响应 schema 和枚举值 | 用户在页面连续提问，界面不展示长解释或证据 |
| AC8 | 证据不足或不确定时返回「无关」，不会猜测为「否」 | 构造无证据问题的测试 fixture，断言 answer 为 `无关` | 用户提出冷僻且无证据问题，看到「无关」而不是误导性否定 |
| AC9 | 非 yes/no 问法返回 invalid，不消耗提问次数，不调用 RAG / LLM | API 测试断言次数不变，并 mock/日志确认未调用 Vectorize/LLM | 用户输入“他是谁？”后，剩余次数不变且看到格式提示 |
| AC10 | RAG 缓存 key 包含 `figure_id + normalized_question + rag_index_version + prompt_version`，TTL 30 天，命中时不查 Vectorize、不消耗 LLM 预算 | 单测覆盖 key 变化、TTL、cache hit 路径；日志或 mock 断言 hit 不调用 Vectorize/LLM | 用户重复问同一问题，第二次响应明显更快且答案一致 |
| AC11 | 主游戏第 6 条线索展示后出现海龟汤入口，第 1-5 条时不出现 | Svelte/component 测试或 Playwright 检查不同 `revealedCount` 状态 | 用户玩主游戏到第 6 条线索时能看到入口，之前看不到 |
| AC12 | 嵌入式海龟汤每局最多 5 问，用过后该局无论是否猜中都记 0 分 | 状态机/API 测试覆盖 5 问上限和 finish payload `score=0` | 用户用过嵌入式海龟汤后猜中，结算页显示通关但 0 分 |
| AC13 | 独立 `/turtle-soup` 模式开局只显示 1 条极短隐晦汤面，不直接暴露姓名、别名、朝代、职业、作品、典故、亲属、地名等强识别信息 | 质量检查脚本校验 `turtle_intro` 长度与禁词；抽样 65 人通过 | 用户打开独立模式，第一屏只有汤面和提问/答题入口，没有普通 7 条线索 |
| AC14 | 独立模式最多 15 次提问、最多 3 次答案提交；错误答案只消耗答案次数，不消耗提问次数 | 状态机/API 测试覆盖 15 问、3 答、错误答案计数 | 用户手动提交错误答案后，看到答案机会减少但提问次数不变 |
| AC15 | 独立模式最终答案只判断是否为目标人物，不要求解释故事或还原过程 | API 测试复用 `matchExactly` / LLM 姓名裁判，不读取 RAG 证据 | 用户只输入人物名即可胜利，不需要写长解释 |
| AC16 | 直接猜名、姓氏、别名类 yes/no 问题允许进入三态问答 | 测试“他是不是诸葛亮？”这类问题不被 invalid 拦截 | 用户直接问“他是某某吗？”时收到三态回答 |
| AC17 | RAG 预算或 Workers AI/Vectorize 调用失败时，页面有降级提示且不把错误计作「否」或错误答案 | API 测试 mock 网络错误 / 预算耗尽，断言 error/degraded response | 用户在降级状态下看到可理解提示，页面仍可提交最终答案 |
| AC18 | 关羽“后世尊为武圣”类问题在补充维基语料后能回答「是」 | 小样本集成测试复跑 Stage 3 失败 case，断言 answer 为 `是` | 用户在关羽局问“他是不是被后世尊为武圣？”得到「是」 |
| AC19 | 自动化检查通过：前端类型检查、构建、单测、相关 Python 校验脚本 | `pnpm test`、`pnpm run check`、`pnpm run build`、相关 `python ...` 命令均通过 | 用户可在本地或部署环境打开页面，无构建错误 |
| AC20 | 两个子模式完成浏览器人工主路径：嵌入式求救一局、独立海龟汤一局 | Playwright 或手工 QA checklist 记录关键状态截图/日志 | 用户实际操作两条主路径，确认入口、次数、三态、提交答案、结算都符合预期 |

> ⚠️ 如果某条 AC 写不出人工验证路径，它通常不够"行为化"——改 AC 而不是省略人工通道。详见 `spec-template.md` 中「AC 双通道验证约定」。

---

## 修订日志

- **v1.0 draft — 2026-05-27**：基于 Stage 1 用户裁剪、Stage 2 17 个 OQ 决策、Stage 3 prototype 14/15 结果起草。等待用户确认。

## 用户确认

- ☑ **等待确认**
- ⬜ **已确认** — 确认时间：______ ｜ 备注：______

> 一旦确认，本 SPEC 即为契约。后续修改需显式重新确认（不允许静默漂移）。
