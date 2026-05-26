# workflow-spec/templates/ — 流程模板

九个阶段的 markdown 模板。**配套 specification.md v1.4「规则五（持久化）+ 规则六（恢复）」使用**。

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

## 怎么用

按 [specification.md §3.5「持久化机制（约定）」](../specification.md#35-持久化机制约定v13)，**新项目首次接到任务时**：

```bash
# 1. 在项目 src 同级建 workflow/ 文件夹 (如未建)
mkdir -p workflow/_template

# 2. 把本目录 9 个 md + 本 README 拷过去作为基础
cp -r path/to/workflow-spec/templates/. workflow/_template/

# 3. 每个新任务从 _template/ cp 一份
cp -r workflow/_template workflow/001-your-task-name
```

之后每个阶段在对应 md 里填写，commit 时按 `stage-N: ...` / `task-TX: ...` / `fix(TX): ...` 前缀分类（见 [`references/plan-and-tasks.md` 的 commit conventions](../references/plan-and-tasks.md)）。

## 模板含的 v1.2 约定（已内嵌）

- **02-grill-me.md**：含 skill 调用记录槽位 + OQ type 标记（`technical` / `taste`）
- **04-spec.md**：AC 双通道（AI 验证 + 人工验证）+ OQ type 标记 + 用户确认槽
- **06-tasks.md**：每个 task 含 Touches / Done when（可验证证据）/ Depends on + 用户确认槽
- **07-implementation.md**：commit prefix 速查表 + verification-before-completion 调用记录槽
- **08-qa.md**：质检就绪摘要 + 人工实测发现 + 用户实测确认槽
- **09-acceptance.md**：22 AC 满足核对表 + 用户验收槽

## 恢复进行中的任务（v1.4 新增，对应规则六）

新 session 接手已有 `workflow/` 的项目时，AI 第一步**不是直接干活，是探测状态**：

```bash
# 1. 列出所有 in-flight 任务
ls workflow/
# → 001-foo/  002-bar/  _template/

# 2. 读目标任务的 9 个阶段文件
ls workflow/002-bar/
# → 01-brainstorm.md  02-grill-me.md  ...  09-acceptance.md
```

逐个 md 按下表判定状态：

| md 文件状态 | 阶段状态 | 处理 |
|---|---|---|
| 文件不存在 / 只剩模板占位符 | **未开始** | 候选 resume point |
| 顶部 `> 已跳过 — 理由：...` | **已跳过** | 算完成,跳过 |
| 内容已填,`⬜ 等待确认` | **已起草,关卡未过** | 候选 resume point（如是阶段 4/6/8/9） |
| 内容已填,`⬜ 已确认` 已勾上 | **已通过** | 跳过 |
| 阶段 1/3/5/7 无确认槽,内容非模板 | **已通过** | 跳过 |

**第一个非"已通过 / 已跳过"的阶段 = resume point**。先把这个判定告诉用户:

> 「检测到 `workflow/002-account-rate-limit`：Stage 1-4 已通过（SPEC 2026-05-20 确认），Stage 5 草稿已写但 Stage 6 尚未开始。要从 Stage 6 续做，还是回 Stage 5 修计划？」

确认后再动手。详见 [specification.md §3 规则六](../specification.md#规则六v14-新增从-workflow-状态恢复任务不从记忆里凭印象续做)。

## 跳过阶段（按规模伸缩规则）

按 [specification.md §3 规则一](../specification.md#规则一按任务规模伸缩)：一行 bug 修复不必走全部九步。

**跳过的阶段保留 md 文件**，开头写 `> 已跳过 — 理由：<...>` 即可（符合规则三「每个阶段可见 artifact」）。

## 相对路径 vs 绝对 URL

本目录 md 中所有 `specification.md` 引用都用**绝对 URL** `https://github.com/znlm1229/vibe-coding-lab/blob/main/workflow-spec/...`，**任何布局都能点开**。

如果你的项目把 workflow-spec/ 复制成本地 monorepo 子目录，可批量改回相对路径：

```bash
# 在你的 workflow/_template/ 目录下跑
sed -i 's|https://github.com/znlm1229/vibe-coding-lab/blob/main/workflow-spec/|../../../../workflow-spec/|g' *.md
```

（路径深度取决于你的布局；vibe-coding-lab monorepo 现状是 `projects/<name>/workflow/_template/` → `workflow-spec/` 即 4 层 `../`。）
