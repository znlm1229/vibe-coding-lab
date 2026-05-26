---
title: "给猜历史人物重做线索生产 pipeline — 003 任务复盘"
description: "guess-figure V3:用九步工作流重构 3 步 LLM 内容生产 pipeline + 题库 50→65。复盘 6 个 production iteration 的隐性陷阱:gemini-2.5-pro thinking model 不输出 content、profile aliases 11+ 让 d6/d7 几乎不可避免穿底、Wikisource mapping 中文数字 vs 阿拉伯数字、LLM judge 跟 deterministic check 标准不一致、regression v1+v2 混合兜底机制、65/70 偏差用户中途多次 explicit accept。"
pubDatetime: 2026-05-26T18:30:00+08:00
author: "李旺"
tags: ["vibe-coding", "workflow", "retrospective", "llm", "deepseek", "prompt-engineering", "content-pipeline", "retrospective"]
featured: true
---

[guess-figure V2](/posts/guess-figure-002-account-rate-limit/) 上线一周后我意识到:题库 50 个人物 × 7 条线索的**内容质量本身**是天花板。游戏好不好玩,核心不在 5+2 求救机制,在每条 clue 是否真有"谜面感"—— d1 不能等同于"乾隆有十全武功"(语义穿底 alias「十全老人」)、d6/d7 也不能直接给"字云长"(子串穿底 alias「关云长」)。

V3(003 任务)就是为内容质量做的阶跃 —— **3 步 LLM pipeline 重构 + 题库 50→65 + quality_check 4 项升级**。从 Stage 1 Brainstorm 到 Stage 9 用户验收**单工作日推完**,18 AC 中 15 PASS + 3 偏差用户 explicit accept,123 测全 pass,总 LLM 成本 ¥2.61。本文记录 6 个 production iteration 的隐性陷阱 —— 都不在 SPEC 字面里,都不在事前知识里,全是 prompt 迭代和 LLM 行为踩出来的。

> 如果你不知道九步工作流是什么,先看 [Hello — 用九步工作流搭这个网站](/posts/hello-and-the-nine-stages/)。或者 [V1 复盘](/posts/guess-figure-retrospective/) / [V2 复盘](/posts/guess-figure-002-account-rate-limit/)。

## 这次做的:3 件事

1. **3 步 LLM pipeline 重构**:把原来的"单步 LLM 直接产 7 条 clue"改成
   - **(强 LLM) 三源材料 → 8-section 结构化人物画像**(`profiles/{id}.md` 入 git,数据资产)
   - **(flash LLM) 画像 + banlist + few-shot → 7 条 clues**
   - **(flash LLM) judge 7 条 clues → 合规/可疑/违规 → 不合规自动重试 N=2**
2. **题库 50→65**:重生成 50 旧 figure(31 个 v2 采用 + 14 个 v2 fail 保留 v1 + 5 个 v2 不如 v1 保留 v1)+ 新增 15 个皇帝(20 候选里 5 个 hard case 失败,见后)。完整 [项目集 entry](/projects/guess-figure/) 含 V3 section。
3. **quality_check.py 升级 4 项**:d1-5 不含 aliases ≥3 字子串 / d1-5 不含 profile typology banlist / 信息密度梯度启发式 / LLM-as-judge (`--with-judge` flag)。最终 65 figure **62 满分 = 95.4%**(SPEC AC6 90% 阈值过)。

输入侧三源材料:**维基中文全文 5000 字**(原 1000 字摘要)+ **Wikidata 6 字段**(沿用 V1)+ **二十四史 Wikisource 选段 5000 字**(新接入,按 history_index.json mapping)。

最终架构:`scripts/generate_figures.py` v2 600+ 行,3 个独立函数 + retry loop + cost cap (¥10 hard cap);`scripts/quality_check.py` 8 项规则 + judge optional;`src/lib/data/profiles/*.md` × 69 个 8-section markdown 入 git。

完整 [项目集 entry](/projects/guess-figure/) | [上线 URL](https://guess-figure.pages.dev) | [源码](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure)

## 工作流验证的赢点

### 1. brainstorming 收敛 4 轮 → 用户引入"个人画像"中间层

Stage 1 我 propose 3 方向(A 仅 quality gate / B 双升级重生成 / C 多源知识库 + judge 循环),用户选 B+C 增强版。**关键转折**:用户在第 3 轮追问中提了"**每个历史人物会有一个个人画像,再全面的凝结出线索**"—— 这是 v3 architectural 核心,**1 步 LLM** 变成 **2 步**(后来 + judge 变 3 步)。

这是 brainstorming skill 的设计意图 —— 不让 AI 锚定第一个方向。AI 推荐的 B+C 是个增量优化,用户加的"画像中间层"才是质的飞跃。**画像 markdown 入 git 后还成了数据资产**,后续 006(题库扩 200 人)/未来的"判断题/选择题"等新玩法都能复用同一份 profile。

### 2. Stage 3 prototype 救场:gemini-2.5-pro 是 thinking model

prototype 阶段我并行测 3 个强 LLM(给 profile 用): `claude-haiku-4-5` / `gemini-2.5-pro` / `deepseek-v3.2`。结果:

- **claude-haiku-4-5**:profile 1962 字,8 sections 完整,反差点 3 个。¥0.18/figure。
- **gemini-2.5-pro**:**profile 0 字**,`completion_tokens=3997` 全在 `reasoning_tokens`,`content=""`。后续 pipeline 拿到空 profile 失败。**这是 thinking model,云雾上输出全在 reasoning,实际 content 是空**。
- **deepseek-v3.2**:profile 1546 字,反差点 3 个**更深**(引《魏略》少数派记载),¥0.05/figure。**质量与 haiku 持平,成本 1/4**。

**SPEC OQ1 推荐 deepseek-v3.2 主选 + 必须排除 thinking model 类型**(`reasoning_tokens > 0 + content 空 → raise`)。这一条直接写进了 generate_figures.py 的 call_llm 函数防御。

> 给 v1.3 的 best practice:**"prototype 阶段用统一 spike 脚本横向测多 model 取代 grill-me 阶段拍脑袋选,model 选择从'假设 + 上线后才知道'变成'实测 + 决策前定'"**。

### 3. AC 双通道 verification-before-completion 抓到一个 LLM 改名 bug

Stage 7 跑全 50 旧 figure 重生成时,我让 verification 直接对比 v1/v2 by name。结果 regen_diff 报"50 旧只匹配到 35 个 v2 candidates 而 36 个里有 1 个不对"—— 仔细查发现:**LLM 在 clues_obj 里把"康熙"改成了"康熙帝"**。原 code `figure["name"] = clues_obj.get("name", name)` 取 LLM 输出,导致 name 不匹配。

修法:`figure["name"] = name`(hardcode 输入 name,忽略 LLM 输出的 name 字段)。

> 给 v1.3 的失败模式:**"LLM 输出可能静默改 figure name(乾隆→乾隆帝 / 康熙→康熙帝 / 杨广→隋炀帝杨广 等),production code 应 hardcode key field 而非取 LLM 输出"**。

## prompt 调优 2 轮的迭代曲线

### 第 1 轮(T14 灰度 1):4/5 → 1/5 通过率

灰度 5 figure(乾隆/关羽/刘备/李白/苏轼)第 1 次跑只有**苏轼 1 个通过**,其余 4 个 judge 重试 3 次仍违规。

诊断 profile 内容发现:**乾隆 profile aliases section 含 11+ 个 alias**(字"元寿" + 号"长春居士、信天主人、古稀天子、十全老人" + 30 字完整谥号 + 庙号"高宗" + 别号"乾龍、亁隆")。LLM 在 clue 阶段几乎不可避免触发某个 alias 子串("高宗"/"长春"/"十全" 等 2 字),judge 严格 ≥ 2 字子串规则一直 flag。

**苏轼成功是因为 aliases 只有 6 个,且 LLM 学会用"号常被作菜名"代称避「东坡居士」**(d7 写"其号取自其居住地,且其号常被作为一种清雅的植物代称"避「青莲居士」的 alias 子串)。

### 第 2 轮(T14 灰度 2):4/5 通过率(X + Y 方案)

修 2 处:

- **X 方案**(治本):`PROFILE_PROMPT` 限制 aliases section **严格 ≤ 5 个最常用**,排除 ≥ 10 字完整谥号(取末 2-3 字简称如"忠武"/"昭烈"/"纯帝")。**LLM 在 build_profile 阶段就 sanitize**,clue 阶段看到的就是精简列表。
- **Y 方案**(止损):`JUDGE_PROMPT` 子串规则从 ≥ 2 字 放宽到 ≥ 3 字(`"高宗"`/`"弘历"`/`"云长"` 2 字 不再算违规;`"长春居"` 3 字 子串 ⊂ `"长春居士"` 仍算)。**LLM 判定标准与 deterministic check 对齐**。

效果:4/5 通过(关羽 / 刘备 / 李白 / 苏轼;乾隆仍 fail —— alias「十全老人」典故「十全武功」太著名 LLM 在 d1-5 难避开,systematic hard case)。

> 给 v1.3 的失败模式:**"LLM stochastic + profile aliases 列表长度 直接 driver clue 触发率;aliases section 不限长会让 hard case figure 几乎不可能 judge 通过"**。

## Stage 8 抓到的 hard case 死循环

全 50 旧 figure 跑出 **36/50 通过 + 14 failed**(乾隆 / 刘邦 / 司马懿 / 司马迁 / 嵇康 / 张居正 / 张飞 / 戚继光 / 李世民 / 李白 / 杜甫 / 杨贵妃 / 王安石 / 郑和),20 新皇帝 retry 后 **15/20 通过 + 5 failed**(刘协 / 杨广 / 柴荣 / 万历 / 雍正)。

共同特征:**alias 多 + 典故密 + 历史地位极高的 famous figure**。LLM 在 d1-5 几乎写不出"不触 banlist + 不触 aliases 子串"的合规 clue —— 不是 prompt 不够好,是这些人物**信息密度本身**太高,任何线索都会指向他们。

**用户在中途多次 explicit accept 偏差**(T15 "A 接受 65 GO 进 T23" + T20 "全部按自动决策" + Stage 8 "通过"),最终 figures.json 65/70 entry 上线。**workflow 灵活性证据**:SPEC AC 字面违反但 user 知情同意,Stage 9 sign-off 通过。

> 给 v1.3 的 best practice:**"hard case 失败 ≠ SPEC 失败,workflow 应有'中途偏差 explicit accept' 路径,允许 user 在 acceptance 关卡之前接受 known 偏差并写入 git history,而非 fix-or-die"**。

## Wikisource mapping 中文数字 vs 阿拉伯数字

T22 跑 20 新皇帝第 1 轮 0/20 全 fail —— 全部 figure 的 Wikisource fetch 都返 "page doesn't exist"。诊断发现:**Stage 5 SPEC patch v1.0.1 里 AI 帮 user 写的 20 个 wikisource_page mapping 全用中文数字**(`後漢書/卷一上` / `宋史/卷十九` / `清史稿/卷九`),但 **Wikisource 中文版实际用阿拉伯数字**(`後漢書/卷1上` / `宋史/卷19` / `清史稿/卷9`)—— 我 WebFetch 验证后才发现。

修两处:
1. `history_index.json` 中 20 mapping 改阿拉伯数字
2. `fetch_wikisource_history` 增强容错:加 `_wikisource_page_variants()` 自动试 阿拉伯/中文数字 + 卷上下后缀,防 LLM 输出格式漂移

第 2 轮 retry 5/10 通过(累计 15/20)。10 → 5 是 LLM stochastic + hard case alias 密的合并结果。

> 给 v1.3 的失败模式:**"LLM 凭历史知识写 wikisource/wiki page name 容易格式漂移(中文 vs 阿拉伯数字 / 简繁体 / 卷上中下后缀),需要 mapping 生成后 verify 一遍 hit rate 才进 production pipeline"**。

## LLM judge 跟 deterministic check 标准不一致 anti-pattern

T23 跑 quality_check 全 65 figure,第 1 次满分率 **42%**(27/65)—— 远低于 SPEC AC6 90% 阈值。诊断发现:**quality_check 的 check #6(d6/7 alias 子串)还在 ≥ 2 字 严格规则**,但 judge prompt 已经 ≥ 3 字 放宽。**两套标准不一致**,deterministic check 报大量 "高宗"/"弘历" 等 2 字子串 warning,而生产时 judge 实际不 flag。

修对齐:check #6 改为 **d1-5 ≥ 3 字 子串**(跟 judge prompt 一致 + 跟 check #4 d1-5 整字 互补;d6/d7 求救范围允许暴露,不查)。再跑满分率 **95.4%**(62/65),AC6 过。

> 给 v1.3 的 best practice:**"deterministic check 跟 LLM judge prompt 必须用同一套规则,否则会出现 generation pass 但 quality_check fail 的双重 standards"**。

## regression 兜底 v1+v2 混合机制

50 旧 figure 重生成不是简单覆盖。`scripts/regen_diff.py` 自动算每个 figure 的 v1 score vs v2 score(用同一升级版 quality_check),自动标"候选采用 v2"(v2 比例 ≥ v1 比例 且 v2 violations ≤ v1)或"保留 v1"。50 个 figure 最终决策:**31 采用 v2 + 5 拒绝(v1 满分但 v2 引入新 alias 子串)+ 14 v2 failed 全保留 v1** = 50 entry v1+v2 混合。

用户 T20 "全部按自动决策" 一句话通过,产 final `figures.json`。**没有这套 regen_diff 机制,要么整体回退(失去 31 个真变好的 figure),要么全用 v2(冒 5 个 regression 风险)**。混合是最优解。

> 给 v1.3 的 best practice:**"内容/数据重生成任务必须有 'individual rollback' 机制 + 自动决策辅助(score-based),用户只 review 边界情况,不必逐 entry 决定"**。

## 整体感受

V3 是个**比 V2 更隐蔽的内容质量阶跃**——玩家看不到 pipeline 重构,只感觉 "诶,d1 怎么变这么难了 / 现在求救一定能猜到"。`profiles/*.md` × 69 个 markdown 入 git,**正向副作用**:后续 006(扩 200 人)/ "判断题"等新玩法都能基于同一份 profile data 复用,内容生产从"一次性"变成"数据资产化"。

总跨度 1 个工作日,**核心 LLM 跑 70 figure 实际耗时约 1 小时 + 2 轮 prompt 调优交互(灰度 5 → 5 → 5)**。其中大半时间在 prompt iteration —— 5 figure 灰度 → 看结果 → 调 prompt → 再跑 → 反复。LLM 时代的"调试"不再是改代码看 stack trace,是**改 prompt 看 LLM 行为分布**。

### 给 v1.3 的 5 个失败模式 / 5 个 best practice 汇总

**失败模式**:

1. LLM 静默改 figure name(乾隆→乾隆帝 / 康熙→康熙帝)— production code 应 hardcode key field
2. LLM stochastic + profile aliases 长度 driver clue 触发率 — aliases section 必须 cap
3. LLM 凭知识写 page name 容易格式漂移 — mapping 生成后必须 verify 一遍
4. thinking model `content` 空陷阱 — call_llm 必须 detect `reasoning_tokens > 0 + content 空 → raise`
5. deterministic check 跟 LLM judge prompt 双重 standards — 必须对齐

**best practice**:

1. prototype 阶段 spike 脚本横向测多 model(model 选型从假设变实测)
2. workflow 应有"中途偏差 explicit accept"路径(允许 known 偏差 written into history,而非 fix-or-die)
3. 内容重生成必须有 "individual rollback" 机制 + score-based 自动决策辅助
4. 数据资产化(profile markdown 入 git)— 一次生产多次复用
5. hard case ≠ workflow 失败,SPEC AC 字面 vs spirit 用户 explicit accept 即可

期待 v1.3 把这 5+5 写进 specification.md 和 SKILL.md。
