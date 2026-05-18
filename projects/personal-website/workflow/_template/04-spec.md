# Stage 4 ｜ SPEC 规格 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-4--spec-规格人工关卡)
> 标准模板见 [`spec-template.md`](../../../../workflow-spec/references/spec-template.md)
>
> **要点**：写"做什么"不写"怎么做"；验收标准必须**可测试**；**用户未确认前不得进入 Stage 5**。

---

## Summary

<!-- 一两句话：这是什么、给谁用的 -->

## Problem

<!-- 解决什么问题、为什么现在做、不做会怎样 -->

## Goals

<!-- 必须达成的具体、可观察的成果 -->

-
-

## Non-goals

<!-- 明确**不**做的事，与 Goals 同等重要，防止范围蔓延 -->

-
-

## Behavior

- **Inputs**: 输入什么、什么形式
- **Outputs**: 输出什么、什么形式
- **Key flows**: 主路径
- **Edge cases**: 已知边界
- **Error handling**: 出错时的行为

## Constraints

<!-- 硬限制：性能预算、兼容、安全、合规、deadline、不可改的依赖；技术栈、测试位置、构建工具也写这里 -->

## Open questions

<!-- 仍未解决的问题。理想情况下确认前应为空；不为空时每条标注 owner 与解决计划 -->

## Acceptance criteria

> 阶段 9 会对照本节逐条核对。每条必须二选一可判定。
>
> 好：「未登录用户访问 /dashboard 被重定向到 /login。」
> 差：「认证工作得很好。」

1.
2.
3.

---

## 用户确认

- ⬜ **等待确认**
- ⬜ **已确认** — 确认时间：______ ｜ 备注：______

> 一旦确认，本 SPEC 即为契约。后续修改需显式重新确认（不允许静默漂移）。
