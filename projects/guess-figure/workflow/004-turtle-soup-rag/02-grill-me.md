# Stage 2 ｜ Grill Me 质询拷问

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-2--grill-me-质询拷问)
>
> **强制工具**：调用 `grill-me` skill 驱动本阶段（v1.1+）。skill 会逐条审问用户的方案 / 设计，覆盖决策树的每个分支。AI 自由列几个问题不能替代。skill 不可用时停下来告诉用户，不要静默退化。
>
> **要点**：暴露隐藏假设、边界、失败模式、集成风险；每条具体到可执行（不写「考虑过边界情况了吗？」这种废话）。

## Skill 调用记录

- **Skill**：`grill-me`
- **调用时间**：2026-05-27 12:20:41 +08:00
- **交互轮数**：17 个决策问题，均由用户逐项确认或修正
- **覆盖的关键决策分支**：
  - D 基建范围：首版从 65 人相关语料扩大到全量二十四史入库
  - Cloudflare 存储架构：Vectorize / R2 / D1 分工
  - embedding 模型：Cloudflare Workers AI vs Qwen Cloud vs BGE-M3
  - chunk 策略：短正文 metadata、来源追溯、overlap
  - 召回质量：Vectorize topK + rerank + LLM 三态判断
  - 三态公平性：证据不足时返回「无关」而不是猜「否」
  - 子模式 1：主游戏求救区嵌入海龟汤、最多 5 问、用过后 0 分
  - 子模式 2：独立海龟汤的 15 问、3 次答案机会、极短隐晦汤面、只判人物
  - 输入约束：允许直接猜名问题，非 yes/no 问法 invalid 且不消耗次数
  - 成本与缓存：RAG 问答 30 天缓存，命中不查 Vectorize / 不消耗 LLM 预算
  - 构建链路：离线构建，全量语料入 Cloudflare 存储但不入 git
  - Stage 3 prototype 范围：离线 spike，不做 UI 和正式游戏流程
- **被搁置的分支与理由**：
  - `@cf/baai/bge-m3` 作为 embedding 备选，仅在 Stage 3 召回效果不佳时做 A/B；理由：首版优先走更贴合中文与 Cloudflare 原生的 `@cf/qwen/qwen3-embedding-0.6b`。
  - 全量二十四史生产级完整构建不在 Stage 3 直接完成；理由：先验证召回、三态 prompt、Cloudflare binding 与构建管线风险，再进入 SPEC / Plan。

> 若本阶段按规模伸缩规则跳过，请在此节写「已跳过 + 理由」，下面其余章节留空即可。

## 拷问对象

Stage 1 保留的组合方案：

1. **D 多源向量库基建**：全量二十四史 + 现有 profiles + 维基材料进入 RAG 基础设施。
2. **子模式 1：主游戏嵌入海龟汤**：玩家进入求救区后，可用有限次数是/否/无关问答辅助猜人物。
3. **子模式 2：独立海龟汤**：开局只给 1 条极隐晦汤面，玩家通过最多 15 问和最多 3 次答案提交猜出人物。

本阶段重点拷问：全量语料是否首版就做、Cloudflare 数据落点、embedding 选择、召回质量、三态公平性、两个子模式规则、成本缓存、原型范围。

## 高危风险（必须先解决）

- [x] **全量二十四史入库会把 004 从玩法任务扩大为数据基建任务。** 决策：用户明确要求全量入库；后续 SPEC 必须把离线构建、断点恢复、构建报告、R2/Vectorize/D1 版本账本列为核心目标，而不是临时脚本。
- [x] **D1 不适合承载全量正文。** 决策：全量原始/清洗语料和 chunk JSONL 存 R2，Vectorize metadata 存线上召回所需短正文，D1 只存 manifest / version / 统计。
- [x] **全量语料噪声会导致相似人物、同朝代、同事件误召回。** 决策：Vectorize 先取 topK=20，再用 Workers AI rerank 选 4-6 个 chunk 喂 LLM。
- [x] **证据不足时答「否」会误导玩家。** 决策：RAG 没有足够证据时必须答「无关」，不能把召回不足当作事实否定。
- [x] **子模式 2 的汤面若暴露生平信息，会变成普通猜人物线索。** 决策：离线生成极短极隐晦汤面，可完全不提生平、朝代、职业、作品、典故、亲属、地名等强识别信息。

## 中危风险（可暂缓但要承担）

- [x] **Workers AI 免费额度能覆盖原型和低流量，但全量构建可能超过每日免费 Neurons。** 决策：使用 Cloudflare Workers AI `@cf/qwen/qwen3-embedding-0.6b`，并在构建脚本中支持断点续跑、分批、预算统计；Stage 5 再细化构建节流。
- [x] **Vectorize metadata 每条 10KiB，chunk 正文不能过长。** 决策：chunk 采用 500-800 中文字，80-120 字 overlap，metadata 只放短正文和必要来源字段。
- [x] **直接问姓名/别名可能快速破题。** 决策：不禁止，海龟汤允许聪明提问；只拦截非 yes/no 问法。
- [x] **子模式 1 可能污染排行榜。** 决策：用过主游戏海龟汤后固定 0 分，只帮助通关，不参与高分竞争。
- [x] **答案判定若要求还原故事，公平性和验收复杂度会显著上升。** 决策：最终答案只判是否猜中目标人物，不要求解释故事。

## 低危 / 已知妥协

- [x] **首版 embedding 不直接用 Qwen Cloud `text-embedding-v4`。** 妥协：Cloudflare Workers AI 更便宜且同生态；如 Stage 3 召回表现不够，再评估 BGE-M3 / Qwen Cloud。
- [x] **Stage 3 不做完整 UI 和正式玩法闭环。** 妥协：先做离线 spike 验证召回与三态逻辑，正式 UI 留到 SPEC / Plan / Tasks 确认后。
- [x] **RAG 回答只展示三态，不展示证据。** 妥协：证据片段和 scores 存在缓存/调试字段，不暴露给玩家，保持玩法纯度。

## 待用户回答的开放问题（OQ）

> 用户回答会喂给 Stage 4 SPEC。**每条 OQ 必须标 type**（v1.2+）：

| # | 问题 | 类型 | AI 推荐 | 决定 | 备注 |
|---|---|---|---|---|---|
| OQ1 | D 多源向量库首版入库范围多大？ | technical | 首版先做 65 个已有人物相关材料 | **全量二十四史入库** | 用户明确修正推荐 |
| OQ2 | 线上 RAG 存储架构怎么定？ | technical | Vectorize 存向量和短 chunk metadata；R2/D1 辅助追溯 | **确认** | Vectorize metadata 存短正文，R2/D1 不走线上召回主路径 |
| OQ3 | embedding 模型、维度、metric 怎么定？ | technical | Cloudflare Workers AI `@cf/qwen/qwen3-embedding-0.6b` + 1024 维 + cosine | **确认** | `@cf/baai/bge-m3` 作为 Stage 3 A/B 备选 |
| OQ4 | 全量二十四史 chunk 策略怎么定？ | technical | 500-800 中文字 chunk，80-120 字 overlap，metadata 保留正文和来源 | **确认** | 控制 metadata 大小并保留跨段语义 |
| OQ5 | 线上问答要不要加 rerank？ | technical | 加轻量 rerank：Vectorize topK=20 后取 4-6 个 chunk | **确认** | 使用 Cloudflare Workers AI rerank |
| OQ6 | 三态回答失败策略怎么定？ | technical | 证据不足时答「无关」，不猜「否」 | **确认** | 公平性优先 |
| OQ7 | 子模式 1 入口时机怎么定？ | technical | 第 6 条线索展示后开放，最多 5 问 | **确认** | 与现有求救区状态机一致 |
| OQ8 | 子模式 1 用过海龟汤后的计分折扣怎么定？ | technical | 用过后固定 0 分 | **确认** | 只帮助通关，不参与高分竞争 |
| OQ9 | 子模式 2 轮次和答案次数怎么定？ | technical | 15 问，最终答案错即失败 | **15 问 + 3 次答案提交机会** | 用户修正；错误答案不消耗提问次数 |
| OQ10 | 子模式 2 汤面怎么生成/选取？ | taste ⚠️ | 离线生成 1 条极短隐晦汤面 | **确认，且必须足够隐晦，可以完全不提生平，越短越好** | SPEC 需写硬约束，AI 起草仅占位 |
| OQ11 | 独立海龟汤最终答案判定怎么做？ | technical | 只判是否猜中目标人物，复用现有姓名判定链路，不走 RAG | **确认** | 不要求解释故事 |
| OQ12 | RAG 三态问答是否过滤直接问姓名/别名？ | technical | 不禁止直接猜名，只拦截非 yes/no 问法 | **确认** | 海龟汤允许策略性提问 |
| OQ13 | 非 yes/no 问法怎么处理？ | technical | 返回 invalid，不消耗次数，不进入 RAG/LLM | **确认** | 降成本并保持玩法边界 |
| OQ14 | RAG 问答缓存策略怎么定？ | technical | `figure_id + normalized_question + rag_index_version + prompt_version` 缓存 30 天 | **确认** | 命中不查 Vectorize、不消耗 LLM 预算 |
| OQ15 | 全量二十四史构建方式与语料是否入 git？ | technical | 离线构建；全量语料不入 git | **确认，但语料需要进入 Cloudflare 数据库/存储体系** | 触发 OQ16 细化落点 |
| OQ16 | 语料进入 Cloudflare 的具体落点怎么定？ | technical | R2 存全量原始/清洗语料和构建产物；Vectorize 存线上短正文；D1 存版本/manifest/统计 | **确认** | 不把全量正文塞 D1 |
| OQ17 | Stage 3 原型要验证到什么程度？ | technical | 离线 spike，不做 UI，不接正式游戏流程 | **确认** | 代表人物 + 少量语料 + 三态 prompt + binding 可行性 |

- `technical` = 客观技术决策（栈选、依赖版本、协议、性能预算等），AI 推荐 + 用户拍板即可
- `taste` = 主观偏好（文案、配色、命名风格、视觉调性），AI 推荐**只是占位**，**必须在 SPEC 中显式标注「用户应自己改写」**

## 用户可接受暂时搁置的问题

- [x] embedding 备选模型 `@cf/baai/bge-m3` 的 A/B 结果：Stage 3 根据召回效果决定是否需要切换。
- [x] 全量二十四史完整生产构建的性能和耗时：Stage 5/6 细化分批、断点续跑、预算上限；Stage 3 只做小样本验证。
- [x] 汤面最终文案风格：Stage 4 先写规则，Stage 7 离线生成后再由质量检查或人工抽样看是否够隐晦。

## Stage 3 输入结论

进入 Stage 3 Prototype 时，应验证以下最小闭环：

1. 用 2-3 个代表人物（建议诸葛亮、关羽、苏轼）和少量 Wikisource/profile chunk 模拟全量语料。
2. 封装 Cloudflare Workers AI `@cf/qwen/qwen3-embedding-0.6b`，确认 1024 维向量和 Vectorize cosine index 兼容。
3. 验证 R2 / Vectorize / D1 的目标分工可落地：R2 放语料与构建产物，Vectorize 放短正文 metadata，D1 放版本 manifest。
4. 对至少 15 个问题跑三态 prompt，覆盖「是 / 否 / 无关 / 证据不足 / invalid」。
5. 不做 UI，不接正式游戏流程；Stage 3 只产离线 spike 和结论。

## 外部资料核对记录

- Cloudflare Vectorize：V2 支持 1024 维 cosine index，metadata 每 vector 10KiB，单 index 上限 10,000,000 vectors。参考 [Vectorize limits](https://developers.cloudflare.com/vectorize/platform/limits/)。
- Cloudflare Workers AI：每天 10,000 Neurons 免费额度；`@cf/qwen/qwen3-embedding-0.6b` 和 `@cf/baai/bge-m3` 均为 `$0.012 / 1M input tokens`。参考 [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)。
- Cloudflare Workers AI embedding：`@cf/qwen/qwen3-embedding-0.6b` 为 hosted text embeddings，context window 8192 tokens。参考 [qwen3-embedding-0.6b](https://developers.cloudflare.com/workers-ai/models/qwen3-embedding-0.6b/)。
- Cloudflare AI Search 支持模型表：`@cf/qwen/qwen3-embedding-0.6b` 为 1024 维、4096 input tokens、cosine；`@cf/baai/bge-m3` 为 1024 维、cosine。参考 [supported models](https://developers.cloudflare.com/ai-search/configuration/models/supported-models/)。
- Cloudflare D1：单库 10GB，单行/string/BLOB 2MB。参考 [D1 limits](https://developers.cloudflare.com/d1/platform/limits/)。
