# _template/

新任务子目录的模板。复制整份到 `../NNN-task-name/` 作为新任务的起点。

## 文件清单

| 文件 | 阶段 | 关卡 |
|---|---|---|
| [`01-brainstorm.md`](./01-brainstorm.md) | 1. 头脑风暴 | |
| [`02-grill-me.md`](./02-grill-me.md) | 2. 质询拷问 | |
| [`03-prototype.md`](./03-prototype.md) | 3. 原型 | |
| [`04-spec.md`](./04-spec.md) | 4. SPEC 规格 | ★ |
| [`05-plan.md`](./05-plan.md) | 5. 计划 | |
| [`06-tasks.md`](./06-tasks.md) | 6. 任务 | ★ |
| [`07-implementation.md`](./07-implementation.md) | 7. 实现 | |
| [`08-qa.md`](./08-qa.md) | 8. 人工质检 | ★ |
| [`09-acceptance.md`](./09-acceptance.md) | 9. 验收 | ★ |

★ = 人工关卡，未经用户确认不得进入下一阶段。

## 使用方法

```bash
cp -r workflow/_template workflow/001-your-task-name
```

随后由 AI agent 按阶段填写。可跳过的阶段：保留文件，开头写「已跳过 + 理由」。
