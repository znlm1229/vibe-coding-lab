# CLAUDE.md — personal-website

> 本文件是 personal-website 的**项目级 AI 指令**。Claude Code / Codex 等 agent 在本目录及子目录下工作时自动加载，规则优先级高于全局默认行为。

## 1. 项目状态

**进行中** —— 项目定位：用户的个人网站。具体范围（极简名片 / 博客 / 作品集 / 混合 / SaaS 寄生等）待 Stage 2 `grill-me` 拷问后定型。

- **001-personal-website ✅ 已完成（2026-05-19 用户验收通过）**
- 公网 URL：https://lw-personal.pages.dev/
- 完整链路：Stage 1 Brainstorm → 2 Grill Me（10 轮）→ 3 Prototype（跳过）→ 4 SPEC（含 v1.0.1 / v1.0.2 patch）→ 5 Plan → 6 Tasks → 7 Implementation（19 task + Stage 8 回路 fix）→ 8 Human QA（1 阻塞已修）→ 9 Acceptance（13/13 AC 通过 + 用户签收）
- 下一任务：候选 002（UX 收尾：Header nav / Footer 清理 / 文案润色）、003（品牌化：自制 OG / 自定义域名）—— 用户提议时再开
- 历史任务台账：见 [`README.md#任务台账`](./README.md#任务台账)

## 2. 必须遵循的工作流（强制）

本项目所有非琐碎开发任务，强制按 [`workflow-spec/`](../../workflow-spec/) 的九步流程执行：

```
Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★
```

> ★ = 人工关卡，未经用户**明确确认**不得跨越。

### 阶段绑定的 skill（workflow-spec v1.2）

| 阶段 | skill | 级别 | 说明 |
|---|---|---|---|
| Stage 1 ｜ Brainstorm | `brainstorming` | 推荐 | superpowers 内置，强制结构化发散，避免锚定第一个想法 |
| Stage 2 ｜ Grill Me | `grill-me` | **强制** | 拷问交互覆盖决策树每个分支。AI 自由列问题不能替代。skill 不可用时停下报告 |
| Stage 5 ｜ Plan | `writing-plans` | 推荐 | 结构化多步计划（phase 排序、风险标记、测试策略）|
| Stage 7 → 8 过渡 | `verification-before-completion` | **强制** | 声明完成前必须跑验证命令并确认输出，证据先于断言；防 AC 字面 PASS / 行为 FAIL 盲区 |
| Stage 8 ｜ Human QA | `requesting-code-review` | 推荐 | 模仿"工程师准备 PR"的格式组织质检就绪摘要 |

新增 skill 绑定需同步更新 [`../../workflow-spec/specification.md`](../../workflow-spec/specification.md) + [`../../workflow-spec/SKILL.md`](../../workflow-spec/SKILL.md) + [`../../workflow-spec/references/tooling.md`](../../workflow-spec/references/tooling.md)。

**完整规则与定义请阅读**：
- 总规范：[`../../workflow-spec/specification.md`](../../workflow-spec/specification.md)
- AI 行为细则：[`../../workflow-spec/SKILL.md`](../../workflow-spec/SKILL.md)
- SPEC 模板：[`../../workflow-spec/references/spec-template.md`](../../workflow-spec/references/spec-template.md)
- Plan/Tasks 模板：[`../../workflow-spec/references/plan-and-tasks.md`](../../workflow-spec/references/plan-and-tasks.md)
- 工具建议：[`../../workflow-spec/references/tooling.md`](../../workflow-spec/references/tooling.md)

**接到任务时，第一句话不是开始干，而是宣布计划**：哪些阶段会走、哪些会跳过、为什么、人工关卡在哪。等用户确认后再开始 Stage 1。

## 3. Artifact 存放约定

每个任务在 [`workflow/`](./workflow/) 下建独立子目录，命名 `NNN-短名称/`（如 `001-user-login/`）：

- `NNN` 是 3 位编号，按完成或开始顺序递增
- `短名称` 用 kebab-case，≤ 4 个词

**起步**：复制 [`workflow/_template/`](./workflow/_template/) 到 `workflow/NNN-task-name/`，再按阶段填写。

子目录内文件名固定（不要重命名）：
```
01-brainstorm.md
02-grill-me.md
03-prototype.md
04-spec.md          ★
05-plan.md
06-tasks.md         ★
07-implementation.md
08-qa.md            ★
09-acceptance.md    ★
```

可跳过的阶段：**不要删除文件**，在文件开头写「**已跳过 + 理由**」即可（符合「每个阶段可见 artifact」原则）。

## 4. 代码组织

- 实际实现代码统一放 `src/`
- 测试位置、构建工具、依赖管理、目录结构 **待第一个任务的 Stage 4 SPEC 写明**（写入 SPEC 的 `Constraints` 节）
- 在 SPEC 没定下这些之前，不要在 `src/` 里凭空创建文件

## 5. 通用约定

- **编码**：所有文件 UTF-8 no BOM
- **语言**：文档、代码注释、commit 信息使用**中文**（例外：`SKILL.md` 等需要保留 AI 标准格式的文件保持英文）
- **commit 信息格式**：`stage-N: 简述` 或 `task-TX: 简述`
  - 例：`stage-4: SPEC for user login`
  - 例：`task-T1: implement login form validation`
- **粒度**：每个 commit 对应一个明确的 artifact 或一个 task 的可验证进度
- **分支**：默认在 `main` 直接提交；如任务涉及风险，开 `feature/NNN-task-name` 分支

## 6. AI 硬性禁止行为

- ❌ 在用户确认 SPEC（Stage 4）之前编写**任何实现代码**
- ❌ 在用户确认 Tasks（Stage 6）之前进入 Implementation
- ❌ 在人工 QA 没实际操作过之前宣布工作"完成"
- ❌ 跳过 artifact 文件说"我想过了"——必须有可读的产出
- ❌ 给一行 bug 修复硬凑 9 个阶段（请按规模伸缩，但要明说跳了哪些和为什么）
- ❌ 在实现中途**静默修改** SPEC——发现 SPEC 错了或不全，**停下来回 Stage 4 显式修订**并取得再确认
- ❌ 自我批准任何人工关卡
- ❌ 在 Stage 2 Grill Me **不调用 `grill-me` skill** 而靠自由列问题敷衍（除非整个 Stage 2 按规模伸缩规则被显式跳过，并写明理由）
- ❌ 在 Stage 7 → 8 过渡 **不调用 `verification-before-completion` skill** 就声明完成（v1.2 强制；防 AC 字面通过 / 行为破洞的盲区）
- ❌ 把 auto-mode 当作绕过人工关卡的借口（v1.2 规则四：auto-mode 仅适用于阶段内例行决策，不可凌驾 4 个人工关卡 SPEC / Tasks / QA / Acceptance）
- ❌ 写 AC 时只写「AI 如何验证」一栏（v1.2 要求：每条 AC 必须同时标 AI 验证 + 人工验证两通道）
- ❌ Stage 8 发现 bug 修完后，commit 信息复用 `task-TX:` 而不是 `fix(TX):`（v1.2 规范：区分首次实现 vs 修复回路）

## 7. 第一次接到任务时的开场动作

1. 读 [`README.md`](./README.md) 看项目当前状态
2. 读 [`../../workflow-spec/specification.md`](../../workflow-spec/specification.md) 第 1–4 节复习流程与人工关卡
3. **评估任务规模**，向用户宣布：
   - 打算走哪些阶段
   - 打算跳过哪些阶段、为什么
   - 三个人工关卡的位置
4. 等用户确认 → 复制 `workflow/_template/` 到 `workflow/NNN-task-name/` → 开始 Stage 1
5. 在 `README.md` 的「任务台账」里登记新任务

## 8. 后续维护

- 项目状态有重大变化（如确定了具体功能）→ 更新本文件第 1 节与 `README.md`
- 工作流细则有变化 → 直接修改 [`../../workflow-spec/`](../../workflow-spec/) 而不是在本文件复制规则
- 出现新的项目级约定（如固定技术栈）→ 在本文件追加新章节
