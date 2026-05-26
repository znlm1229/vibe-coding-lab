# Stage 9 ｜ Acceptance 验收 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-9--acceptance-验收)
>
> **要点**:逐条对照 SPEC v1.0.1 的 18 项 Acceptance Criteria;二选一判定;**只有用户能说"通过"**。

**SPEC 版本**:[`04-spec.md`](./04-spec.md) v1.0.1(用户 2026-05-26 已确认)
**Stage 8 入场报告**:[`07-implementation.md`](./07-implementation.md)
**Stage 8 用户回复**:"通过"(2026-05-26)

---

## 验收核对表(18 项 AC)

| # | AC | AI 验证证据 | 人工验证证据(Stage 8) | 用户判定 |
|---|---|---|---|---|
| AC1 | generate_figures.py v2 重写 3 步 pipeline | grep build_profile/clues_from_profile/judge_and_retry = 3 ✓ | (Stage 8 用户未需手测代码结构) | ⬜ 满足 / ⬜ 未满足 |
| AC2 | history_index 70 entry,覆盖率 ≥ 80% | total=70, non_null=67 (95.7%) ≥ 80% ✓ | Stage 8 spot check 5 mapping(可补,推荐苏轼/杨坚/朱棣/道光/拓跋宏) | ⬜ 满足 / ⬜ 未满足 |
| **AC3** | 题库 70 entry | **65 / 70** ⚠️(5 新皇帝 v2 fail) | 用户 T15 已接受 65(commit `32c624e`)+ Stage 8 "通过" | ⬜ **满足(已 accept 偏差)** / ⬜ 未满足 |
| **AC4** | profiles/*.md × 70 | **69 / 70** ⚠️(刘协因 API 500 缺) | 与 AC3 关联,用户已 accept | ⬜ **满足(已 accept 偏差)** / ⬜ 未满足 |
| AC5 | quality_check 升级 4 项 | grep check #6/#7/#8/judge/extract_banlist = 10 matches ✓ | (Stage 8 用户未需手测代码) | ⬜ 满足 / ⬜ 未满足 |
| AC6 | 满分率 ≥ 90% | 62/65 = **95.4%** ≥ 90% ✓ | (Stage 8 用户未需手跑 quality_check) | ⬜ 满足 / ⬜ 未满足 |
| AC7 | 单 figure < 90s | 0/70 figure > 90s ✓ | (推断:跑 70 个 figure 总耗时 < 2 小时, Stage 8 不需手测) | ⬜ 满足 / ⬜ 未满足 |
| AC8 | 总成本 ≤ ¥10 | ¥2.61 ≤ ¥10 ✓ | (Stage 8 不需手测) | ⬜ 满足 / ⬜ 未满足 |
| **AC9** | failed ≤ 5/70 | **19 > 5** ❌(50 旧 14 有 v1 fallback + 5 新无) | Stage 8 用户 "通过" → 接受 spirit | ⬜ **满足(spirit OK,已 accept 偏差)** / ⬜ 未满足 |
| AC10 | figures.v1.json baseline 入 git | exists 127167 bytes, commit `8cd0e90` ✓ | (Stage 8 不需手测) | ⬜ 满足 / ⬜ 未满足 |
| AC11 | regen review 50 混合 | regen_diff.md 已生成,用户 T20 "全部按自动决策" → 31 v2 + 19 v1 ✓ | 用户 T20 已 sign-off | ⬜ 满足 / ⬜ 未满足 |
| AC12 | 部署 zero-break | npm test 66/66 pass + build exit 0 + push `c168b22..2bad7f7` ✓ | 用户 Stage 8 上线测,"通过" | ⬜ 满足 / ⬜ 未满足 |
| **AC13** | d1-3 加难:10 局 ≥ 7 需 d4+ | (无 AI 验证) | 用户 Stage 8 实测 "通过" | ⬜ 满足 / ⬜ 未满足 |
| **AC14** | d6-7 救命 ≤ 7/10 | (无 AI 验证) | 用户 Stage 8 实测 "通过" | ⬜ 满足 / ⬜ 未满足 |
| **AC15** | 玩 20 局比 V2 旧版耐玩 | (无 AI 验证) | 用户 Stage 8 实测 "通过" | ⬜ 满足 / ⬜ 未满足 |
| AC16 | 不破坏游戏机制 | git log 0a56e7b..HEAD -- types/game-state/routes → 0 commits ✓ | 用户 Stage 8 "通过"(游戏行为一致) | ⬜ 满足 / ⬜ 未满足 |
| AC17 | thinking model 防御 | grep "reasoning_tokens" = 4 (raise + 3 单测) ✓ | (Stage 8 不需手测) | ⬜ 满足 / ⬜ 未满足 |
| AC18 | clue prompt inject banlist | clues_from_profile signature 含 banlist + grep banlist=20 + 单测 ✓ | (Stage 8 不需手测) | ⬜ 满足 / ⬜ 未满足 |

---

## 已识别偏差(用户已接受,需在 sign-off 时确认)

| 偏差 | 字面 vs 实际 | 用户已接受 |
|---|---|---|
| AC3 题库 70 → **65** | 5 新皇帝 hard case 失败 | T15 "A 接受 65 GO" + Stage 8 "通过" |
| AC4 profiles 70 → **69** | 刘协 API 500 错误 | 同上 |
| AC9 failed ≤ 5 → **19** | 50 旧有 v1 fallback;5 新即 AC3 | Stage 8 "通过" → spirit |

**这些偏差在 Stage 9 sign-off 时被视为"已知接受偏差"**(用户在中途多次 explicit accept),不阻挡 003 完成。后续可在 006(题库扩展)中补 5 失败皇帝。

## 已识别遗留(留给后续任务)

1. **3 个 v1 旧 figure quality_check warning** — 张居正 d3 "考成法" / 李清照 aliases 数 2 / 武则天 d4 "神龙革命"。SPEC v1.0 没要求修;006 题库扩展时可一并处理。
2. **006 候选**:补 5 缺失皇帝(刘协 / 杨广 / 柴荣 / 万历 / 雍正)+ 扩到 200 人
3. **004 / 005**:邮箱 magic link / 排行榜 / 自定义域名(候选)

---

## 用户最终 sign-off

⬜ **003 验收通过** — 验收时间:______ ｜ 签字:______

> 通过则:
> 1. SPEC v1.0.1 → v1.1(标 "已 accept 3 项偏差")
> 2. README 任务台账标 003 为 ✅ 已完成
> 3. CLAUDE.md 项目状态更新到 V3
> 4. (可选)写 10-retrospective.md 复盘 003 全流程

⬜ **未通过 — 哪条 AC 不满足**:______ ｜ 要求 fix 范围:______

---

## 验收说明

按 workflow-spec §5 阶段 9:
- 验收对每条 AC 是**二元**(满足 / 未满足)
- 工作"完成"当且仅当用户同意每条标准都已满足
- 任何未满足项 → 路由回相应阶段(通常 Stage 7 Implementation)
- 不允许 AI 自我验收
