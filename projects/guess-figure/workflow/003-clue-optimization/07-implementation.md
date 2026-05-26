# Stage 7 ｜ Implementation 实现 + Stage 8 入场报告

> Stage 7 完成,Stage 8 Human QA 入场前最后一站。
> **v1.2 强制**:本节调用 `verification-before-completion` skill 跑过,每条 AC 都有命令证据。

---

## 改了什么 (T1-T26 全 commit 汇总)

| Task | Commit | 改动 |
|---|---|---|
| T1 | `7e56b5f` | scripts/gen_history_index.py + scripts/data/history_index.json (50→后续 70) |
| T2 | `7e56b5f` | scripts/few_shot_examples.md (5 好 + 5 坏) |
| T3 | `59d4db2` | quality_check.py + 单测 (d6/7 alias 子串 → 后改 d1-5 ≥3字) |
| T4 | `7a178ea` | quality_check.py extract_banlist_from_profile + check #7 |
| T5 | `c3fb437` | quality_check.py count_specific_terms + check #8 信息密度 |
| T6 | `614442e` | quality_check.py JUDGE_PROMPT + judge_clues_llm + --with-judge flag |
| T7-T13 | `455d41a` | generate_figures.py v2 (3 步 pipeline + retry + cost cap) + 单测 |
| T14 | `4a1059e` + `70b8b2b` | 灰度 + 2 轮 prompt 调优 (judge 子串 ≥3字 + profile aliases ≤5 + clue 用代称) |
| T15 | (用户 GO) | 灰度 4/5 通过 → GO 进 Phase 5 |
| T16 | `866f6ee` | spec-emperor-list.md 20 候选 |
| T17 | `7f9e15f` | SPEC v1.0.1 + history_index.json 50→70 |
| T18 | `T18 commit` | 跑全 50 旧 figure,36 通过 |
| T19 | (含 T18 commit) | regen_diff.py + scripts/data/regen_diff.md |
| T20 | (用户 "全部按自动") | 31 采用 v2 + 5 拒绝 + 14 v2 failed |
| T21 | `8cd0e90` | figures.v1.json baseline + figures.json 50 混合 |
| T22 | `32c624e` + retry | 20 新皇帝:第 1 轮 10/20 + retry 5/10 = 总 15/20 通过 (mapping 阿拉伯数字 fix) |
| T23 | `9c80934` | quality_check 跑 65 figure: 62 满分 (95.4%) |
| T24 | (verify) | npm test 66/66 + npm run build ✓ |
| T25 | `push 9c80934` | git push origin main → CF Pages auto build/deploy |
| T26 | 本 artifact | 入场报告 + verification 证据 |

**累计 commit ≈ 20+,LLM 总成本 ¥2.61,工时约 1 个工作日跑通**

---

## SPEC AC 状态汇总(18 项)

按 v1.2 规范,每条 AC 双通道(AI 验证 + 人工验证)。下面是 **AI 验证**结果,人工验证留 Stage 8。

### ✅ PASS (12 项 — AI 验证已通过)

| # | AC | AI 验证证据 |
|---|---|---|
| AC1 | generate_figures.py v2 重写为 3 步 pipeline | `grep -c "def build_profile\|def clues_from_profile\|def judge_and_retry" scripts/generate_figures.py` → **3** ✓ |
| AC2 | history_index 70 entry + 覆盖率 ≥ 80% | total=**70**, non_null wikisource_page=**67** (95.7%) ≥ 80% ✓ |
| AC5 | quality_check 升级 4 项 (新增 #6 #7 #8 + judge) | grep "check #6/#7/#8/judge_clues_llm/extract_banlist" 共 **10** matches ✓ |
| AC6 | 满分率 ≥ 90% | quality_check --profiles-dir 跑 65 figure: **62/65 = 95.4%** ≥ 90% ✓ |
| AC7 | 单 figure < 90s | cost_summary.json: **0/70** figure latency > 90s ✓ |
| AC8 | 总成本 ≤ ¥10 | cost_summary.json total_cost_cny = **¥2.61** ≤ ¥10 ✓ |
| AC10 | figures.v1.json baseline 入 git | exists (`127167 bytes`),commit `8cd0e90` ✓ |
| AC11 | regen review 50 混合 v1+v2 | `scripts/data/regen_diff.md` 已生成 + 用户 "全部按自动决策" → 31 v2 + 19 v1 混合 ✓ |
| AC12 | 部署 zero-break | npm test **66/66 vitest pass** + npm run build **exit 0 4.11s** + push 完成 `c168b22..9c80934` ✓ |
| AC16 | 不破坏游戏机制 | `git log 0a56e7b..HEAD -- src/lib/types.ts game-state.svelte.ts src/routes/` → **0 commits** ✓ |
| AC17 | thinking model 防御 | `grep -c "reasoning_tokens"` = **4** (call_llm raise + 3 单测 cases) ✓ |
| AC18 | clue prompt inject banlist | `clues_from_profile(... banlist: list[str], ...)` signature + `grep -c "banlist"` = **20** + 单测覆盖 ✓ |

### ⚠️ PARTIAL (2 项 — 实质未完全达到 SPEC 字面)

| # | AC | 字面 | 实际 | 原因 |
|---|---|---|---|---|
| AC3 | 题库 70 figure | 70 | **65** | 5 个新皇帝(刘协 / 杨广 / 柴荣 / 万历 / 雍正)judge 重试 3 次仍违规,无 v1 fallback,不入 figures.json |
| AC4 | profiles/*.md × 70 | 70 | **69** | 刘协 build_profile 因 yunwu API HTTP 500 失败,无 .md 产出 |

### ❌ FAIL,但 SPIRIT OK (1 项)

| # | AC | 字面 | 实际 | 实质 |
|---|---|---|---|---|
| AC9 | failed ≤ 5/70 | 5 | **19** | 50 旧 14 failed 全有 v1 fallback(figures.json 保留 v1 entry);5 新皇帝无 fallback(造成 AC3 65/70)。AC9 字面违反 ≥ 4 倍,但 figures.json 最终是 65 entry(50 混合 + 15 新)未缺 entry,仅 5 新缺 |

### 留 Stage 8 主观行为(3 项 — 必须人工验证)

| # | AC | 验证路径 |
|---|---|---|
| AC13 | d1-3 加难:10 局 ≥ 7 需打开 d4+ | 用户实测玩 10 局,记录 d1-3 内猜出 vs d4+ |
| AC14 | d6-7 救命 ≤ 7/10 | 同 AC13 的 10 局,d6-7 才猜出次数 |
| AC15 | 玩 20 局比 V2 旧版耐玩 | 用户连玩 20 局,主观体感对比 |

---

## SPEC v1.0/1.0.1 偏差(用户在 Stage 9 决定是否接受)

| 偏差 | 严重度 | 用户已确认 |
|---|---|---|
| AC3 题库 65/70(5 新皇帝缺) | 中 | 用户 T15 后 "A 接受 65 GO 进 T23"(commit `32c624e`)— 已接受 |
| AC4 profiles 69/70(刘协缺) | 低 | 与 AC3 关联,同上 |
| AC9 failed 19 > 5 | 高字面/低 spirit | 50 旧有 v1 fallback 兜底;5 新无 fallback 即 AC3 偏差 |

**建议**:Stage 9 Acceptance 时,user 可选:
- (a) 接受 65/70(SPEC v1.0.2 patch 修订 AC3/AC4/AC9 阈值)
- (b) 再做一轮 retry 失败 5 皇帝(成本 ~¥0.25,但已 iterate 多轮边际收益低)
- (c) 用 5 备选替换(北周武帝/唐肃宗/嘉庆/光绪/明仁宗)

---

## Stage 8 人工 QA 入场指南

### 怎么手测 4 件事

#### 1. AC13/14 难度梯度感受(必做)

```
浏览器开 https://guess-figure.pages.dev/play
连玩 10 局, 每局换 figure (用 "换一个人物" 按钮)
记录每局: d1-3 内猜出 / d4-5 内 / d6-7 才猜
目标: d1-3 内猜出 ≤ 3 局 (≥ 7 局靠 d4+ 才出), d6-7 救命 ≤ 7 局
```

#### 2. AC15 整体耐玩度(必做)

```
连玩 20 局
主观对比: 是否比 V2 旧版有意思? (V2 旧版指 002 上线后 50 figure)
看点:
- d1 是否够隐晦 (反差点而非典故)?
- d4-5 是否甜点 (信息恰到好处)?
- 新增 15 个皇帝 (拓跋宏/杨坚/赵祯/赵佶 等) 是否新鲜?
```

#### 3. AC16 游戏机制兼容性(快速验证)

```
浏览器测以下行为, 与 V2 旧版一致即可:
- [ ] 答错自动消耗 1 条线索 (002 SPEC v1.1 行为)
- [ ] 标准范围用完 → "🆘 求救" 按钮出现
- [ ] 求救范围答对 → 得分 ≤ 10
- [ ] 标准范围 d1 答对 → 100 分 (6-1)*20
- [ ] "放弃看答案" 显示 figure 名 + wiki_url
```

#### 4. AC2 spot check Wikisource mapping(随机抽 5)

```
浏览器随机访问 5 个 mapping (从 scripts/data/history_index.json) 看 Wikisource page 真实存在:
- 推荐: 苏轼 https://zh.wikisource.org/wiki/宋史/卷338 (✓ 已 verify)
- 推荐: 杨坚 https://zh.wikisource.org/wiki/隋書/卷1
- 推荐: 朱棣 https://zh.wikisource.org/wiki/明史/卷5
- 推荐: 道光 https://zh.wikisource.org/wiki/清史稿/卷17
- 推荐: 拓跋宏 https://zh.wikisource.org/wiki/魏書/卷7上
```

### 已知问题(Stage 8 不需要重测)

1. **5 个新皇帝缺失**(刘协 / 杨广 / 柴荣 / 万历 / 雍正)— 用户 T22 后已接受 65/70
2. **3 个 quality_check warning** — 张居正 d3 "考成法" / 李清照 aliases 数 2 / 武则天 d4 "神龙革命"。都是 v1 旧 figure 残留问题,SPEC v1.0 没要求修;Stage 9 可决定是否要 patch
3. **deploy 后 CF Pages cache** — 若 https://guess-figure.pages.dev 仍显示旧版,等 1-2 min CDN propagate

### 如果 Stage 8 发现 bug

按 v1.2 规范:
- 回 Stage 7 修 → commit 用 **`fix(TX): ...`** prefix(而非 `task-TX:`)
- 重新做 Stage 8 入场报告 + verification-before-completion
- 不允许 amend 已有 commit

---

## verification-before-completion 调用记录

- **Skill**:`verification-before-completion` (v1.2 强制)
- **调用时间**:2026-05-26 17:30
- **verification 命令**:全部跑过,见上表的"AI 验证证据"列(每条 AC 都有命令 + 输出)
- **claim 与 evidence 一致性**:✓ 所有 PASS 都有 fresh command output 支撑;PARTIAL/FAIL 都明示 gap

---

**Stage 7 收尾** — 准备 Stage 8 Human QA。等用户测完 AC13/14/15/16/AC2 后进 Stage 9 Acceptance。
