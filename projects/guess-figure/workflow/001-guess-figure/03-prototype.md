# Stage 3 ｜ Prototype 原型

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-3--prototype-原型)
>
> **要点**：解决最大不确定性；最小可运行；用完即弃；**当无真正不确定性时直接跳过**。

## 决定

- [x] **构建原型** — 拆为 2 个 prototype，针对 [Stage 2 grill-me](./02-grill-me.md) 列出的 4 个高危风险中最关键的两个：
  - **Prototype A** — 内容生产 pipeline 端到端 + LLM 加工质量验证（grill-me 风险 1）
  - **Prototype B** — SvelteKit + CF Pages + Function + LLM 调用部署链路（grill-me 风险 4）

## 原型位置

| Prototype | 位置 | 内容 |
|---|---|---|
| A 内容生产 | [`prototype/A-content/`](./prototype/A-content/) | Python 脚本：维基中文 + Wikidata 拉数据 → LLM 加工 7 条线索 + 异称 + 难度标。含 6 模型 benchmark 工具 + 5 人 × 2 模型批量生产工具 |
| B 部署链路 | [`prototype/B-deploy/`](./prototype/B-deploy/) | SvelteKit 5 + `adapter-cloudflare` 项目：固定目标人物诸葛亮、前端输入猜测、`+server.ts` 调云雾 LLM 判断、返回 `{correct, reason}` |

## 验证 / 证伪了什么

### Prototype A：✅ 通过

**核心验证**：维基 + Wikidata 主源 + LLM 加工 → 7 条线索 JSON pipeline 端到端可行；人工审核能拦住事实错误；不同模型质量差异巨大、必须实测选型。

**6 模型 benchmark（单跑诸葛亮）**结果：

| 模型 | 时间 | 成本 | 质量 | 状态 |
|---|---|---|---|---|
| gemini-3.1-flash-lite | 4.2s | $0.00141 | 5/5 | ✅ |
| gpt-5.4-mini | 4.5s | $0.00140 | 5/5（实际有"刘备/三顾茅庐"暴露 false positive）| ⚠️ |
| gpt-5.4-nano | 6.2s | $0.00047 | 5/5（事实有错"齐桓乐毅"应为管仲乐毅）| ⚠️ |
| glm-4.7 | 50.7s | $0.01070 | 4/5（reasoning 风格 R5089 字思考）| ⚠️ |
| gemini-3.5-flash | 33.4s | **$0.11020** | 0/5 content 空（output 7996 token 全浪费）| ❌ |
| deepseek-v4-flash | 148.6s | $0.01702 | 0/5 content 空（reasoning 12111 字突破 max_tokens）| ❌ |

**双模型 5 人物全量（gemini vs deepseek 分工对比）**：

| 模型 | 用途 | 成功率 | 总时间 | 总成本 | 均质量 |
|---|---|---|---|---|---|
| gemini-3.1-flash-lite | 实时对话 | **5/5** | 20.5s | $0.00653 | **4.8/5** |
| deepseek-v4-flash | 内容生成 | 2/5 | **768.5s（12.8 分钟）** | $0.06266（10× 贵）| 2.0/5 |

**核心证伪**：
- **"reasoning model 适合内容生产"假设被推翻**：deepseek-v4-flash 60% 失败率 + 即便成功质量也不优于 gemini（李白难度1 太明显、难度 4 直给《蜀道难》）
- **gemini-3.5-flash 在 strict JSON 任务上不稳定**：output 跑满 8000 token 但 content 空，$0.11 全打水漂

**核心证明**：
- **V1 主模型应用 gemini-3.1-flash-lite**（同时用于内容生产 + 运行时模糊匹配，统一架构最简）
- prompt 加严约束（"难度 1-5 全段禁止异称" / "难度 1 禁标志性事件"）有效，gemini 5 人输出全部规避了之前 deepseek-v4-flash 的"卧龙暴露"问题

### Prototype B：🟡 进行中

**已验证**：
- ✅ SvelteKit 5 + `adapter-cloudflare` 项目骨架建立
- ✅ `pnpm install` + `pnpm dev` 本地启动成功
- ✅ `$env/dynamic/private` 读 .env 工作正常
- ✅ 前端 → `+server.ts` → 云雾 LLM API → 返回 `{correct, reason}` 链路本地通

**待最终验证**（用户的协作步骤）：
- ⏳ `pnpm build` 编译通过（adapter-cloudflare 输出 `.svelte-kit/cloudflare/`）
- ⏳ CF Pages dashboard 创建 project `guess-figure-proto` + 配 env vars + 触发 deploy
- ⏳ 线上 https://guess-figure-proto.pages.dev 测试用例全通过

**踩过的坑（V1 实施时可少走）**：
- pnpm 11+ 把 `package.json` 的 `pnpm` 字段移到了 `pnpm-workspace.yaml`，字段名 `allowBuilds`（不是 `onlyBuiltDependencies`）
- esbuild / sharp / workerd 都需要显式 `allowBuilds: true`
- 本地 dev 不能用 `process.env.YUNWU_API_KEY`，必须用 `$env/dynamic/private`（SvelteKit 标准接口；CF Pages 部署时自动桥接 platform.env）
- 首次 `pnpm dev` 之前 `.svelte-kit/tsconfig.json` 不存在的 warning 可忽略（第二次启动消失）

## 对 SPEC 的影响

| 维度 | grill-me 原决定 | prototype 后修订 |
|---|---|---|
| **LLM 模型** | DeepSeek V3 via 云雾（grill-me 收尾时加的） | **gemini-3.1-flash-lite via 云雾**（prototype A 实测后） |
| **LLM 月成本** | $0.8-1（DeepSeek V3 估算） | 内容生产 $0.07 一次性 + 运行时 ~$3-5/月（修订基于 gemini 实测 token 数）|
| **reasoning model 角色** | 待 prototype 实测 | **彻底剔除**：内容生成 / 运行时都不用 reasoning |
| **prompt 设计** | 草案"难度1不含人名/朝代/作品" | 加严"难度 1-5 全段禁止 aliases / 难度 1 禁标志性事件"已实测有效 |
| **题库 schema** | 基本敲定 | **确认**：`{name, aliases[], clues[7]{text, difficulty 1-7}, source, wikidata_id}` 跑通且 LLM 能严格遵循 |
| **运行时 LLM 调用模式** | 假设直接调 Anthropic / OpenAI | **修订**：走云雾 OpenAI-compatible 代理，CF Pages Function 用 `$env/dynamic/private` 读 env vars |
| **CF Pages 部署根目录** | 未提及 | **明确**：CF Pages dashboard 必须设 Root directory 为 prototype 子目录（多 project 共 1 个仓库的关键配置）|

## 进 Stage 4 SPEC 前的 OQ 收敛

[02-grill-me OQ6](./02-grill-me.md) LLM 模型选型已修订为 gemini-3.1-flash-lite（标 ✅ RESOLVED）。其他 11 个 OQ 留到 Stage 4 SPEC 阶段决定。

**Stage 3 总评判**：✅ V1 架构与关键技术路线可行，进 Stage 4 SPEC。
