# SPEC: 003 — 线索优化 (pipeline + 内容质量 + 题库扩 70)

> Stage 4 ★ 人工关卡。标准模板见 [`spec-template.md`](../../../../workflow-spec/references/spec-template.md)
>
> **v1.2 约定**:AC 双通道 + OQ 标 type。**用户未确认前不得进入 Stage 5**。

**版本**: v1.0.1(用户 2026-05-26 已确认 v1.0,OQ4 patch)

---

## Summary

重生成现有 50 figure 的 7 条线索 + 新增 20 皇帝(题库 50 → 70),走升级后的内容生产 pipeline:**三源材料(维基中文全文 + Wikidata + 二十四史)→ 强 LLM 产结构化人物画像 → flash-lite 产 clues → flash-lite judge 自动循环重试**。

## Problem

现有 V2 题库(50 figure × 7 clue)质量问题已被 prototype 与人工抽样多重证实:

- **语义穿底**:乾隆 d1「暮年自诩拥有十项武功」≈ alias「十全老人」(字符级 grep 漏)
- **子串穿底**:关羽 d7「字云长,河东解人」⊂ alias「关云长」(d6/d7 没禁子串)
- **直接穿底**:刘备 d7「谥号为昭烈,庙号烈祖」直接给 aliases「汉昭烈帝/昭烈皇帝/烈祖」
- **标志事件穿底**:刘备 d2「以织席贩履为业,与两位结义兄弟」(d2 应远离)
- **难度梯度乱**:乾隆 d5「清朝入关后的第四位统治者」比 d1 更易猜
- **pipeline 信息饥饿**:老 pipeline 单步 LLM 用 1000 字材料,无法支撑梯度精细化
- **校验失明**:`quality_check.py` 5 项全字符级,语义穿底完全抓不到

不动手会怎样:对长期玩家,V2 题库 ≈ 半小时可全部记忆(50 人 × 7 提示),游戏成"考记忆"而非"猜谜"。本任务是 V2 → V3 内容质量阶跃。

## Goals

1. 重生成 50 现有 figure,新版 quality_check (升级版 6 项规则 + LLM-as-judge 第 7 项)在新 figures.json 上的满分率 ≥ 90%
2. 新增 20 个皇帝 figure 走新 pipeline 入题库 (题库 50 → 70)
3. d1/d2/d3 显著加难 — 主观抽样 10 局,**≥ 7 局**需打开 d4 或以上才猜出来;同时 **d6-7 救命 ≤ 7 局**(d4-5 应是"甜点")
4. 总 LLM 成本 ≤ ¥10
5. 新数据资产:`src/lib/data/profiles/*.md` × 70 入 git
6. 内容质量不退化:个体回退机制保证 figures.json 是 v1+v2 混合
7. 上线后玩家(用户本人)实测体验"明显比之前耐玩"

## Non-goals

- ❌ 不动游戏机制(5+2 求救分法、计分公式 `(6-N)*20`、答错自动消耗 — 002 SPEC v1.1 行为不变)
- ❌ 不动前端 (`src/routes/play/`、`src/routes/daily/`、`+page.svelte`、`AnswerInput.svelte`、`FailReveal.svelte`)
- ❌ 不动游戏状态机 (`src/lib/game-state.svelte.ts`)
- ❌ 不动 figures schema(`src/lib/types.ts` 的 `Figure / Clue` interface 不变)
- ❌ 不动 D1 schema、KV namespaces、wrangler.toml、auth、rate-limit、llm-cache
- ❌ 不扩 Wikidata 字段(prototype 证实现有 6 字段已够,扩 15 是 over-engineering)
- ❌ 不接百度百科 / CN-DBpedia(反爬复杂 / ROI 低)
- ❌ 不扩题库到 V2 200 人(留 006)
- ❌ 不实现 A/B 灰度上线(留 005)
- ❌ 不实现"动态游戏内 LLM 出题"(题库始终静态 JSON)

## Behavior

### Inputs

- `figure_name`:中文人物名(如「诸葛亮」)
- `strong_llm_model`:强 LLM model id(默认 `deepseek-v3.2`,可换 `claude-haiku-4-5-20251001`)
- `history_index.json`:`{ figure_id: { wikisource_page, is_合传, extract_pattern? } | null }`(70 entry)
- `few_shot_examples.md`:好/坏对比示例池(初始 5 好 + 5 坏,AI 提案 → 用户审稿入库)

### Outputs(per figure)

- `src/lib/data/profiles/{figure_id}.md` — 8 sections 结构化画像(强 LLM 产)
- `src/lib/data/figures.json` 对应条目 — 7 条 clues + aliases(schema 不变,与 V1/V2 兼容)
- 失败时:`scripts/data/failed_figures.json` 记录该 figure + 失败原因,不写入 figures.json

### Key flows

```
[1] fetch 三源材料:
    - 维基中文 page.text 截 5000 字 (现 1000 字 → 5000 字)
    - Wikidata 6 字段 (现有不变 — prototype 证实够)
    - 二十四史 Wikisource page (按 history_index.json 查 mapping, 简单清 markup, 截 5000 字)
      - mapping=null → fallback 仅前两源
[2] 强 LLM (deepseek-v3.2) build_profile:
    - 输入: 三源材料拼接 + PROFILE_PROMPT (8 sections schema)
    - 输出: profile markdown
    - check: regex 验证 8 个 section header 都齐 → 否则重试 1 次 → 否则 figure 标 failed
    - 写入 profiles/{figure_id}.md
[3] flash-lite (gemini-3.1-flash-lite) clues_from_profile:
    - 输入: profile + 从 profile typology+作品 section regex extract 的 banlist + few-shot 反例 + 难度规则
    - 输出: { name, aliases, clues:[{text,difficulty}×7] } JSON
[4] flash-lite judge:
    - 输入: aliases + profile typology+作品 section + 7 clues + JUDGE_PROMPT (区分 d1-5 vs d6-7 规则)
    - 输出: { verdicts: [{d, verdict:"合规"/"可疑"/"违规", reason}] }
[5] 重试循环:
    - 任意 verdict="违规" 且重试 < N=2:
      - inject 上次违规反馈 (negative example) 回 [3]
    - 重试 N 次仍违规 → 标 failed, 不入 figures.json
[6] 写入 figures.json:
    - 新版 figure 暂存 figures.v2-candidates.json
    - 70 figure 跑完后, 自动 vs 人工 review 决定哪些写入最终 figures.json
```

### Edge cases

- **维基中文无该人物**:跳过 figure,记 skipped(沿用现 generate_figures.py)
- **Wikidata 搜不到**:用 wiki + 空 wikidata 字段继续
- **二十四史 mapping=null**(鲁迅 / 孙中山 / 部分李清照):fallback 仅维基 + Wikidata
- **强 LLM 是 thinking model**:detect `reasoning_tokens > 0 且 content 空` → 报错 exit(防 gemini-2.5-pro 类失败)
- **profile 缺 section**:regex 验证 8 个 header 齐;缺则重试 1 次后标 failed
- **profile/clue/judge JSON parse 失败**:重试 1 次后标 failed
- **judge 自身误判率**:人工抽样发现 > 15% 误判 → 调 judge prompt(SPEC v1.0.1 patch)
- **figure 重生成质量不如旧版**:auto-vs-人工 review 流程保留旧版条目
- **figure 名字被改**(如「陶渊明」→「陶潜」):**禁止**,保持 id 与现有 figures.json 一致

### Error handling

- LLM API 失败 → 现有 `call_llm_with_retry` 重试(max-retries 2,指数退避)沿用
- 整 batch 中断 → 增量保存机制(现有)沿用
- LLM 成本超 ¥10 硬上限 → abort + 人工 review(防成本失控)

## Constraints

### 技术栈(不变)

- Python 3.13 + `projects/guess-figure/venv/`
- requests / wikipediaapi / python-dotenv(无新 deps)
- 云雾 OpenAI 兼容 API(`YUNWU_API_KEY` + `YUNWU_BASE_URL`)
- `gemini-3.1-flash-lite`(flash 用途:clue 生成 + judge)
- **新引入**:强 LLM 候选 — `deepseek-v3.2`(主) / `claude-haiku-4-5-20251001`(备用)

### 成本

- 总 LLM 成本 **硬上限 ¥10**(超过 abort)
- 单 figure 估算:deepseek 主路径 ~¥0.05 + flash clue/judge + 重试 buffer ≤ ¥0.15
- 70 figure × ¥0.15 = ¥10.5 上限(覆盖最坏)

### Build / runtime

- 单 figure 端到端 < 90s
- 70 figure 全量跑总耗时 < 2 小时(含 sleep 1s 礼貌 cool down)

### 数据

- `profiles/*.md` × 70 入 git,total ≤ 5MB
- `figures.json` 部署体积 < 1MB(~14KB × 70)
- 旧 `figures.json` 重命名为 `figures.v1.json` 保留(同入 git)

### Pipeline 强约束(基于 prototype 教训)

- 强 LLM 候选必须 **排除 thinking model**(`reasoning_tokens > 0 + content 空` 视为不可用)
- clue prompt **必须 inject banlist**(从 profile typology + 关键作品 section regex extract)
- judge prompt **必须区分 d1-d5 vs d6-d7**:
  - d1-d5:禁 banlist + 禁 aliases 子串
  - d6-d7:允许 banlist,仍禁 aliases 子串
- 所有 Python 脚本顶部加 `sys.stdout.reconfigure(encoding="utf-8")`
- prompt 第一行用 system role,主指令用 user role

### Compliance

- Wikipedia / Wikisource API 遵守 robots.txt + User-Agent(沿用 `guess-figure/0.1`)
- 不爬反爬源
- LLM 输出仅历史人物公开信息

### 兼容性

- `figures.json` schema 不变,前端 zero-break
- 现有单元测试 54 个不需改

## Open Questions

| # | 问题 | 类型 | AI 推荐 | 决定 | 阻塞节点 | 备注 |
|---|---|---|---|---|---|---|
| OQ1 | 强 LLM 具体型号 | technical | **deepseek-v3.2** 主选(prototype 验证质量 = haiku 且成本 1/4);claude-haiku-4-5-20251001 备用 | (待) | Stage 7 实现前 | prototype 已排除 thinking model |
| OQ2 | judge 用哪个模型 | technical | `gemini-3.1-flash-lite` 自审 | (待) | Stage 7 | flash judge 已 work,但需精化 prompt(见 OQ14) |
| OQ3 | 自动 judge 循环最多重试 N | technical | **N=2** | (待) | Stage 7 | N=1 已可降 d4-5 违规率;N=2 兜底罕见 case |
| OQ4 | 20 皇帝具体候选清单 | taste ⚠️ | (见 [`spec-emperor-list.md`](./spec-emperor-list.md)) | **✅ 用户 2026-05-26 全部通过 20 名** | Stage 7 实现前 | spec-emperor-list.md 定稿:刘秀/刘协/拓跋宏/杨坚/杨广/李治/李隆基/李纯/柴荣/赵祯/赵佶/赵构/耶律阿保机/完颜阿骨打/朱棣/嘉靖/万历/崇祯/雍正/道光 |
| OQ5 | 灰度先跑哪 5 个 figure | taste ⚠️ | 乾隆 / 关羽 / 刘备 / 李白 / 苏轼(3 个有问题的 + 2 个本来好的诗人) | (待) | Stage 7 灰度前 | 用户可改 |
| OQ6 | LLM N 次重试后仍失败的 figure 处理 | technical | 标 failed → 写入 failed_figures.json → 不入 figures.json;人工兜底(直接编辑旧版条目入 figures.json) | (待) | Stage 7 | 估算 < 5 个 / 70 |
| OQ7 | 旧 figures.v1.json 是否 deploy | technical | 否,仅 deploy 新版;v1 留 git 历史 | (待) | Stage 7 部署前 | 减少部署体积 |
| OQ8 | profile 文件命名 | technical | `profiles/{id}.md`(id = name.lower(),中文人物 id = 中文) | (待) | Stage 7 | prototype 已验证 Windows + git 中文文件名 OK |
| OQ9 | 二十四史拉取上限字数 | technical | 5000 字 | (待) | Stage 7 | 超过则截前 4000 + 论赞结尾 1000 |
| OQ10 | profile 「典故/作品」section regex extract 算法 | technical | `^##\s+(典故 \\/ 标志事件\|关键作品)\s*\n((?:[-*]\s*.+\n?)+)` | (待) | Stage 7 | prototype 验证 work |
| OQ11 | profile schema 是否带 yaml frontmatter | technical | 否,纯 markdown 8 sections | (待) | Stage 7 | 后续如需 metadata 再加 |
| OQ12 | few-shot pool 初版内容 | taste ⚠️ | `scripts/few_shot_examples.md`,5 好 + 5 坏 由 AI 提案、用户审稿入库 | (待) | Stage 7 实现前 | 用户必须审,内容主观 |
| OQ13 | clue prompt 是否 inject banlist | technical | **是**(prototype 暴露:不塞时 LLM 控制不住 d4-d5) | (待) | Stage 7 | 强约束已写入 Constraints |
| OQ14 | judge prompt 的 d6/d7 规则修正 | technical | "d1-d5 禁 banlist + aliases 子串;d6-d7 允许 banlist 但仍禁 aliases 子串" | (待) | Stage 7 | 强约束已写入 Constraints |
| OQ15 | Wikidata 字段范围 | technical | **保持现有 6 字段**(prototype 证实够) | (待) | Stage 7 | brainstorm 中"扩 15"已废弃 |

## Acceptance Criteria

> 每条 AC 双通道(AI 验证 + 人工验证),两边都 PASS 才 PASS。Stage 9 逐条核对。

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| **AC1** | `scripts/generate_figures.py` v2 重写为 3 步 pipeline(build_profile + clues_from_profile + judge_clues + 自动重试循环) | 1) `git log --diff-filter=M -- scripts/generate_figures.py` 有 stage-7 commit;2) `grep -c "def build_profile\|def clues_from_profile\|def judge_clues" scripts/generate_figures.py` ≥ 3 | 用户读 generate_figures.py,3 个步骤函数 + 循环逻辑清晰 |
| **AC2** | 二十四史 mapping table 已生成且通过 spot check | 1) `scripts/data/history_index.json` 存在;2) `jq 'length' history_index.json` = 70;3) `jq '[.[] \| select(. != null)] \| length' history_index.json` ≥ 55(覆盖率 ≥ 80%) | 用户随机抽 5 个 mapping(如「李白」→「新唐書/卷202」),浏览器访问对应 Wikisource page 存在 + 该人物本传所在 |
| **AC3** | 题库新增 20 个皇帝 figure(总 50→70) | 1) `jq 'length' figures.json` = 70;2) 用 `jq '[.[] \| select(._meta.generated_at >= "2026-05-25")] \| length' figures.json` ≥ 20(本任务期间新增的至少 20 个) | 用户读 figures.json 中新增的 20 个 figure name,确认:朝代覆盖均衡(每朝代 1-3)+ 都是皇帝身份 + 不与现 50 已有皇帝重复 + 知名度 tier 1-2 |
| **AC4** | `src/lib/data/profiles/` × 70 个 .md 入 git,每个 8 sections 齐 | 1) `ls src/lib/data/profiles/*.md \| wc -l` = 70;2) 每个 .md `grep -c "^## "` ≥ 8 | 用户随机打开 5 个 profile.md,8 sections 完整且符合该人物身份 |
| **AC5** | 升级版 `quality_check.py` 新增 3 项规则(d6/7 alias 子串、典故 banlist、信息密度启发式) + 1 项 LLM judge | 1) `python scripts/quality_check.py figures.json --verbose` 输出含 4 个新检测项的 verdict | 用户读 quality_check.py 源码,4 项实现且可跑通 |
| **AC6** | 70 figure 新版 quality_check 满分率 ≥ 90% | 1) `python scripts/quality_check.py figures.json --strict` 输出"✅ 满分: ≥ 63/70" | 用户读输出,确认满分率 ≥ 90% |
| **AC7** | 单 figure pipeline 端到端 < 90s | 1) spot check 5 个 figure 的 `cost.json` 中 `total_latency_s < 90` | 用户跑 1 个 figure `time python scripts/generate_figures.py --names 苏轼`,real 时间 < 90s |
| **AC8** | 70 figure 总 LLM 成本 ≤ ¥10 | 1) 跑完后 `scripts/data/cost_summary.json` 汇总成本 ≤ ¥10 | 用户读 cost_summary.json |
| **AC9** | 70 figure 中 failed 数 ≤ 5 | 1) `jq 'length' scripts/data/failed_figures.json` ≤ 5 | 用户读 failed_figures.json,每个 failed 有理由 + 总数 ≤ 5 |
| **AC10** | 旧 figures.json 备份为 figures.v1.json 入 git | 1) `ls src/lib/data/figures.v1.json` 存在;2) `git log -- src/lib/data/figures.v1.json` 有 stage-7 commit | 用户 diff 旧 vs 新,确认旧版安全保留 |
| **AC11** | regression 兜底(**仅针对 50 旧 figure**):自动 + 人工 review,v2 不如 v1 的条目保留 v1 | 1) `scripts/data/regen_diff.md` 存在,逐 figure(50 旧)列 v1 vs v2 score + 违规数对比;2) 独立脚本输出"v2 采用 X 个 / v1 保留 Y 个 / X+Y=50" | 用户打开 regen_diff.md,review 自动标"候选采用"的子集,accept/reject 后产 final figures.json(50 旧 = v1+v2 混合,加 20 新皇帝 = 全 v2) |
| **AC12** | 上线后 figures.json 正确部署,前端 zero-break | 1) `npm run build` 成功;2) build 后 figures.json 出现在 `.svelte-kit/output/`;3) 现有 54 个 .test.ts 全 pass | 用户访问 [guess-figure.pages.dev](https://guess-figure.pages.dev) play 5 局,figure 加载、可猜、求救、放弃流程通 |
| **AC13** | d1/d2/d3 显著加难 — 主观抽样 10 局,**≥ 7 局**需打开 d4+ 才猜出 | 1) (无 AI 验证 — 主观行为) | 用户实测玩 10 局(每局换 figure),记 d4+ 才猜出 ≥ 7 次 |
| **AC14** | d6-7 救命占比 ≤ 70% | 1) (无 AI 验证 — 主观行为) | 同 AC13 的 10 局,d6-7 才猜出 ≤ 7 次 |
| **AC15** | 上线后玩家(用户本人)实测"明显比之前耐玩" | 1) (无 AI 验证 — 主观体感) | 用户连玩 ≥ 20 局后,主观觉得"比 V2 旧版有意思"(对比 002 上线后体感) |
| **AC16** | 不破坏游戏机制(5+2 / 计分 / 答错消耗) | 1) `git diff main..HEAD -- src/lib/game-state.svelte.ts src/routes/play/+page.svelte src/routes/daily/+page.svelte src/lib/types.ts` 输出为空 | 用户上线后实测玩,行为与 002 上线版一致 |
| **AC17** | 强 LLM thinking model 防御机制 work | 1) `grep "reasoning_tokens" scripts/generate_figures.py` ≥ 1(实现 detect);2) 单测覆盖该 case | 用户故意指定 `gemini-2.5-pro-thinking-*` 跑,脚本应报错 exit 而非静默产空 |
| **AC18** | clue prompt inject banlist 行为正确 | 1) `grep -A 3 "banlist" scripts/generate_figures.py` 在 clues_from_profile 函数中出现;2) 单测覆盖 banlist 注入路径 | 用户跑 1 figure,看到生成的 d1-d5 clue 不含 profile「典故/关键作品」section 中的词 |

---

## 修订日志

### v1.0(2026-05-25,初版)

- 基于 Stage 1 brainstorm v3 + Stage 2 grill-me 5 轮决议 + Stage 3 prototype 验证
- 18 项 AC,涵盖 pipeline 重构 / 70 figure / 数据资产 / 防 regression / 兼容性 / 主观行为 6 大类
- 15 项 OQ(3 个 taste 标"用户应自己改";其余 technical 标 AI 推荐)
- 关键约束:强 LLM 主选 deepseek-v3.2、排除 thinking model、clue prompt inject banlist、judge prompt 区分 d1-5 / d6-7

### v1.0.1(2026-05-26)

- **OQ4 finalize**:T16 AI 提案 20 皇帝 → T17 用户审稿"全部通过"。`spec-emperor-list.md` 入 SPEC,`history_index.json` 加 20 entry(总 70)
- 命名风格:唐前+宋元用本名,明嘉靖/万历/崇祯+清雍正/道光用年号

### v1.0.x 后续可能 patch

- v1.0.2:OQ12 (few-shot pool 初版内容) 用户审稿后入库
- v1.0.x:若 deepseek 实际产出有大量退化,改主选为 claude-haiku-4-5-20251001
- v1.0.x:T14 灰度 fix prompt 调优(profile aliases ≤ 5,judge d6/d7 整字放可疑) — 已在 git history,后续若有更多 prompt iteration 在此记录

---

## 用户确认

- ☑ **已确认** — 确认时间:2026-05-25 ｜ 备注:用户回复 "SPEC 通过",18 AC + 15 OQ(3 taste 留 v1.0.1 patch)全部认可,准入 Stage 5 Plan

> 本 SPEC v1.0 即为契约。后续修改需显式重新确认(不允许静默漂移)。
>
> 已锁定的 unknowns 留作 SPEC patch:
> - v1.0.1: OQ4 20 皇帝候选清单
> - v1.0.2: OQ12 few-shot pool 初版内容
