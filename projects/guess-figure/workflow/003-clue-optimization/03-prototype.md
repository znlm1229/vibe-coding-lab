# Stage 3 ｜ Prototype 原型

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-3--prototype-原型)
>
> **要点**:解决最大不确定性;最小可运行;用完即弃。

## 决定

- [x] **构建原型** — 解决的不确定性:
  - 强 LLM 直接消化文言文 + 三源材料的可行性
  - 二十四史 Wikisource 接入是否 work
  - profile 中间层 + flash clue + judge 3 步 pipeline 跑通
  - 校准强 LLM 候选 (OQ1) 的实际成本与质量

## 原型位置

- 代码:[`scripts/proto_pipeline.py`](../../scripts/proto_pipeline.py) (~ 400 行 Python spike,**用完即弃**,production 实现会重写)
- 跑了 3 个 model 对比:
  - [`proto/run-claude-haiku-4/`](./proto/run-claude-haiku-4/) — claude-haiku-4-5-20251001
  - [`proto/run-gemini-2.5-pro/`](./proto/run-gemini-2.5-pro/) — **失败 (thinking model)**
  - [`proto/run-deepseek-v3_2/`](./proto/run-deepseek-v3_2/) — deepseek-v3.2

测试 figure: **诸葛亮**(三国志卷 35,有完整二十四史本传,材料充足)。

每个目录含:
- `material.txt` — 三源材料拼接 (~ 15K 字)
- `profile.md` — 强 LLM 产的画像
- `clues.json` — flash-lite 产的 7 条
- `judge.json` — flash-lite judge verdict
- `cost.json` — token / 耗时明细

## 验证 / 证伪了什么

### ✅ 验证通过

1. **强 LLM 直接消化文言文产 profile 可行**(Q1+Q2 决议被证实)。claude-haiku 和 deepseek 都成功:
   - 8 sections 完整输出
   - 引用了三国志原文(如「治戎为长,奇谋为短」「科教严明,赏罚必信」),证明真消化了文言文
   - 「反差 / 鲜为人知点」section 都 ≥ 3 条优质内容(娶丑女 / 《魏略》主动求见少数派 / 对刘琦冷漠)
2. **二十四史 Wikisource API 接入 work**。`zh.wikisource.org/w/api.php?action=parse&page=三國志/卷35` 5000 字成功拉取,wiki markup 简单清后可直接喂 LLM
3. **d1 加难 guidance 路线效果好**(Q4 决议 D 折中被证实):
   - claude-haiku d1:「他曾因择偶标准被乡里编成谚语嘲笑,且在躬耕陇亩时常自比古之名将,却被周围士人轻视」— 完全用反差,普通人大概率猜不出
   - deepseek d1:「他曾因择偶标准异于常人沦为乡里笑谈,且史料中存在其主动投奔而非被动受邀的记载」— 同样用反差,引《魏略》少数派
4. **pipeline 3 步端到端跑通**(fetch 三源 → 强 profile → flash clue → flash judge),总耗时 ~50s/figure
5. **Wikidata 现有 6 字段(无需扩 15 字段)已经够用** — 6 字段 + 维基全文 + 二十四史构成的材料,LLM 产出的 profile 已经很丰满。**SPEC 阶段可以**降低 brainstorm v3 §"输入侧扩材料"的 Wikidata 字段扩展范围(从 15 → 暂保持 6 + 后续按需扩)
6. **中文文件名在 Windows + git 下 work**(profiles/run-claude-haiku-4/ 目录中文 .md 文件读写 OK)

### ❌ 证伪 / 排除

7. **gemini-2.5-pro 不适用**。这是 thinking model — completion_tokens=3997 全在 reasoning_tokens,content 字段空,后续 pipeline 拿到空 profile 失败。
   - **对 OQ1 的影响**:候选强 LLM **必须排除 thinking model 类型**。gemini-2.5-pro / gemini-2.5-pro-thinking-* / claude-opus 系若开了 thinking 同样会失败
   - 如需用 gemini 系应选 non-thinking:gemini-3-flash-preview / gemini-2.5-flash

### ⚠️ 暴露的待精化点

8. **d4-d5 banlist 控制不严**。两 model 都忍不住在 d4/d5 用了木牛流马 / 八阵图 / 出师表等 banlist 词:
   - claude-haiku d5:「连发弩机...山地运输粮草的机械装置」(对应诸葛连弩、木牛流马)
   - deepseek d4:「山地运输难题...复杂的军事阵法」(对应木牛流马、八阵图)
   - **修复方向**(SPEC 阶段):
     - prompt 里把 banlist 显式塞入(目前只在 judge prompt 中塞了 banlist,clue prompt 没塞)→ clue LLM 看不到 banlist,自然控制不住
     - 加 negative guidance(few-shot 反例)
     - 自动 judge 循环重试时,反馈具体哪条 banlist 触发,LLM 第二次能避开
9. **judge prompt 把 d6/d7 也禁了 banlist**(原 Q4 决议:d6/d7 允许典故)。需要在 judge prompt 里把规则改成"d1-d5 禁 banlist,d6-d7 允许 banlist 但禁 aliases 子串"
10. **stdout 中文乱码**(Windows console 默认 GBK)。已在 spike 代码加 `sys.stdout.reconfigure(encoding="utf-8")`,SPEC 阶段沿用

## 对 SPEC 的影响

### OQ 决议更新

| OQ | grill-me 推荐 | prototype 后修正 |
|---|---|---|
| **OQ1** 强 LLM 具体型号 | claude-haiku-4-5 | **deepseek-v3.2 作主选**(成本 ¥3.5/70 figure,质量与 haiku 相当且反差点更深);claude-haiku-4-5 作 备用;**必须排除 thinking model** |
| OQ2 judge 用哪个模型 | gemini-3.1-flash-lite | 保持(prototype 验证 flash judge work,但需 SPEC 精化 prompt 区分 d1-5 vs d6-7) |
| OQ9 二十四史字数上限 | 5000 字 | 保持 |
| OQ10 profile typology section extract | regex | 验证可行(`^##\s+典故 / 标志事件\s*\n((?:[-*]\s*.+\n?)+)` work) |

### 成本估算修正(再次)

- grill-me §中危风险预估 ¥12-15(基于 claude-haiku 报价)
- prototype 验证 claude-haiku **¥0.18/figure × 70 = ¥12.6** ✓ 准
- prototype 发现 deepseek-v3.2 **¥0.05/figure × 70 = ¥3.5** —— 选 deepseek 作主选成本可降到 **¥4-5 总**(含 judge / 重试)

### 新增 OQ(prototype 暴露)

| # | 问题 | 类型 | 推荐 |
|---|---|---|---|
| OQ13 | clue prompt 是否要 inject banlist | technical | **是**(prototype 暴露:不塞 banlist 时 LLM 控制不住 d4-d5),inject 从 profile typology section 提取的词 |
| OQ14 | judge prompt 的 d6/d7 规则修正 | technical | judge prompt 改成"d1-d5 禁 banlist + aliases 子串;d6-d7 允许 banlist 但仍禁 aliases 子串" |
| OQ15 | Wikidata 字段范围 | technical | **保持 6 字段(现有)**,不扩 15;prototype 证实 6 字段已够;若 SPEC 后发现 profile 缺信息再扩 |

### SPEC 可以删掉的内容

- brainstorm v3 §"Wikidata 字段补全(6 → 15)" — 验证后发现没必要,SPEC 不需写这条
- brainstorm v3 §"百度百科 / 二十四史 / CN-DBpedia" 部分 — prototype 验证仅 Wikisource 二十四史已够,SPEC 不引入百度百科 / CN-DBpedia

### SPEC 必须新增的内容

- **clue prompt inject banlist** 的实现细节(从 profile typology section regex extract → 塞入 prompt 的 "你必须避免的词" block)
- **judge prompt 的 d1-5 vs d6-7 规则区分**
- **强 LLM 候选排除 thinking model 类型** 的硬约束
- **stdout UTF-8 reconfigure** 在所有 Python 脚本顶部

## 给 Stage 4 SPEC 的下一步建议

SPEC 写出 12 项 + 新增 3 项 = **15 项 Acceptance Criteria**,要覆盖:

1. **pipeline 结构 AC**:fetch 三源 → 强 LLM profile (deepseek 主) → flash clue (含 banlist inject) → flash judge → 重试循环 N=2
2. **质量 AC**:升级 quality_check 6 项 + LLM judge 第 7 项
3. **行为 AC**:d1-3 加难效果(主观抽样 ≥ 8/10 觉得"梯度合理")
4. **regression AC**:figures.v2-candidates 个体回退流程
5. **20 皇帝候选清单 AC**:AI 提案 70 候选 → 用户审 → 跑全 70 figure
6. **成本 AC**:总 LLM 成本 ≤ ¥10(基于 deepseek 主选,预留 buffer)
7. **数据资产 AC**:profiles/*.md × 70 入 git,deploy 包大小 ≤ 5MB
8. **失败处理 AC**:N=2 重试后仍违规的 figure 标 failed,< 5 个

按 v1.2 规范,每条 AC 必须双通道(AI 验证 + 人工验证)写明。
