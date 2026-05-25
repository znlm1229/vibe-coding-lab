# Stage 2 ｜ Grill Me 质询拷问

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-2--grill-me-质询拷问)
>
> **强制工具**：调用 `grill-me` skill 驱动本阶段（v1.1+）。

---

## Skill 调用记录

- **Skill**：`grill-me`
- **调用时间**：2026-05-25
- **交互轮数**：5 轮(Q1-Q5)
- **覆盖的关键决策分支**：
  - 二十四史文言文进 LLM 的处理方式(Q1)
  - 强 LLM 在 pipeline 里的角色范围(Q2)
  - 二十四史检索机制(Q3)
  - d1/d2/d3 加难规则的实施风格(Q4)
  - 重生成的 regression 兜底策略(Q5)
- **被搁置的分支与理由**：
  - 强 LLM 具体型号 — 留 Stage 3 Prototype 用实测决定(标 OQ1)
  - 20 皇帝具体候选清单 — 留 SPEC 阶段(AI 提案 → 用户审,标 OQ4)
  - judge 模型选择 — 默认 flash-lite 自审,SPEC 阶段确认(标 OQ2)
  - 重试 N 值具体数 — 默认 N=2,SPEC 阶段定(标 OQ3)
  - 测试策略 — 留 Stage 5/6 Plan/Tasks 阶段
  - 灰度 5 个具体清单 — 留 SPEC 阶段(标 OQ5)
- **pipeline 复杂度变更**:Q1-Q5 决策后,LLM call 数量从 brainstorm 的 2 步 → 实际 3 步(强 LLM profile + flash clue + flash judge),成本估算从 ¥4-10 **修正到 ¥12-15**(brainstorm.md §9 第 8 节已知需后续 patch)

---

## 拷问对象

来自 Stage 1 的 M 方案 v3:
- 输入侧三源(维基中文全文 + Wikidata 15 字段 + 二十四史选段)
- 画像中间层(profile.md 入 git)
- d1/d2/d3 显著加难
- prompt + quality_check 升级 + LLM-as-judge 自动循环
- 重生成 50 旧 figure + 新增 20 皇帝(共 70)

---

## Grill 决议(Q1-Q5)

### Q1 — 文言文进 LLM 的处理方式

| 候选 | 用户选择 | 理由 |
|---|---|---|
| A. 直接喂文言文(flash-lite 读) | ❌ | gemini lite 文言能力不足风险高 |
| B. 加翻译预处理 LLM call | ❌ | 翻译有损,3 步 LLM 成本上升 |
| **C. 用更强的 LLM 单独处理二十四史** | ✅ | 质量上来 + 成本可控(仅一步用贵型号) |

### Q2 — 强 LLM 在 pipeline 里负责哪一步

| 候选 | 用户选择 | 理由 |
|---|---|---|
| A. 只翻译文言文 | ❌ | 比 B 多一步 LLM call,无独家收益 |
| **B. 直接产 profile** | ✅ | 把"读懂文言+合成画像"合并;clue 生成是 mechanical 用 flash 够 |
| C. profile + clue 都用强 | ❌ | 成本 × 1.5 倍,clue 不需要强 |
| D. 全管道用强 | ❌ | 成本 × 4-5 倍,过度 |

### Q3 — 二十四史检索机制

| 候选 | 用户选择 | 理由 |
|---|---|---|
| A. Wikisource fuzzy search | ❌ | 命中错风险高,合传无法 extract |
| B. 严格指 24 史(不含清史稿) | (sub-decision)默认 + 清史稿 | 否则乾隆/康熙/曾国藩等清朝人物全 fallback |
| **C. 半自动 mapping table** | ✅ | LLM 生成初版 + 人工 spot check,确定性查找 |
| D. 跳过原文,LLM 用自带知识 | ❌ | 与"二十四史进库"初衷矛盾,LLM 幻觉难控 |

Sub-decisions in Q3:
- 范围 = 24 史 + 清史稿(25 史)
- mapping 生成 = Stage 3 Prototype 期间 LLM 一次性产 70 figure 的初版 + 用户 spot check 5-10 个验证准确率
- 无传 figure(鲁迅/孙中山/可能李清照) → 设 mapping null,fetch 时走"仅维基 + Wikidata"分支

### Q4 — d1/d2/d3 加难规则风格

| 候选 | 用户选择 | 理由 |
|---|---|---|
| A. 严格 hard 规则(brainstorm 默认 5 条) | ❌ | 估算 ~30% failure rate,人工救火工时大 |
| B. 严格规则 + d1-3 单独用强 LLM | ❌ | 成本 ×1.5,引入新 pipeline 步骤 |
| C. 柔性 guidance 全走 | ❌ | 防穿底也靠 LLM 自觉,不稳 |
| **D. 折中** | ✅ | 保 deterministic 防穿底 hard 规则 + 软规则 + few-shot |

折中 D 的具体规则:
- **保留 hard 规则**(deterministic 可 grep):
  - alias 字符整字 + 子串禁(d1-d7 全段)
  - 画像「典故 / 标志事件 / 关键作品」section 词禁(d1-d5)
  - 朝代名禁(d1)
- **去掉**:"≤ 3 个具体名词" 这种 LLM 难自检的量化规则
- **改用 prompt guidance + few-shot 示范**(锚定输出形态):
  - d1 prompt 写:"让普通人脱离朝代/作品/典故的提示后,只能凭隐晦的反差细节去猜"
  - few-shot:乾隆 d1「暮年自诩拥有十项武功」(坏 — ≈ 十全老人语义穿底) vs 改进示例
- **风险**:guidance 路线"加难"幅度可能不如 hard 规则明显;**Stage 3 Prototype 拿 5 figure 实测,若主观感觉不够难再补加 hard 规则**

### Q5 — Regression 兜底策略

| 候选 | 用户选择 | 理由 |
|---|---|---|
| A. 整体回退(任一坏全退) | ❌ | 错过大多数真的变好的 |
| **B. 个体回退 + auto + 人工** | ✅ | quality_check 自动过滤 + 抽样 review,figures.json 是 v1+v2 混合 |
| C. 全护稿你 review 50 个 | ❌ | 工时 ~4 小时太大 |
| D. 全用新版接受 regression | ❌ | 可能上线不如旧版 |

具体流程:
1. 新 pipeline 跑完 50 旧 figure → `figures.v2-candidates.json`
2. quality_check 对 v1/v2 各跑一遍 → `scripts/regen_diff.md`(逐 figure 双版本得分 + 违规项对比)
3. 自动决策:`v2_score >= v1_score` 且 `v2_violations <= v1_violations` → 标"候选采用"
4. 用户 review "候选采用"的子集(~1-1.5 小时),accept/reject 后产 final `figures.json`(v1+v2 混合)

---

## 高危风险(已在 Q1-Q5 中解决)

- ✅ 二十四史无传 figure 的 fallback 处理 — Q3 sub-decision:无传走"仅维基+Wikidata"分支
- ✅ d1 加难规则的 LLM 可执行性 — Q4 决议 D 折中,软规则避免 30% failure rate
- ✅ Regression: 新版反不如旧版 — Q5 决议 B 个体回退,figures.json v1+v2 混合
- ⚠️ 文言文 LLM 处理质量 — Q1+Q2 决议用更强 LLM 产 profile,**但具体型号 OQ1 待 Stage 3 Prototype 验证**

## 中危风险(可暂缓但要承担)

- **Pipeline 复杂度上升**:2 步 LLM → 3 步(强 profile + flash clue + flash judge),`generate_figures.py` 结构需要重新设计
- **成本估算修正**:¥4-10 → **¥12-15**(主要在 70 figure × 强 LLM profile call ~¥0.175 each ≈ ¥12)。绝对值仍可控,无需 budget hard cap
- **数据资产新增**:`src/lib/data/profiles/*.md` × 70 入 git,~700KB-2MB,deploy 包大小可接受(远低于 CF Pages 限制)
- **judge 循环失败处理**:N=2 重试仍失败的 figure 默认标 failed 不入 figures.json(可能 70→65-68 个);**人工补救工时未估**,SPEC 阶段需定流程

## 低危 / 已知妥协

- 强 LLM API 依赖云雾中转支持 claude-haiku/gemini-pro 等型号 — Prototype 阶段需验证(若云雾不支持就换直连)
- profile 8 sections 对非政治人物(诗人/词人/僧侣 共 22 个 = 44%)可能略 awkward — LLM 自适应解决,不需要 specialize
- 二十四史范围扩到 25 史(+清史稿)— 默认接受
- profiles/*.md 用中文文件名 `profiles/诸葛亮.md` — Windows/Git 处理中文文件名可能有边角问题,Stage 3 Prototype 验证

---

## 待用户回答的开放问题(OQ) — 喂给 Stage 4 SPEC

| # | 问题 | 类型 | AI 推荐 | 决定 | 备注 |
|---|---|---|---|---|---|
| OQ1 | 强 LLM 具体型号 | technical | claude-haiku-4-5(Anthropic 系对古汉语理解被广泛好评) | (Stage 3 决定) | Prototype 阶段实测 2-3 个候选(haiku / gemini-3.1-pro / 其他云雾支持型号),选 profile 质量 / 成本最优 |
| OQ2 | judge 用哪个模型 | technical | gemini-3.1-flash-lite(自审) | (待) | flash 自审成本最低;若 prototype 发现 judge 误判率 > 15% 再考虑用强 LLM 二审 |
| OQ3 | 自动 judge 循环最多重试 N | technical | N=2 | (待) | N 太低 → 高 failure;N 太高 → 成本 × N。SPEC 拍 |
| OQ4 | 20 皇帝具体候选清单 | taste ⚠️ | (SPEC 阶段 AI 按原则提案 70 候选) | (待) | 原则:排除现有 50 已有皇帝、朝代覆盖均衡(每朝代 1-3)、优先有完整二十四史本传、知名度 tier 1-2(小/初中历史课能见)。**用户应自己审稿,AI 提案仅占位** |
| OQ5 | 灰度先跑哪 5 个 figure | taste ⚠️ | 乾隆 / 关羽 / 刘备 / 李白 / 苏轼(3 个有问题的 + 2 个本来好的诗人) | (待) | 既要验证"防穿底"修复,也要验证"不 regress 已经好的"。**用户可改单子** |
| OQ6 | LLM 调用 N 次仍失败的 figure 处理 | technical | 标 failed,写入 failed.json,不入 figures.json;人工兜底(直接编辑旧版 figure 进 figures.json) | (待) | 70 figure 里估算 < 5 个会 fail |
| OQ7 | CF Pages 部署: 旧 figures.v1.json 是否一起 deploy | technical | 否,仅 deploy 新版;v1 留作 git 历史 baseline | (待) | 减少部署体积,无需在线 toggle |
| OQ8 | profile 文件命名 | technical | `profiles/{id}.md`(id 当前规则 = name.lower().replace(" ", "-"),中文人物 id = 中文) | (待) | Prototype 验证 Windows / git 中文文件名兼容性 |
| OQ9 | 二十四史拉取上限字数(每 figure) | technical | 5000 字(超过则截取最前 + 论赞结尾) | (待) | 文言 5000 字 ≈ 现代汉语 ~15000 字 ≈ 5K-8K tokens,context window 不紧 |
| OQ10 | profile 中「典故」 section 作为 banlist 的 extract 算法 | technical | regex 抓 `^## 典故 / 标志事件\n((?:- .*\n)+)`,split 每行 `- ` 后的内容作为 banlist 词 | (待) | quality_check 升级时实现 |
| OQ11 | profile schema 是否要带 yaml frontmatter | technical | 否,纯 markdown 8 sections;若后续需要程序级 metadata 再加 frontmatter | (待) | 减少 schema 维护 |
| OQ12 | few-shot pool 文件位置与初版内容 | taste ⚠️ | `scripts/few_shot_examples.md`,5 好(从现 figure 选)+ 5 坏(用真实观察反例);AI 提案,用户审稿 | (待) | 内容主观,AI 仅占位 |

---

## 用户可接受暂时搁置的问题

- 暂无 — 所有 unknowns 已进 OQ 或已 grill 决议

---

## 给 Stage 3 Prototype 的下一步建议

Prototype 主任务:**用 1-3 个 figure 验证新 pipeline 端到端可跑通,且产物质量上来**。

建议 prototype 验证清单:
1. **诸葛亮**作为主验证 case(三国志卷 35 有完整本传,材料充足)
2. 验证强 LLM 候选 2-3 个(haiku-4-5 / gemini-3.1-pro / 其他云雾型号),用相同 input 比较 profile 质量
3. 验证 mapping table LLM 自动生成可行性(让 LLM 输出 70 figure 的初版 mapping,人工 spot check 5 个验证)
4. 验证 profile → clue 的 d1 加难 guidance 风格效果(给 5 个不同人物类型测)
5. 验证 judge 循环单次 + 重试 1 次的成功率
6. 实测一个 figure 端到端成本(强 LLM profile + flash clue + flash judge,真实云雾计费),校准 ¥12-15 估算

OQ1 + OQ8 + Q1+Q2 的二十四史文言文处理质量 → Prototype 后能给定论。
