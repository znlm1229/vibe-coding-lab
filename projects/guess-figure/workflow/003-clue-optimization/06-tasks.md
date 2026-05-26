# Tasks: 003 — 线索优化

> Stage 6 ★ 人工关卡。标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)。
>
> **v1.2 commit 前缀**:`task-TX:` 新 task 首次实现 / `stage-N:` 阶段产出 / `fix(TX):` Stage 8 回路修复。
>
> **Done when 必须可验证**(跑得出证据,不写"功能完成")。
>
> **用户未确认前不得进入 Stage 7**。

---

## 任务清单(T1-T26,对应 Plan Phase 1-8)

### Phase 1 — 准备数据

- [ ] **T1 — 半自动生成 history_index.json**
  - Touches:`scripts/data/history_index.json` (new),`scripts/gen_history_index.py` (new spike,可后 throwaway)
  - Done when:
    - (a) `scripts/data/history_index.json` 含 50 entry(20 皇帝由 T17 补;此 task 先 50 旧 figure 的 mapping),非 null 覆盖率 ≥ 80%
    - (b) 用户随机抽 5 个 mapping,浏览器访问 Wikisource page 实际存在
  - Depends on:nothing

- [ ] **T2 — few-shot 示例池起草**
  - Touches:`scripts/few_shot_examples.md` (new)
  - Done when:
    - (a) 文件含 5 好 + 5 坏对比示例(坏例从 figures.json 真实穿底案例选:乾隆 d1 / 关羽 d7 / 刘备 d7 / 刘备 d2 / 乾隆 d5 梯度乱序)
    - (b) 用户 review 通过(commit 后用户在对话确认)
  - Depends on:nothing

### Phase 2 — quality_check.py 升级(可与 Phase 1 并行)

- [ ] **T3 — d6/7 alias 子串检测**
  - Touches:`scripts/quality_check.py`(新增第 6 项 check),`scripts/tests/test_quality_check.py` (new)
  - Done when:
    - (a) `python scripts/quality_check.py src/lib/data/figures.json --verbose` 输出第 6 项 check 结果,关羽 d7「字云长」被标违规
    - (b) `python -m pytest scripts/tests/test_quality_check.py -v` 含至少 1 个 d6/7 子串穿底正反例单测且 pass
  - Depends on:nothing

- [ ] **T4 — d1-5 典故 banlist 检测(从 profile extract)**
  - Touches:`scripts/quality_check.py`(新增第 7 项 check + extract_banlist_from_profile 函数),`scripts/tests/test_quality_check.py`
  - Done when:
    - (a) check 接受参数:figure 关联的 profile.md 路径,从中 regex 抓「典故/标志事件」「关键作品」section 词作为 banlist
    - (b) 单测覆盖 banlist regex extract 正确性(用 prototype 跑出的 profile.md 作为 input)
  - Depends on:T3

- [ ] **T5 — 信息密度启发式**
  - Touches:`scripts/quality_check.py`(新增第 8 项 check)
  - Done when:
    - (a) check 统计每条 clue 的"具体名词数"(用 regex 抓「《...》」+ 中文专有名词 pattern,简化版),要求难度越低密度越低
    - (b) 单测含"梯度反转"反例(如 d1 5 个名词、d5 2 个名词 → 应预警)且 pass
  - Depends on:T4

- [ ] **T6 — LLM-as-judge 集成**
  - Touches:`scripts/quality_check.py`(新增 `--with-judge` flag + judge prompt 实现)
  - Done when:
    - (a) `python scripts/quality_check.py src/lib/data/figures.json --with-judge` 跑通(调 flash LLM judge),judge prompt 显式区分 d1-5 vs d6-7 规则
    - (b) 单测含 judge 输出 JSON parse(mock flash LLM)
  - Depends on:T5

### Phase 3 — generate_figures.py v2 pipeline 重构

- [ ] **T7 — fetch_three_sources 实现**
  - Touches:`scripts/generate_figures.py`(重写 fetch 部分),`scripts/tests/test_generate_figures.py` (new)
  - Done when:
    - (a) `fetch_three_sources(name, mapping)` 返回 dict 含 wiki/wikidata/history 三 key,维基扩到 5000 字,二十四史按 mapping 拉,mapping=null 走 fallback(history=None)
    - (b) 单测(mock requests):mapping=null 时 history=None,有 mapping 时拉到 wikisource 内容(stub)
  - Depends on:T1(mapping table 作输入)

- [ ] **T8 — build_profile 实现(含 thinking model 防御)**
  - Touches:`scripts/generate_figures.py`(新增 build_profile 函数 + PROFILE_PROMPT)
  - Done when:
    - (a) `build_profile(material, model)` 调强 LLM,8 sections regex 验证(缺则重试 1 次后 raise),且含 `if reasoning_tokens > 0 and not content: raise` 防 thinking model(AC17)
    - (b) 单测(mock LLM):正常 case + 8 sections 缺 case + thinking model case 3 个全 pass
  - Depends on:T7

- [ ] **T9 — extract_banlist_from_profile(共用工具)**
  - Touches:`scripts/generate_figures.py`(新增工具函数,与 quality_check.py T4 用法一致)
  - Done when:
    - (a) `extract_banlist_from_profile(profile_md)` 返回词列表(典故+作品 section 各行的内容)
    - (b) 单测用 prototype 跑出的 profile.md 验证 extract 出 ≥ 5 词(诸葛亮的)
  - Depends on:T8

- [ ] **T10 — clues_from_profile 实现(inject banlist + few-shot)**
  - Touches:`scripts/generate_figures.py`(新增 clues_from_profile 函数 + CLUE_PROMPT),`scripts/few_shot_examples.md` 读取
  - Done when:
    - (a) `clues_from_profile(profile, banlist, few_shot_pool, model)` 调 flash LLM,prompt 中 inject banlist + 从 pool 选 2 对 few-shot,输出 JSON 7 clues
    - (b) 单测(mock flash LLM):JSON parse 成功 + 失败 retry 1 次路径 + final 失败 raise
  - Depends on:T8,T9,T2(few-shot pool)

- [ ] **T11 — judge_clues 实现(d1-5 vs d6-7 区分)**
  - Touches:`scripts/generate_figures.py`(新增 judge_clues 函数 + JUDGE_PROMPT)
  - Done when:
    - (a) `judge_clues(aliases, banlist, clues, model)` 调 flash LLM,prompt 显式写"d1-5 禁 banlist + aliases 子串;d6-7 允许 banlist 但仍禁 aliases 子串"(OQ14)
    - (b) 单测含 d6/7 含 banlist 应判合规(非违规)+ d3 含 banlist 应判违规
  - Depends on:T10

- [ ] **T12 — retry loop + failed_figures.json**
  - Touches:`scripts/generate_figures.py`(新增主循环逻辑),`scripts/data/failed_figures.json` (产物)
  - Done when:
    - (a) judge 任一 verdict="违规" → 回 clues_from_profile 重新生成,inject 上次违规反馈作 negative example,最多 N=2 次重试;仍违规 → 该 figure 标 failed 写入 failed_figures.json,不入 figures.json
    - (b) 单测(mock judge 第一次"违规",第二次"合规")覆盖 retry+pass 路径
  - Depends on:T11

- [ ] **T13 — cost cap + cost_summary.json**
  - Touches:`scripts/generate_figures.py`(新增 cost 累积逻辑),`scripts/data/cost_summary.json` (产物)
  - Done when:
    - (a) 每 figure 跑完后 cost 累积写入 cost_summary.json,总 cost ≥ ¥10 时 abort(exit 3)
    - (b) 单测(mock LLM usage)覆盖 cap 触发路径(模拟跑 100 figure 累积 cost > ¥10 应 abort)
  - Depends on:T12

### Phase 4 — 灰度 5 figure

- [ ] **T14 — 跑灰度 5 figure(乾隆/关羽/刘备/李白/苏轼)**
  - Touches:`src/lib/data/profiles/{乾隆,关羽,刘备,李白,苏轼}.md` × 5(new),临时 `scripts/data/figures.v2-grayscale.json`
  - Done when:
    - (a) 5 个 profile.md 入 src/lib/data/profiles/,每个 8 sections 齐(`grep -c "^## " profiles/X.md ≥ 8`)
    - (b) 灰度 candidate JSON 含 5 entry,cost_summary.json 累积 ≤ ¥1,failed ≤ 1
  - Depends on:T13(pipeline ready)

- [ ] **T15 — 用户灰度 spot check(GO/NO-GO)**
  - Touches:用户主观 review(可在对话中给反馈)
  - Done when:
    - (a) 用户开 5 个 profile.md 读,确认 8 sections 完整且符合各人物身份(诗人/词人有"关键作品",将军有"关系网"政敌)
    - (b) 用户开 5 个 candidate clues 读,主观觉得"d1-3 难度感受 OK"(若 NO-GO 回 Phase 3 调 prompt)
  - Depends on:T14

### Phase 5 — SPEC v1.0.1 patch(20 皇帝清单)

- [ ] **T16 — AI 提 20 皇帝候选清单**
  - Touches:`workflow/003-clue-optimization/spec-emperor-list.md` (new)
  - Done when:
    - (a) 文件含 20 候选,每个标:朝代 / 在位时间 / wikisource page / 排除现 50 已有 11 个皇帝
    - (b) 朝代覆盖 ≥ 6 个(秦 / 汉 / 三国 / 晋 / 隋 / 唐 / 五代 / 宋 / 元 / 明 / 清 等),每朝代 1-3 个
  - Depends on:T15(灰度 GO 后才动)

- [ ] **T17 — 用户审稿 + SPEC v1.0.1 patch**
  - Touches:`spec-emperor-list.md` (modify per feedback),`04-spec.md` (升级 v1.0.1),`scripts/data/history_index.json` (add 20 entry)
  - Done when:
    - (a) 用户 accept/swap 后 spec-emperor-list.md 定盘
    - (b) 04-spec.md 修订日志加 v1.0.1 条目,history_index.json 含 70 entry(50 + 20)
  - Depends on:T16

### Phase 6 — 50 旧 figure 全量重生成 + regen review

- [ ] **T18 — 跑全 50 旧 figure 重生成**
  - Touches:`src/lib/data/profiles/*.md` × 50,`scripts/data/figures.v2-candidates.json`
  - Done when:
    - (a) 50 个 profile.md 入 src/lib/data/profiles/(含 Phase 4 灰度 5 个),figures.v2-candidates.json 含 50 entry
    - (b) cost_summary.json 累积 ≤ ¥4,failed_figures.json 中 50 旧的 failed ≤ 5(AC9)
  - Depends on:T13(pipeline)+ T15(灰度 GO)

- [ ] **T19 — regen_diff 自动对比脚本**
  - Touches:`scripts/regen_diff.py` (new),`scripts/data/regen_diff.md` (产物)
  - Done when:
    - (a) regen_diff.py 跑完输出 regen_diff.md,逐 figure 列 v1 vs v2 score + violations 对比 + 自动标"候选采用 / 拒绝"
    - (b) 输出末尾统计行:`候选采用 X / 候选拒绝 Y / X+Y = 50`
  - Depends on:T18

- [ ] **T20 — 用户 review regen_diff + 产 final figures.json(50 混合)**
  - Touches:`src/lib/data/figures.json` (final 50 entry, v1+v2 mixed)
  - Done when:
    - (a) 用户开 regen_diff.md,accept/reject "候选采用" 子集(可在对话中说"采用 X,拒绝 Y")
    - (b) final figures.json 跑 `quality_check.py --strict --with-judge` 50 个满分率 ≥ 90%(≥ 45 满分)(AC6 一部分)
  - Depends on:T19

- [ ] **T21 — figures.v1.json 备份**
  - Touches:`src/lib/data/figures.v1.json` (new from stage-1 之前的 figures.json 副本)
  - Done when:
    - (a) figures.v1.json 是 stage-1 commit `9d02f44` 之前的 figures.json 完整副本(`git show 9d02f44~1:projects/guess-figure/src/lib/data/figures.json > figures.v1.json`)
    - (b) figures.v1.json 入 git(stage-7 task-T21 commit)
  - Depends on:T20

### Phase 7 — 20 新皇帝 + 入题库

- [ ] **T22 — 跑 20 新皇帝 figure**
  - Touches:`src/lib/data/profiles/*.md` × 20 new(从 T17 名单),`src/lib/data/figures.json` (add 20 entry → final 70)
  - Done when:
    - (a) 20 个皇帝 profile.md 入 src/lib/data/profiles/,figures.json 含 70 entry(50 旧混合 + 20 新)
    - (b) cost_summary.json 总累积 ≤ ¥10(50 旧 ¥4 + 20 新 ¥2 + judge/retry buffer ≤ ¥10)(AC8),failed 总 ≤ 5(AC9)
  - Depends on:T17(名单)+ T21(50 旧 final)

- [ ] **T23 — quality_check 跑全 70 figure**
  - Touches:验证(no file mod)
  - Done when:
    - (a) `python scripts/quality_check.py src/lib/data/figures.json --strict --with-judge` 输出"✅ 满分: ≥ 63/70"(AC6 完整)
    - (b) 不满分 figure 的 quality_check 输出含具体违规理由(可解释)
  - Depends on:T22

### Phase 8 — 部署 + Stage 7 收尾

- [ ] **T24 — npm test + npm build + 兼容性验证**
  - Touches:验证(no file mod)
  - Done when:
    - (a) `cd projects/guess-figure && npm test` 跑 54 个 vitest 全 pass + `npm run build` exit 0
    - (b) `git diff main..HEAD -- src/lib/types.ts src/lib/game-state.svelte.ts src/routes/play/+page.svelte src/routes/daily/+page.svelte` 全空(AC16:不破坏游戏机制)
  - Depends on:T23

- [ ] **T25 — git push 触发 CF Pages auto deploy**
  - Touches:remote git push
  - Done when:
    - (a) `git push origin main` 成功,GitHub 触发 CF Pages build
    - (b) CF Pages dashboard 显示 build 成功 + 公网 [guess-figure.pages.dev](https://guess-figure.pages.dev) 加载新 figures.json(浏览器 DevTools Network 看 figures.json size 增加,或 view-source 看包含 20 个新皇帝 name)
  - Depends on:T24

- [ ] **T26 — Stage 8 Human QA 入场报告 + verification-before-completion**
  - Touches:`workflow/003-clue-optimization/07-implementation.md` (new)
  - Done when:
    - (a) 入场报告写明:T1-T25 改了什么 / 如何测 / AI 验证的 AC(AC1-12 / 16-18)/ 留给人工的 AC(AC2-4 / 11 / 13-15)
    - (b) 调 `verification-before-completion` skill 跑过,每条 AC 的"AI 验证"列都有命令输出证据
  - Depends on:T25

---

## 任务依赖图

```
T1 (mapping) ──┬─► T7 ──► T8 ──► T9 ──► T10 ──► T11 ──► T12 ──► T13 ──► T14 ──► T15 ─┐
T2 (few-shot) ─┤                            ▲                                          │
T3 ──► T4 ──► T5 ──► T6 ─────────────────────┘                                         │
                                                                                       │
T16 ◄─────────────────────────────────────────────────────────────────────────────────┘
  │
  └─► T17 ─► T18 ─► T19 ─► T20 ─► T21 ─► T22 ─► T23 ─► T24 ─► T25 ─► T26
```

## Commit 映射

- T1-T26 实现时:`task-TX: <短描述>`
- Stage 8 发现 bug 修复:`fix(TX): <bug 描述>`
- Phase 完成时阶段产出:`stage-7: Phase N (TX-TY) 完成`(可选,大批量时用)

## 估算

- Phase 1-2(T1-T6):~ 1-2 天(可并行)
- Phase 3(T7-T13):~ 3-4 天(核心实现 + 测试)
- Phase 4(T14-T15):~ 半天 + 用户主观 review
- Phase 5(T16-T17):~ 0.5 天(AI 提案 + 用户审稿)
- Phase 6(T18-T21):~ 1 天 + 用户 regen review 1-2 小时
- Phase 7(T22-T23):~ 0.5 天(跑 20 figure + 验证)
- Phase 8(T24-T26):~ 0.5 天

**总:8-10 工作日**(包含用户人工 review 卡点);实际 LLM 跑全 70 figure 约 2 小时(含 sleep)

---

## 用户确认

- ⬜ **等待确认**
- ⬜ **已确认** — 确认时间:______ ｜ 备注:______

> 一旦确认,本清单成为 Stage 7 的进度追踪单位。改范围请显式回到本阶段。
