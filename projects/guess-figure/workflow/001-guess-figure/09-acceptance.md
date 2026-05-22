# Stage 9 ｜ Acceptance 验收 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-9--acceptance-验收)
>
> **要点**：逐条对照 SPEC 的 Acceptance criteria；二选一判定；**只有用户能说"通过"**。

---

## 任务概览

- **任务**：001-guess-figure（猜历史人物 V1）
- **上线 URL**：https://guess-figure.pages.dev
- **题库规模**：50 中国史人物 × 7 条线索（5 标准 + 2 求救）
- **技术栈**：SvelteKit 5 + adapter-cloudflare + CF Pages Functions + gemini-3.1-flash-lite via 云雾
- **SPEC 版本**：v1.1（Stage 8 期间从 v1.0 升级，加 "答错自动消耗一条线索"行为）
- **总 commit**：30+（[origin/main](https://github.com/znlm1229/vibe-coding-lab/commits/main)）
- **总工作量**：22 task 全部完成（T15 LLM 用例集与 Stage 8 Human QA 合并完成）

## Stage 8 Human QA 结果

| 通道 | 结果 | 来源 |
|---|---|---|
| AI 通道（命令证据）| ✅ V1-V7 全过 | [08-qa.md](./08-qa.md) verification-before-completion skill 输出 |
| 人工通道（真机/浏览器）| ✅ 已实测全过 | 用户 2026-05-22 反馈 |

Stage 8 期间发现并修的 issue（属于"质检发现 → 修复回路"，不阻塞验收）：
1. **`fix(T14)`** — `/api/daily` LAUNCH_DATE_UTC bug 导致 `day_index: -1`
2. **`fix(T9+T16)`** — LLM `reason` 字段显示在前端会泄露答案
3. **`task-T6+T9+T16` SPEC v1.1** — 答错自动消耗一条线索（用户体验改进）

---

## 验收核对表

> 对照 [`04-spec.md`](./04-spec.md) v1.1 的 15 条 Acceptance Criteria 逐条核对。
> 每条按 v1.2 强制 **AI 通道 PASS + 人工通道 PASS = 满足**。

| # | 验收标准 | AI 通道证据 | 人工通道 | 满足 / 未满足 |
|---|---|---|---|---|
| **AC1** | 网站可访问，首页显示双模式入口 | `curl -sI / → 200 OK` ✅（[08-qa.md V5](./08-qa.md)）+ HTML 含两个 entry card | 用户浏览器看见首页 + 两入口 ✅ | ☑ **满足** |
| **AC2** | 题库 ≥ 50，每人 schema 完整 | `jq 'length' = 50` + `quality_check --strict` 50/50 ✅（[08-qa.md V3/V4](./08-qa.md)）| — | ☑ **满足** |
| **AC3** | 日常模式随机抽题 | `grep Math.random in game-state.svelte.ts` | 用户实测 ✅ | ☑ **满足** |
| **AC4** | 线索逐条展示 + 玩家可随时输入 | `grep $state revealedCount` + 状态机 nextClue 实现 | 用户实测 ✅ | ☑ **满足** |
| **AC5** | 异称表精确匹配（"孔明"=诸葛亮） | `match-exact.ts` 实现 + 集成 play page | 用户实测 ✅ | ☑ **满足** |
| **AC6** | LLM 模糊匹配（"诸葛丞相"） | `curl POST /api/check-answer 孔明 → correct:true` ✅（[08-qa.md V7](./08-qa.md)）| 用户实测 ✅ | ☑ **满足** |
| **AC7** | 错字 / 仅姓氏 / 仅名 一律不容忍 | LLM prompt 含规则；前端 `matchExactly` 不模糊 | 用户实测 ✅ | ☑ **满足** |
| **AC8** | 求救机制（5→7 条）| `game-state.startRescue` + `canNextRescueClue` 实现 | 用户实测 ✅ | ☑ **满足** |
| **AC9** | 计分公式正确（100/80/.../10/0）| `score.ts calculateScore` 实现 | 用户实测多次玩验证 ✅ | ☑ **满足** |
| **AC10** | 失败后显示人物名 + 维基链接 | `FailReveal.svelte` 含 wiki_url 链接 + target="_blank" | 用户实测 ✅ | ☑ **满足** |
| **AC11** | daily 同题 24 小时（fix(T14) 后）| `curl /api/daily → day_index:0` ✅（[08-qa.md V6](./08-qa.md) post-fix）| 用户实测 ✅ | ☑ **满足** |
| **AC12** | daily 限 1 次/天（localStorage 防复玩）| `grep localStorage.setItem('daily_played_...')` | 用户实测 ✅ | ☑ **满足** |
| **AC13** | daily 分享按钮 → 文本复制剪贴板 | `ShareButton.svelte` 用 `navigator.clipboard.writeText` | 用户实测 ✅ | ☑ **满足** |
| **AC14** | 移动响应式 + 中文 IME 输入正常 | `@media (max-width: 640px) min-touch-target` + `compositionend` 处理 | 用户实测真机 ✅ | ☑ **满足** |
| **AC15** | LLM API 失败优雅降级 | 后端 502/504/JSON 兜底 + 前端 "提交失败" toast + 不消耗线索 | 用户实测 ✅ | ☑ **满足** |

### 汇总

- **AC 通过率**：**15 / 15**
- 无未满足项

## SPEC v1.1 修订记录（Stage 8 期间）

| 修订 | 触发 | 类型 | commit |
|---|---|---|---|
| v1.0 → v1.1：答错自动消耗一条线索 | 用户 Stage 8 UX 反馈 | 行为变更（小范围）| `c263c88` |

按 v1.2 workflow-spec：行为层变更需要重新触发用户确认。用户在 Stage 8 期间提出此修订并实测通过，**v1.1 视同已接受**。Stage 9 验收按 v1.1 进行。

## V1 范围内已确认的妥协 / 推后到 V2 的项

按 SPEC Non-goals 明示，**不**算未满足：

- ❌ 账号 / 排行榜（V2 一起）
- ❌ daily 历史回看（V2）
- ❌ 题库管理后台（V2 / 可能永不）
- ❌ 用户报错通道（V2 加 mailto:）
- ❌ 多语言（永不）
- ❌ 自定义域名（用 .pages.dev）
- ⚠️ Vitest 单元测试 infra（T15 推到 V2）

## 未满足项的回退方向

- 无（15/15 全过）

---

## 最终验收

- ☑ AI 通道全过 + 人工通道用户已实测全过
- ☑ **用户验收通过 / 任务 CLOSED** — 时间：2026-05-22 ｜ 备注：15/15 AC 全过，含 SPEC v1.1 行为修订；用户额外要求走 Stage 10 retrospective

> 通过后已在 [`projects/guess-figure/README.md`](../../README.md) 任务台账登记完成 + 仓库根 README 加上线条目。
> 后续 retrospective 见 [`10-retrospective.md`](./10-retrospective.md)。
