# Stage 7 ｜ Implementation 实现

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-7--implementation-实现)
>
> **要点**：按任务清单顺序；一次一个；commit 映射到 task；**发现 SPEC 缺口立即停下回 Stage 4**，不要静默偏离。
>
> **v1.2 强制约定**：
> - 进入 Stage 8 之前**必须调 `verification-before-completion` skill** 核对每条 AC 的 AI 验证证据
> - Bug 修复回路 commit 用 **`fix(TX):`** 前缀，不要复用 `task-TX:`

---

## 进度（与 [`06-tasks.md`](./06-tasks.md) 同步）

- [ ] T1 — <短名>  ｜ commit: `<hash>`
- [ ] T2 — <短名>  ｜ commit: `<hash>`
- [ ] T3 — <短名>  ｜ commit: `<hash>`

## 偏离 SPEC 的发现

<!-- 实现中如发现 SPEC 错 / 不全，记录在此并触发 SPEC 修订（回 Stage 4） -->

- 无

## 已运行的自动化检查

- [ ] 单元测试
- [ ] 集成测试
- [ ] Linter
- [ ] 类型检查
- [ ] 构建通过

## Stage 7 → 8 过渡前 verification-before-completion 核对（v1.2 强制）

> 调 `verification-before-completion` skill 之后填。每条 AI 验证通道的 AC 都要有验证命令 + 输出证据。
>
> 这一步是为了挡住「AI 自报 PASS 但实际没跑过验证」的盲区。

| AC | AI 验证命令 | 输出证据 | PASS? |
|---|---|---|---|
| AC1 | <例：`curl https://...`> | <粘贴 HTTP 200> | ✅/❌ |
| AC2 | ... | | |

## Stage 8 入场摘要预备

> 完成本阶段前先准备好给 Stage 8 的"质检就绪摘要"草稿（建议用 `requesting-code-review` skill 的结构）：改了什么、入口在哪、自动化通过情况、建议人工重点测什么。
