# Plan & Tasks (Stages 5 and 6)

> Aligned with workflow-spec **v1.2** — adds commit conventions including `fix(TX):` for Stage-8 回路.

## Stage 5: The Plan

The Plan answers **how** and **in what order** — it turns the confirmed SPEC into a technical route. Where the SPEC is the destination, the Plan is the path.

Use this structure:

```markdown
# Plan: [Feature / system name]

## Approach
The overall technical strategy in a few sentences. The key architecture
decision(s) and why this approach over the alternatives raised in Brainstorm.

## Phases
An ordered list of phases. Each phase is a meaningful, coherent chunk of
progress — not yet individual tasks. For each:
- What it delivers
- Why it comes where it does in the order

## Dependencies
What depends on what. Call out anything that blocks parallel work, anything
that touches shared/fragile code, anything that needs an external input.

## Risks
The parts most likely to go wrong, and how the plan mitigates them. If a
Prototype (Stage 3) settled a risk, note that here. Remaining unknowns get
flagged loudly.

## Test strategy
How the result will be verified — what gets unit tested, what gets
integration tested, and what is left for Human QA (Stage 8) because it
needs a person.
```

## Stage 6: The Tasks

Tasks break the Plan into individually completable work items. This is the **last cheap point to change scope**, and it's a hard human gate.

A good task:
- Is small enough to complete and verify on its own
- Could, in principle, be handed to a separate agent with just the SPEC and Plan as context
- Names what it touches (files, modules, surfaces)
- States its own "done" — usually one or two checkable conditions
- Is ordered relative to the others (dependencies respected)

Use this structure:

```markdown
# Tasks: [Feature / system name]

- [ ] **T1 — [short name]**
  Touches: [files / modules]
  Done when: [checkable condition]
  Depends on: [other tasks, or "nothing"]

- [ ] **T2 — [short name]**
  Touches: ...
  Done when: ...
  Depends on: T1
```

## Task sizing guidance

- If a task's "done when" needs more than two conditions, it's probably two tasks.
- If you can't say what files a task touches, the Plan isn't detailed enough yet — go back.
- If a task can't be verified without first completing three other tasks, the ordering or the breakdown is wrong.
- Prefer more, smaller tasks over fewer, larger ones — small tasks make Implementation progress visible and reviewable.

## Using the task list in Implementation

Once the user confirms the task list, it becomes the unit of progress tracking for Stage 7. Work through it in order, complete one task at a time, and mark each task done as you finish it — keeping the list a live, accurate picture of where things stand. Map commits to tasks so the diff stays reviewable.

## Commit conventions (v1.2)

每个 commit 必须明确归属——是新 task 工作、阶段产出、还是 bug 回路修复：

| 前缀 | 用于 | 例 |
|---|---|---|
| `task-TX:` | 新 task 的首次实现 | `task-T5: implement EmailLink obfuscation component` |
| `stage-N:` | 阶段转换、artifact 提交、确认动作 | `stage-4: SPEC confirmed; OQ1-4 resolved` |
| `fix(TX):` | 已完成 task 的 bug 修复（通常来自 Stage 8 回路） | `fix(T5): EmailLink script never runs under ClientRouter` |
| `chore:` | 仓库治理、依赖、配置修改（非业务 task） | `chore: pin pnpm@10.11.1 for CF Pages compat` |
| `docs:` | 仅文档改动 | `docs: align spec template with v1.2` |
| `spec(vX.Y):` | workflow-spec 自身的版本演化 | `spec(v1.2): add 4 stage-skill bindings` |

**为什么 `fix(TX):` 重要**：把 bug 修复回路从 task 首次实现里分出来，git 历史能诚实反映"实现一次、修一次"的迭代真相，方便后续做 task 复盘 / 回归分析 / 估算下次类似 task 的实际工时（首次 vs 回路）。

## 任务 done-when 包含验证证据（v1.2）

每个 task 的 "Done when" 不能只写「功能实现了」这种主观断言，必须能跑出验证证据：

- ✅ Good: `pnpm build` 通过 + 新页面 `/projects/<slug>/` 返回 200 + 截图见 evidence/
- ❌ Bad: 项目卡片实现完成 / 功能正常 / 看起来不错

进入 Stage 8 之前，**必须调 `verification-before-completion` skill**（v1.2 强制）核对每个 task 的 done-when 都有对应证据。AI 自己说"完成"不算。

