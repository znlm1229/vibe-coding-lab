# SPEC Template (Stage 4)

> Aligned with workflow-spec **v1.2** — adds AC dual-channel verification + OQ type marking.

The SPEC describes **what** will be built, never **how**. It is the contract that Stage 9 (Acceptance) checks the finished work against, so every part of it must be concrete enough to verify.

Use this exact structure:

```markdown
# SPEC: [Feature / system name]

## Summary
One or two sentences. What is this and who is it for.

## Problem
What problem does this solve. Why now. What happens if we don't build it.

## Goals
The specific outcomes this work must achieve. Each goal should be observable.

## Non-goals
What this work explicitly does NOT cover. This section prevents scope creep
and is as important as the Goals section — be generous with it.

## Behavior
The expected behavior in concrete terms:
- Inputs: what goes in, in what form
- Outputs: what comes out, in what form
- Key flows: the main paths a user or caller takes
- Edge cases: known boundary conditions and how they should behave
- Error handling: what should happen when things go wrong

## Constraints
Hard limits the solution must respect — performance budgets, compatibility
requirements, security or compliance rules, deadlines, dependencies that
can't change.

## Open questions

Each OQ MUST carry a **type** field — `technical` or `taste`. (v1.2)

| # | 问题 | 类型 | AI 推荐 | 决定 | 备注 |
|---|---|---|---|---|---|
| OQ1 | 联系邮箱用 X 还是 Y | technical | Y（理由） | (待用户) | |
| OQ2 | 站点 hero 文案 | taste ⚠️ | 占位草稿 | (待用户) | AI 起草仅占位，用户应自行替换 |

- `technical` = 有客观正确答案，AI 给推荐 + 用户拍板即可
- `taste` = 主观偏好（文案、配色、命名风格），AI 推荐**只是占位**，必须显式提示"用户应自己改写"
  以防"接受 AI 推荐 → AI 起草内容 → 用户后悔重写"的反复成本

## Acceptance criteria

每条 AC 必须显式两栏：**AI 如何验证 / 人工如何验证**。两边都 PASS 才算 PASS。(v1.2)

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC1 | URL 返回 200 | `curl URL` → HTTP 200 | 浏览器访问能打开 |
| AC2 | 邮箱链接可用 | grep HTML 不含 `xxx@xxx.xxx` ✓ | 浏览器点击邮箱，邮件客户端弹出且收件人正确 |
| AC3 | 暗黑切换 | grep theme-btn 存在 | 点击按钮切换主题 + 刷新仍保持 |

Good:   "A logged-out user visiting /dashboard is redirected to /login."
Bad:    "Authentication works well."

Good:   "p95 response time for the search endpoint is under 200ms with 10k records."
Bad:    "Search is fast."

Each criterion should be checkable by someone who did not build the feature.
```

## Writing testable acceptance criteria

The single most important part of the SPEC. A criterion is testable when two different people checking it would reach the same verdict.

- State a **condition** and an **expected result**, not a quality adjective.
- Prefer observable behavior ("the file appears in the list") over internal state ("the cache is updated") unless the internal state is the deliverable.
- Make each criterion independent — one criterion, one thing to check.
- Quantify anything quantifiable — counts, times, sizes, limits.
- If a criterion can't be made testable, it probably belongs in Goals or Behavior as context, not in Acceptance.

### AC 双通道验证约定（v1.2）

每条 AC 必须同时定义 **AI 验证路径** 和 **人工验证路径**：

- **AI 验证路径**：字符级 / 结构级检查 —— `grep` / `curl` / build output / 文件存在等。可被脚本化。
- **人工验证路径**：浏览器交互、视觉判断、UX 体感、点击触发、文案审美。需要真人在浏览器 / 设备上实际操作。

**核心原则**：**如果一条 AC 写不出人工验证路径，它通常不够"行为化"，改 AC 而不是省略人工通道**。

为什么这条规则存在：AI grep 检查通过 ≠ 用户体验通过。本仓库 personal-website 任务 001 的 EmailLink bug 就是教训——AC10「HTML 不含明文邮箱」AI 字面 PASS，但用户面前的邮箱链接完全坏（脚本没加载）。详见 specification §6「字面 AC vs 行为 AC 脱节」失败模式。

## Keeping the SPEC honest

The SPEC is a hard gate. Present it to the user and wait for explicit confirmation before moving to Plan. If during later stages the SPEC turns out to be wrong or incomplete, return here, change it visibly, and get re-confirmation — never let the implementation quietly diverge from the written SPEC.

每次 SPEC 修订（包括小的命名层 patch）都应：
- 在 SPEC 末尾「修订日志」节加版本条目（v1.0 → v1.0.1 → v1.0.2 → ...）
- 写明触发、变更范围、理由
- **如果是行为层变更**：必须重新触发用户确认
- **如果仅命名层 / URL 层 patch**：可在 commit 中显式说明，不必重新走完整确认流程，但仍必须可追溯
