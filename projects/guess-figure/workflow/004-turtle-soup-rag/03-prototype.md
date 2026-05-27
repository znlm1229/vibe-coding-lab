# Stage 3 ｜ Prototype 原型

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-3--prototype-原型)
>
> **要点**：解决最大不确定性；最小可运行；用完即弃；**当无真正不确定性时直接跳过**。

## 决定

- [ ] **跳过本阶段** — 理由：不适用
- [x] **构建原型** — 解决的不确定性：
  - Cloudflare 账号是否具备 Workers AI / Vectorize / D1 / R2 的基础可用性
  - 500-800 中文字 chunk + 80-120 overlap 是否能形成可喂给 LLM 的证据片段
  - 「目标人物 + 用户问题」隐藏 query expansion 是否是 RAG 必需条件
  - 三态 prompt 在真实 LLM 下是否能稳定输出「是 / 否 / 无关 / invalid」
  - profile + Wikisource 小样本是否足够覆盖海龟汤常见问题

## 原型位置

- 原型脚本：[`proto/turtle_rag_spike.py`](./proto/turtle_rag_spike.py)
- 完整运行报告：[`proto/run-20260527-122741/report.md`](./proto/run-20260527-122741/report.md)
- case 明细：[`proto/run-20260527-122741/cases.json`](./proto/run-20260527-122741/cases.json)
- corpus manifest：[`proto/run-20260527-122741/corpus_manifest.json`](./proto/run-20260527-122741/corpus_manifest.json)

运行命令：

```powershell
python workflow/004-turtle-soup-rag/proto/turtle_rag_spike.py --live-llm
```

辅助 Cloudflare 预检命令：

```powershell
pnpm exec wrangler whoami
pnpm exec wrangler vectorize list
pnpm exec wrangler ai models --json | Select-String -Pattern "qwen3-embedding|bge-m3|bge-reranker"
pnpm exec wrangler d1 list
pnpm exec wrangler r2 bucket list
```

## 验证 / 证伪了什么

### 已验证

1. **Cloudflare 账号权限基本可用**：
   - `wrangler whoami` 成功，账号为 `Liwang529799@gmail.com's Account`
   - Workers AI catalog 中存在 `@cf/qwen/qwen3-embedding-0.6b`、`@cf/baai/bge-m3`、`@cf/baai/bge-reranker-base`
   - Vectorize API 可访问，但当前账号尚未创建任何 index
   - D1 `guess-figure-db` 已存在
2. **R2 是上线前置项**：`wrangler r2 bucket list` 返回 Cloudflare API `code: 10042`，提示需要先在 Dashboard 启用 R2。Stage 4 SPEC / Stage 5 Plan 必须把 R2 enable + bucket 创建列为环境前置条件。
3. **chunk 策略可用**：对诸葛亮、关羽、苏轼三人各取 profile + Wikisource 小样本，共得到 31 个 chunk；500-800 中文字 + 100 字 overlap 形成的证据片段能被 LLM 消化。
4. **三态 prompt 主体可用**：live LLM 跑 15 个 case，14/15 通过；覆盖「是 / 否 / 无关策略 / invalid 不进 RAG」。
5. **invalid 策略可行**：非 yes/no 问法（如「他是谁？」「他有哪些作品？」）在本地校验层直接返回 `invalid`，不消耗 RAG / LLM。
6. **隐藏 query expansion 必须做**：用户问题大量使用「他」，检索 query 必须注入目标人物姓名和别名，否则语义检索没有稳定锚点。

### 已证伪 / 暴露风险

1. **仅 profile + Wikisource 不够**：失败 case 是「关羽是不是被后世尊为武圣？」。profile 只含「关公 / 关帝 / 关圣帝君」等别名，Wikisource 本传也不含后世「武圣」称号，LLM 按规则答「无关」。这证明 Stage 1 的「维基主条目」不能省，后世评价/民间尊号类问题需要维基或更完整 profile 覆盖。
2. **mock embedding 不能代表真实召回质量**：原型用 1024 维 deterministic mock，只验证接口形状与报告链路。Stage 7 必须用真实 Workers AI embedding + Vectorize 做集成验证。
3. **全局召回会混入跨人物证据**：部分 top evidence 来自其他人物 chunk。正式方案必须有 target-aware query expansion、source weighting，并尽量给 profile/wiki 类 chunk 标 `figure_id` 做过滤或 boost；全量二十四史 chunk 则用书名/卷名/人物名匹配做二级加权。
4. **Cloudflare 资源尚未全部准备好**：未创建 Vectorize index，R2 未启用；原型没有创建云资源，避免在 SPEC 前引入外部状态。

## 对 SPEC 的影响

### SPEC 必须新增 / 强化

1. **语料源必须包括维基主条目**：profiles + 全量二十四史之外，维基 chunk 是后世评价、尊号、文化影响类问题的关键补充。
2. **RAG query 必须注入隐藏目标信息**：`目标人物 name + aliases + 用户问题`，用户不可见，但用于检索和三态判断。
3. **metadata 字段要支持 target-aware boost**：
   - `source_type`: `profile | wikipedia | wikisource | figure_clue | ...`
   - `figure_id`: profile/wiki/figure_clue 必填；全量史料可为空或后处理抽取
   - `book / volume / page / offset / chunk_hash / corpus_version`
4. **召回策略要写成两段**：Vectorize topK=20 后 rerank；最终 4-6 个 chunk 喂 LLM；同人物 profile/wiki chunk 应优先 boost，避免同朝代串线。
5. **Cloudflare 环境前置条件**：
   - 创建 Vectorize V2 index：1024 dimensions + cosine
   - 启用 R2 并创建语料 bucket
   - D1 新增 corpus manifest / build manifest 表
   - wrangler v3.114.17 可用但已过期，Plan 阶段决定是否升级到 wrangler 4
6. **验收标准要区分 mock 与真实链路**：Stage 3 mock 通过不等于生产 RAG 通过；Stage 7 AC 必须包含真实 Workers AI embedding + Vectorize 查询 + rerank + LLM 的端到端检查。
7. **三态规则保持**：证据不足答「无关」是正确行为，不为了提高 case pass 率改成猜测；失败 case 应通过补语料解决，而不是放宽 LLM 规则。

### 可继续沿用的决策

- Cloudflare Workers AI `@cf/qwen/qwen3-embedding-0.6b` + 1024 维 + cosine 作为主线。
- `@cf/baai/bge-m3` 保留为召回效果不佳时的 A/B 备选。
- 非 yes/no 问法 invalid，不消耗次数，不进 RAG / LLM。
- Stage 4 SPEC 可基于 14/15 prototype 结果继续推进，但要把唯一失败转化为语料覆盖 AC。
