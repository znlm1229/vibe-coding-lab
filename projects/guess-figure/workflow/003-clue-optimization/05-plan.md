# Plan: 003 — 线索优化 (pipeline + 内容质量 + 题库扩 70)

> Stage 5。由 `writing-plans` skill 驱动 (v1.2 推荐)。
>
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)
>
> **Plan 阶段定"怎么做、按什么顺序"**;具体 task list 见 [`06-tasks.md`](./06-tasks.md) (Stage 6)。

---

## Approach

**3 步 LLM pipeline 重构** + **数据资产层**(profiles/)+ **质量门户层**(quality_check.py 升级)+ **灰度发布**:

1. **3 步 pipeline**:`generate_figures.py` v2 重写为 `fetch_three_sources → build_profile (强 LLM) → clues_from_profile (flash, banlist+few-shot inject) → judge_clues (flash, d1-5/d6-7 区分) → retry loop N=2`
2. **数据资产**:每个 figure 产 `src/lib/data/profiles/{id}.md` 8 sections 画像入 git,作为 v3+ 内容生产基础
3. **质量门户**:`quality_check.py` 升级 4 项检测(d6/7 alias 子串 + 典故 banlist + 信息密度启发式 + LLM-as-judge),用作"重生成是否值得替换 v1"的自动判据
4. **灰度发布**:5 figure spot check → 50 全量重生成 → 20 新皇帝(总 70)

**关键决策(回顾 Stage 1-3 来源)**:
- 强 LLM 选 `deepseek-v3.2`(prototype 实证质量 ≥ haiku 且成本 1/4) — SPEC OQ1
- 二十四史走 Wikisource + 半自动 mapping table — SPEC OQ + Stage 2 Q3 决议
- d1-3 加难走 guidance + few-shot,非 hard 规则 — Stage 2 Q4 决议(避免 30% failure)
- regression 兜底 = 个体回退 + auto + 人工 review — Stage 2 Q5 决议
- pipeline 文件不重新拆 — 仍单文件 `generate_figures.py`(沿用现有结构,内部加 3 个函数),减少 file 数量,易于审查

**为什么不选 A/B 替代**:
- 不选 fuzzy search Wikisource(命中率风险,Stage 2 Q3 决议)
- 不选全用 hard 规则(failure rate ~30%,Stage 2 Q4 决议)
- 不选整体回退(失去多数真变好的 figure,Stage 2 Q5 决议)
- 不选 claude-haiku 主选(成本贵 4x,prototype 实证 deepseek 同质量)

## Phases

按依赖排序;`(可并行)` 标记并发候选。

### Phase 1 — 准备数据(可并行)

**交付**:
- `scripts/data/history_index.json` — 70 figure 二十四史 mapping(部分 null = fallback)
- `scripts/few_shot_examples.md` — 5 好 + 5 坏对比示例池
- `scripts/data/` 目录入 git

**为什么排这里**:这两份数据是 Phase 3 pipeline 的输入。准备数据先于实现 pipeline,降低实现期间的卡点。

**Phase 1 内任务**(Stage 6 细化):
- T1 史书 mapping 半自动生成(LLM 提案 70 entry,用户 spot check 5-10 个验证准确率)
- T2 few-shot 示例池起草(AI 提案 5 好 + 5 坏,用户审稿)

### Phase 2 — quality_check.py 升级(可并行 Phase 1)

**交付**:
- `quality_check.py` 新增 4 项检测(d6/7 alias 子串 + d1-5 典故 banlist 从 profile extract + 信息密度启发式 + LLM-as-judge `--with-judge` flag)
- `quality_check.test.py` 新增对应 Python 单测

**为什么排这里**:quality_check 是独立模块,与 pipeline 解耦;早做完可同时给 prototype profile + Phase 5/6 输出做质量校验,加速验证循环。

**Phase 2 内任务**:
- T3 d6/7 alias 子串检测 + 单测
- T4 d1-5 典故 banlist 检测(regex 抓 profile section)+ 单测
- T5 信息密度启发式(具体名词数统计)+ 单测
- T6 LLM-as-judge 集成(`--with-judge` flag,接 flash judge)+ 单测

### Phase 3 — generate_figures.py v2 pipeline 重构

**交付**:
- `generate_figures.py` v2:3 步 pipeline + retry loop + cost cap + failed_figures.json
- `generate_figures.test.py` 新增单测(mock LLM)

**为什么排这里**:核心实现,所有后续 phase 的基础。依赖 Phase 1 mapping + Phase 2 quality_check 可调用。

**Phase 3 内任务**:
- T7 实现 `fetch_three_sources`(维基 5K + Wikidata 6 + 二十四史 Wikisource 含 fallback)
- T8 实现 `build_profile`(强 LLM,8 sections validation,thinking model 防御)
- T9 实现 typology/作品 section banlist regex extract(共用函数)
- T10 实现 `clues_from_profile`(banlist inject + few-shot inject + 难度规则)
- T11 实现 `judge_clues`(d1-5 vs d6-7 区分)
- T12 实现 retry loop(N=2,inject 上次违规反馈)+ failed_figures.json
- T13 实现 cost cap(¥10 abort)+ `cost_summary.json` 累积输出

### Phase 4 — 灰度 5 figure spot check

**交付**:
- `figures.v2-candidates.json` 含 5 个灰度 figure(SPEC OQ5: 乾隆/关羽/刘备/李白/苏轼)
- 用户 spot check report

**为什么排这里**:在跑全量前用 5 个不同类型 figure(3 个有问题的 + 2 个本来质量好的)验证 pipeline 端到端 + 难度感受。**这是 GO/NO-GO 决策点 — 失败需回 Phase 3 调整**。

**Phase 4 内任务**:
- T14 跑 5 灰度 figure(deepseek-v3.2 主),产 profiles/*.md + candidates JSON + judge reports
- T15 用户主观 review 5 figure(d1-3 难度感受,8 sections 完整度),GO/NO-GO

### Phase 5 — SPEC v1.0.1 patch(20 皇帝清单)

**交付**:
- `workflow/003-clue-optimization/spec-emperor-list.md` — 20 皇帝候选 + Wikisource mapping
- SPEC 04-spec.md 升级到 v1.0.1
- `history_index.json` 更新加 20 entry

**为什么排这里**:在 Phase 4 灰度 GO 之后做(避免 pipeline 还需大改时白做选名单工作);在 Phase 7 全量跑之前完成(20 皇帝清单是 Phase 7 必要输入)。

**Phase 5 内任务**:
- T16 AI 按 SPEC 原则提 20 皇帝候选名单 + Wikisource mapping
- T17 用户审稿,通过后入 spec-emperor-list.md + history_index.json + SPEC v1.0.1

### Phase 6 — 50 旧 figure 全量重生成 + regen review

**交付**:
- `figures.v2-candidates.json` 含 50 旧 figure 新版
- `scripts/data/regen_diff.md` 自动对比 v1 vs v2 score
- final `figures.json` = 50 个 v1+v2 混合(regression 兜底)
- `figures.v1.json` 保留 baseline 入 git

**为什么排这里**:Phase 4 灰度通过后,信心建立,可跑全 50。需在 Phase 7 跑 20 新之前完成(避免 figures.json 大变动一次性提交)。

**Phase 6 内任务**:
- T18 跑全 50 旧 figure → figures.v2-candidates.json + profiles/*.md × 50
- T19 实现 regen_diff.md 生成脚本(v1 vs v2 score + violations 对比)
- T20 用户 review regen_diff,accept/reject 后产 final figures.json(50 混合)
- T21 旧 figures.json 改名 figures.v1.json + commit baseline

### Phase 7 — 20 新皇帝跑 + 入题库

**交付**:
- `figures.json` 含 70 entry(50 旧混合 + 20 新)
- `profiles/*.md` × 20 新增

**为什么排这里**:50 旧的 review 流程跑通后才跑 20 新(避免 20 新跑出来后又要重 review)。

**Phase 7 内任务**:
- T22 跑 20 新皇帝 → 写入 figures.json final
- T23 quality_check 跑完整 70 figure,确认满分率 ≥ 90%(AC6)

### Phase 8 — 部署 + Stage 7 收尾

**交付**:
- 现有 54 个 vitest 全 pass(npm test)
- `npm run build` 成功
- 推 main 触发 CF Pages auto deploy
- Stage 8 Human QA 入场报告

**为什么排这里**:所有内容产出 + 质量校验通过后,才上线。

**Phase 8 内任务**:
- T24 跑 npm test + npm run build,确认 zero-break(AC12/16/17/18)
- T25 git push 触发 CF Pages deploy
- T26 写 07-implementation.md 入场报告(verification-before-completion skill 跑过)

## Dependencies

```
Phase 1 ─┐
         ├─► Phase 3 ─► Phase 4 ─► Phase 5 ─► Phase 6 ─► Phase 7 ─► Phase 8
Phase 2 ─┘
```

**阻塞并行点**:
- Phase 3 需 Phase 1 (mapping) + Phase 2 (quality_check) 都 OK 才开始(虽然 Phase 1 + 2 内部可并行)
- Phase 5(SPEC v1.0.1)是 hard stop — 用户审 20 皇帝清单前不进 Phase 6
- Phase 6 内 T20 是 hard stop — 用户 review regen_diff 前不进 Phase 7

**触碰共享 / 脆弱代码的点**:
- T18/T22 写 figures.json — 影响 production(CF Pages 直接 deploy)。**操作:先写 figures.v2-candidates.json,确认 review 通过才覆盖 figures.json**
- T21 改名 figures.v1.json — 旧版备份操作,Stage 9 可对比验证;用 `git mv` 保留历史

**外部输入点**:
- T1: Wikisource API(MediaWiki),无 rate limit but cool down 1s 礼貌
- T1/T18/T22: 云雾 LLM API,需 YUNWU_API_KEY(已配)
- T18/T22: 调强 LLM(deepseek-v3.2)+ flash(gemini-3.1-flash-lite)

## Risks

### prototype 已解(无残留风险)

- ✅ 文言文 LLM 处理 — deepseek 实证可消化(引用三国志原文)
- ✅ Wikisource MediaWiki API 接入 — `三國志/卷35` 5000 字成功拉取
- ✅ 8 sections schema 是否可执行 — claude+deepseek 都完整产出 8 sections
- ✅ pipeline 3 步可跑通 — 端到端 < 60s
- ✅ thinking model 防御 — 已加 detect 逻辑

### 残留风险(Plan 期已识别)

| 风险 | 缓解策略 | 影响 phase |
|---|---|---|
| **R1 mapping table 准确率** | LLM 自动生成 + 用户 spot check 5-10 个;不准 figure 走 fallback,不阻塞 | Phase 1 / 3 |
| **R2 非政治人物 8 sections 适用度** | 8 section schema 通用,LLM 自适应(如诗人「关系网」填师友,「典故」填游历/被贬等),Phase 4 灰度抽李白验证 | Phase 4 |
| **R3 20 皇帝 LLM 知识盲区** | AI 提候选时仅选有正史本传的;mapping 准确率不足部分手工补;用户审稿守门 | Phase 5 |
| **R4 50 旧 figure regression** | Phase 6 T19 auto+人工 review,差则保留 v1;最坏退化 0(全保 v1) | Phase 6 |
| **R5 regression review 人工工时膨胀** | regen_diff.md 提供自动判据;用户只 review 自动标"候选采用"的子集(估 ~10-20 个),不是全 50;工时上限 2h | Phase 6 |
| **R6 d1-3 加难效果不足** | Phase 4 灰度抽 5 figure 主观验证;不足则 prompt 加 few-shot(可在 Phase 3 内 iteration) | Phase 4 |
| **R7 LLM 成本失控** | T13 实现 hard cap ¥10 abort;cost_summary.json 实时累积;预估 ~¥4-5,buffer 充足 | Phase 3 / 6 / 7 |
| **R8 deepseek 实际 70 figure 大量退化** | OQ1 备用 claude-haiku-4-5;若 Phase 4 灰度 ≥ 2/5 觉得不如 v1,切 haiku 重跑灰度 | Phase 4 |
| **R9 中文文件名 Windows/git 边缘问题** | prototype 已验证 OK,但 70 个全量可能暴露未知;失败 figure 用 `pinyin(name)` 转写 fallback | Phase 6 / 7 |
| **R10 figures.json schema 不变但 _meta 多了字段** | prototype 实测 _meta 字段不破坏前端 Figure 类型(可选字段);保持兼容 | Phase 8 |

## Test Strategy

### 单元测试覆盖

- **Python 端**(本任务新增):
  - `scripts/tests/test_quality_check.py` — 5 个旧检测项 + 4 个新检测项 + judge mock
  - `scripts/tests/test_generate_figures.py` — fetch_three_sources(mock requests)+ build_profile schema validation + thinking model detection + banlist regex extract + retry loop logic(mock LLM)
- **Frontend 端**(现有,不破坏):
  - `match-exact.test.ts` 9 个 + `auth.test.ts` 12 个 + `hooks.test.ts` 4 个 + `rate-limit.test.ts` 17 个 + `llm-cache.test.ts` 12 个 = **54 个全 pass**

### 集成测试覆盖

- 跑 1 个 figure 真 LLM 端到端 smoke test(Phase 3 末)— 不入 CI(成本),仅本地手跑
- Phase 4 灰度 5 figure 是天然的集成测试(主观 + AI 双通道)

### 留给 Stage 8 Human QA(必须人工)

- **AC2 spot check mapping** — 用户随机抽 5 个 mapping 看 Wikisource page 真存在
- **AC3 20 皇帝候选合理性** — 用户审名单
- **AC4 spot check profile** — 用户开 5 个 profile.md 看 8 sections 完整且符合身份
- **AC11 regression review** — 用户开 regen_diff.md accept/reject
- **AC12 上线后玩 5 局** — 浏览器实测 game 流程
- **AC13/14/15 主观难度感受** — 玩 10 局记 d1-3 vs d4+ vs d6-7 分布
- **AC16 行为兼容性** — 用户上线后玩,确认 5+2 / 计分 / 答错消耗与旧版一致
- **AC17 thinking model 防御** — 故意指定 thinking model,确认报错 exit

### 进入 Stage 8 前的硬关卡

**必须调 `verification-before-completion` skill**(v1.2 强制)核对每个 task 的 "Done when" 都有对应证据。AI 自己说"完成"不算。

## 给 Stage 6 的下一步建议

Stage 6 用 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md) 模板把 Phase 内的 T1-T26 细化成可勾选任务清单,每个 task 标:
- Touches(具体文件)
- Done when(可验证条件)
- Depends on(依赖)

`task-TX:` commit prefix 用于实现 commit;`fix(TX):` 用于 Stage 8 回路修复。
