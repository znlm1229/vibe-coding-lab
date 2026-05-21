# Stage 4 ｜ SPEC 规格 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-4--spec-规格人工关卡)
> 标准模板见 [`spec-template.md`](../../../../workflow-spec/references/spec-template.md)
>
> **要点**：写"做什么"不写"怎么做"；验收标准必须**可测试**；**用户未确认前不得进入 Stage 5**。
>
> **v1.2 关键约定**：
> - **AC 必须分两栏 AI 验证 / 人工验证**（两边都 PASS 才算 PASS）—— 见下方表格模板
> - **OQ 必须标 type**：`technical`（客观）vs `taste`（主观，AI 推荐仅占位）
> - SPEC 修订需显式版本号 + 修订日志，不许静默漂移

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

> 每条 OQ 标 type（v1.2）：`technical` vs `taste`。taste 类必须显式标"AI 起草仅占位"。

| # | 问题 | 类型 | AI 推荐 | 决定 | 阻塞节点 | 备注 |
|---|---|---|---|---|---|---|
| OQ1 | <问题> | technical | <推荐> | (待) | Stage 7 前 | |
| OQ2 | <问题> | taste ⚠️ | <占位草稿> | (待) | Stage 7 写文案时 | AI 起草仅占位，用户应自己改写 |

## Acceptance criteria

> Stage 9 会对照本节逐条核对。每条必须二选一可判定，且**必须分 AI 验证 + 人工验证两栏**（v1.2）。
>
> 好：「未登录用户访问 /dashboard 被重定向到 /login。」
> 差：「认证工作得很好。」

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| AC1 | <描述> | `curl URL` / `grep ...` / build OK | 浏览器访问 / 点击 / 视觉判断 |
| AC2 | <描述> | <如何机器测> | <真人如何测> |
| AC3 | <描述> | <如何机器测> | <真人如何测> |

> ⚠️ 如果某条 AC 写不出人工验证路径，它通常不够"行为化"——改 AC 而不是省略人工通道。详见 `spec-template.md` 中「AC 双通道验证约定」。

---

## 用户确认

- ⬜ **等待确认**
- ⬜ **已确认** — 确认时间：______ ｜ 备注：______

> 一旦确认，本 SPEC 即为契约。后续修改需显式重新确认（不允许静默漂移）。
