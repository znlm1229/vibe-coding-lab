# _template/

新任务子目录的模板。复制整份到 `../NNN-task-name/` 作为新任务的起点。

## 文件清单

| 文件 | 阶段 | 关卡 | v1.2 stage-bound skill |
|---|---|---|---|
| [`01-brainstorm.md`](./01-brainstorm.md) | 1. 头脑风暴 | | 推荐 `brainstorming` |
| [`02-grill-me.md`](./02-grill-me.md) | 2. 质询拷问 | | **强制 `grill-me`** |
| [`03-prototype.md`](./03-prototype.md) | 3. 原型 | | — |
| [`04-spec.md`](./04-spec.md) | 4. SPEC 规格 | ★ | — |
| [`05-plan.md`](./05-plan.md) | 5. 计划 | | 推荐 `writing-plans` |
| [`06-tasks.md`](./06-tasks.md) | 6. 任务 | ★ | — |
| [`07-implementation.md`](./07-implementation.md) | 7. 实现 | | (转 8 前) **强制 `verification-before-completion`** |
| [`08-qa.md`](./08-qa.md) | 8. 人工质检 | ★ | 推荐 `requesting-code-review` |
| [`09-acceptance.md`](./09-acceptance.md) | 9. 验收 | ★ | — |

★ = 人工关卡，未经用户确认不得进入下一阶段。

> **workflow-spec 当前版本**：[v1.2](../../../../workflow-spec/specification.md)。模板里的 OQ 类型字段、AC 双通道、commit 前缀规范（`task-TX:` / `stage-N:` / `fix(TX):`）、Stage 7→8 verification-before-completion 强制 都对应 v1.2 规范。

## 使用方法

```bash
cp -r workflow/_template workflow/NNN-your-task-name
```

随后由 AI agent 按阶段填写。可跳过的阶段：保留文件，开头写「已跳过 + 理由」。
