# Stage 1 ｜ Brainstorm 头脑风暴

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-1--brainstorm-头脑风暴)
>
> **要点**：发散 3–5 个方向；每个配一句核心思路 + 一句主要权衡；**不评判出胜者**（由用户决定）。
>
> 本文件用 `brainstorming` skill 驱动（2026-05-25）。

---

## 任务

用户原话：**「开始第三个需求,优化线索」**。

经 brainstorming skill 引导 4 轮收敛后，明确为以下两个动作的合集：

1. **重生成现有 50 个 figure 的 7 条线索**（用升级后的内容生产 pipeline）
2. **新增 20 个皇帝**（同样走新 pipeline），合计 70 个 figure

**显式不动**：游戏机制（5 标准 + 2 求救）、`src/routes/` 前端、`src/lib/game-state.svelte.ts`、wrangler.toml / D1 schema / KV 配置。

---

## 现状速读（探索结论）

> 数据来自 `src/lib/data/figures.json` + `scripts/generate_figures.py` + `scripts/quality_check.py` + `src/routes/play/+page.svelte` + `src/lib/game-state.svelte.ts`。

- **数据结构**：每人 7 条 `Clue { text, difficulty }`，难度 1（最难）→ 5（标准最易）→ 6-7（求救）。50 人。
- **生产**：单步 LLM（gemini-3.1-flash-lite via 云雾），材料只用 **维基中文摘要 1000 字 + Wikidata 6 个字段**（label/aliases/description/birth/death）；prompt 规则简单（1-5 段不出 aliases、d1 不出朝代、6-7 不出本名）；temperature 0.3。
- **质量校验**：`quality_check.py` 5 项检查，全部字符级（aliases 数 / clues 数 / 难度齐 / 1-5 不含 aliases 整字 / d1 不含朝代名整字）。**不查语义**。
- **游戏机制**：初始展示 1 条；玩家可主动「再来一条」或答错自动消耗；标准范围 (6-N)*20 分，求救范围最高 10 分。

### 真实痛点样例（从现 figures.json 抽样发现）

| 人物 | 难度 | 文本（节选） | 问题 |
|---|---|---|---|
| 乾隆 | d1 | "暮年自诩拥有**十项武功**" | 语义穿底 ≈ alias「十全老人」（字符级 grep 抓不到） |
| 乾隆 | d5 | "清朝入关后的第四位统治者，实际掌权时间最长" | 比 d1 还容易猜（**梯度乱序**） |
| 关羽 | d7 | "**字云长**，河东解人" | 子串包含 alias「关云长」的关键字（d6/d7 prompt 没禁子串） |
| 刘备 | d7 | "**谥号为昭烈，庙号烈祖**" | 直接给出 aliases「汉昭烈帝/昭烈皇帝/烈祖」 |
| 刘备 | d2 | "以**织席贩履**为业，与两位**结义兄弟**" | 标志性事件穿底（d2 应远离） |

---

## 方向（3 个发散）

### A — 仅 Quality Gate 守门（轻）

- **核心思路**：不改 prompt、不重生成；只升级 `quality_check.py` 加更多检测项（d6/d7 alias 子串、d1-5 强暴露事件 banlist、用 LLM-as-judge 二次审语义穿底）；违规条目**人工修补** figures.json。
- **主要权衡**：1-2 天即可完成、0 LLM 成本；但治标不治本 — 下一个新增 figure 仍走老 prompt 复发同 bug；手工修补品质参差。

### B — prompt + 校验 双升级 + 重生成（中）

- **核心思路**：升级 prompt（加 few-shot 好/坏对比、每难度必做必避清单、d1 信息密度限制、d6/d7 禁 alias 子串）+ 升级 quality_check（A 的所有检测项）+ 输入侧轻度扩材料（维基 1000→3000 字）+ 全 50 figure 重生成；旧 figures.json 保留做 baseline。
- **主要权衡**：3-5 天，LLM 成本 < ¥0.5，无新依赖；但 prompt 改动可能引入新风格漂移，需要小批量灰度。

### C — 多源知识库 + few-shot pool + 自动 judge 循环（重）

- **核心思路**：在 B 之上 — 输入侧接多源知识库（百度百科 / 二十四史 / CN-DBpedia 等）、维护好/坏 few-shot 示例池、生成后自动 LLM-as-judge 评分循环（不合规自动重生成）。
- **主要权衡**：1-2 周，LLM 成本 ¥1-5；数据源整合复杂（反爬 / 编码 / corpus 处理）；pipeline 维护成本上升；但能根本性提升内容质量。

---

## 用户收敛 → M 方案 v3

用户经 2 轮调整选定：**B + C 的增强版**（删 C 的「自动 judge 循环」？ → 用户回正：保留 → 又加 3 项调整）：

- **+ 二十四史进库**（C 选中维基 + Wikidata + 二十四史 三源）
- **+ d1/d2/d3 显著加难**（"特别是前面三个问题"）
- **+ 引入"人物画像"中间层**（先全面凝结画像，再从画像产线索）
- **+ 新增 20 个皇帝**（题库 50 → 70，部分吃掉候选 006 的 scope）

### v3 完整内容

#### 1. 改 prompt（`scripts/generate_figures.py` 的 `PROMPT_TEMPLATE`）

- 加 **few-shot 好/坏对比示例**（从 pool 文件读入，默认塞最有代表性的 2 对）
- 每难度的「必做 / 必避」清单显式列：
  - **d1**：只能引用画像「反差 / 鲜为人知点」section 的 1-2 条；禁触画像「典故 / 作品 / 标志事件」section 任何字眼；禁朝代名；禁 alias 字符；≤ 3 个具体名词
  - **d2**：可触历史评价的最抽象描述；禁触「典故 / 作品」section；禁 alias 字符
  - **d3**：可触「关系网」抽象描述；禁触「典故 / 作品」section；禁 alias 字符
  - **d4-5**：可间接指代作品 / 典故；仍禁 alias 字符
  - **d6**：明确禁 alias **子串**（不只是整字），允许朝代 / 作品名
  - **d7**：同 d6，且禁「字 / 号 / 谥号 / 庙号」等关键字 + alias 字符
- temperature 实验值（SPEC 阶段定）

#### 2. 输入侧扩材料（`fetch_material` 升级）

- **维基中文全文**：从 `page.summary[:1000]` → `page.text` 核心 sections（生平 / 政治 / 作品 / 评价 / 影响，过滤参考与导航），~3000-5000 字
- **Wikidata 字段补全**：6 → ~15 字段（加 P106 职业、P27 国籍、P39 就职、P26 配偶、P40 子女、P22/P25 父母、P140 信仰、P166 受奖、P800 著名作品、P509 死因 等）
- **二十四史选段**（新）：
  - 来源：Wikisource 中文版（无本地下载 GB 级 corpus）
  - 检索：Wikidata P800 → Wikisource 搜「{name}传 / 本纪 / 世家 / 列传」→ 前 3 匹配取正文 ≤ 5000 字
  - 容错（**点 2A**）：拉不到记 warning，figure 照常生成（兜底用维基 + Wikidata）

#### 3. 新增中间层：人物画像 profile（**v3 核心 architectural shift**）

- 生产 pipeline 从 1 步 LLM 改为 **2 步 LLM**：
  - call #1 `build_profile`：（维基全文 + Wikidata + 二十四史选段）→ 结构化 markdown 画像
  - call #2 `clues_from_profile`：（画像 + few-shot pool + 难度规则）→ 7 条 clues
- **画像入 git**（**点 1A**）：存 `src/lib/data/profiles/{id}.md` × 70
- **画像结构（默认，SPEC 可调）**：

  ```markdown
  # {name}

  ## 基本信息
  - 字 / 号 / 谥号 / 庙号 / 别号
  - 生卒年 / 朝代区间 / 籍贯
  - 主要职业 / 身份

  ## 主要事迹  (5-10 件，按时间序，标重要程度)
  ## 性格 / 风格特征  (2-4 条)
  ## 典故 / 标志事件  (3-5 个 — 自动成为 d1-5 banlist)
  ## 关键作品  (3-5 个)
  ## 关系网  (老师 / 同辈 / 弟子 / 政敌 / 家人)
  ## 历史评价  (正面 / 负面 / 后世神话)
  ## 反差 / 鲜为人知点  (1-3 个 — d1 必用源)
  ```

- **副产品**：画像「典故」section 自动作为 d1-5 banlist（取代 v1 v2 设想的手维护 `event_banlist.json`）；「反差」section 自动作为 d1 来源

#### 4. few-shot pool（新文件 `scripts/few_shot_examples.md`）

- 初始 **5 好 + 5 坏**（**SPEC 阶段确定具体内容，初版由 AI 提案，用户审稿**）
- 好示例：从现有 50 figure 中挑梯度最自然、d1 最有"谜面感"的 5 条
- 坏示例：用真实观察到的反例（乾隆 d1 / 关羽 d7 / 刘备 d7 / 刘备 d2 / 乾隆 d5 梯度乱序）
- 文件结构：markdown，每条带「问题分类 / 反面文本 / 改进文本 / 一行解说」，可逐步增长

#### 5. quality_check 升级（`scripts/quality_check.py`）

**规则项新增**：

- (a) d6/d7 alias **子串**检测（现有只查整字）
- (b) d1-5 不触画像「典故」section 任何字眼（取代手维护 banlist）
- (c) 难度 ≥ 2 的「信息密度」启发式：统计每条 clue 的"具体名词数"（年号 / 地名 / 书名 / 事件名），要求难度越低密度越低（梯度反转 → 报警）

**LLM-as-judge 项**（新增第 6 项，`--with-judge` flag）：

- 每条 clue 用 judge LLM 打「合规 / 可疑 / 违规」标签
- judge prompt：输入（画像 + 7 条 clue + aliases + 标志事件）→ 输出（每条 verdict + 理由）

#### 6. 自动 judge 循环（生成阶段内嵌）

- 单 figure 生成后立刻跑 judge
- 任意 clue 标「违规」→ 回 call #2 重新调 LLM（prompt inject 上次的违规反馈作为 negative example）
- 最多重试 N 次（**SPEC 阶段定，推荐 N=2**）
- 仍违规 → 标 failed 写入 failed report，不阻塞批处理

#### 7. 重生成 + 新增策略

- **20 皇帝候选清单**：**SPEC 阶段定**，由 AI 提候选，用户审。原则：
  - 排除现有 50 figure 已收录的皇帝
  - 朝代覆盖均衡（每个主要朝代 1-3 个）
  - 优先有完整二十四史本传的（便于走新 pipeline 三源材料）
  - 知名度 tier 1-2（小学 / 初中历史课能见到）
- **分批灰度**：
  1. 先跑灰度 5 个旧（从现 figures.json 最有问题的选，如乾隆 / 关羽 / 刘备 + 随机 2 个）
  2. 人工 spot check，5 个都觉得"明显比旧版好" → 跑全量旧 50
  3. 再跑新增 20 皇帝
- 旧 `figures.json` 重命名为 `figures.v1.json` 留 baseline
- 新版直接覆盖 `figures.json`，部署时 CF Pages 自动 deploy

#### 8. 范围 / 不动什么

- 只动 `scripts/` + `src/lib/data/figures.json` + `src/lib/data/profiles/`
- **不动** `src/routes/`、`src/lib/game-state.svelte.ts`、`src/lib/types.ts`（schema 不变）、`wrangler.toml`、D1 schema

#### 9. 预估盘子（v3）

| 维度 | v3 估算 |
|---|---|
| 工时 | ~1.5-2 周（pipeline 重构 + 二十四史接入 + 20 皇帝选择 + 灰度调校） |
| LLM 成本 | ~¥4-10（70 figure × 2 步 LLM + judge × 70×7 + N 次重试） |
| 新依赖 | 仅 `mwclient`（或 `requests` 调 MediaWiki API；轻） |
| 数据资产新增 | 70 个 profiles/*.md 入 repo（~200KB-2MB） |
| 删除项 | 不再需手维护 `event_banlist.json`（画像「典故」section 替代） |

#### 10. 成功标准（初版，SPEC 阶段精化）

- **量化**：升级后 quality_check（6 项 + judge）在新 figures.json 上**满分率 ≥ 90%**（70 个里 ≥ 63 个满分）
- **定性 1**：用户随机抽 10 个 figure 人工 spot check，主观觉得 **≥ 8 个**"梯度合理、不穿底"
- **定性 2**：用户上线实测玩 10 局，**< 2 局**出现"线索 1 就秒猜"或"线索 5 还摸不到边"
- **定性 3**（前 3 难度加难专项）：用户玩 10 局中 ≥ 7 局**需要打开 d4 或以上**才猜出（验证 d1-3 真的变难，但**不能** ≥ 8 局靠 d6-7 救命，那是过难）

---

## 给 Stage 2 Grill Me 的下一步建议

`grill-me` skill 在 Stage 2 会拷问决策树。预期重点拷问的几个高风险分支：

1. **画像结构是否覆盖所有人物类型** — 现 50 个里有诗人 / 词人 / 画家 / 工匠 / 僧侣 / 军事家 / 哲人 / 皇帝多种身份，统一 8-section 模板是否对非政治人物 awkward？是否需 specialize（如「文学派」画像加「文学风格」「代表作分析」section）？
2. **二十四史 fallback 影响面** — 估计 50 个里有多少诗人 / 工匠 / 僧侣在二十四史里无本传？若超过 40% 就意味着"二十四史进库" 实际只覆盖少数 figure，方案 ROI 要重新评估。
3. **d1/d2/d3 加难的过难阈值** — 成功标准定性 3 写"< 2 局 d1-3 猜出"，这阈值合理吗？过严会让游戏从"猜谜"变成"看故事"？
4. **自动 judge 循环重试 N 次仍失败的处理** — 标 failed 阻塞？用旧版兜底？用 N+1 次手动救火？影响最终 figure 数量保证。
5. **重生成 50 个旧 figure 的 regression 风险** — 新版可能某些 figure 反不如旧版（如李白 / 苏轼这种诗人，旧版梯度本来就好）。是否需要逐人 A/B 对比并允许"按 figure 回退"？
6. **profile 入 git 对 CF Pages 包大小的影响** — 70 个 .md 约 200KB-2MB，加现有 figures.json + 题库 V2 扩 200 人后是否撑爆 free plan 限制？
7. **20 皇帝候选清单的具体原则细化** — "朝代覆盖均衡"每朝代几个？"知名度 tier 1-2"谁来打分？SPEC 阶段要把这个定死。
8. **few-shot pool 持续维护机制** — 生产中遇到新坏例怎么入 pool？是否需要 ergonomic 工具（如 `python scripts/add_bad_example.py --figure 苏轼 --clue-d 3 --reason ...`）？
9. **LLM 成本上限保护** — 估算 ¥4-10 是 happy path；最坏情况（每个都重试 N=2 次 + judge 全跑）是否超 ¥20？需 SPEC 加 budget hard cap（参考 002 的 LLM 成本兜底）。
10. **测试策略** — 新 pipeline 的单元测试用 mock LLM？还是只 e2e 跑 1-2 个 figure？画像生成的"质量"如何自动化测？

具体哪些拷问入 SPEC 的 Open Questions 由 `grill-me` skill 在 Stage 2 决定。
