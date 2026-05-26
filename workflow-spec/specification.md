# AI 原生开发工作流程规范

> Brainstorm · Grill Me · Prototype · SPEC · Plan · Tasks · Implementation · Human QA · Acceptance
>
> 供团队成员与 AI 编码代理共同参考 ｜ **v1.3**

> 这是 [`specification.docx`](./specification.docx) 的可读 Markdown 版本，也是**正本**。docx 通过 `pandoc specification.md -o specification.docx --toc --toc-depth=2` 重生成，与本文件同步（v1.3 升级后请重跑此命令）。
>
> **v1.3 关键变更**（在 v1.2 基础上累加）：加规则五「每个项目必须建 `workflow/` 文件夹持久化阶段 artifact」+ 新增 [`templates/`](./templates/) 子目录含 9 个阶段 markdown 模板（去项目化通用版，绝对 URL 引用 spec）。这是把已有事实约定（vibe-coding-lab 各项目都建过 `workflow/`）从「项目级惯例」上提为「spec 级强制规则」+ 提供 turnkey templates 给新项目。
>
> **v1.2 关键变更**：扩展 4 个 stage-skill 绑定（`brainstorming` / `grill-me` / `writing-plans` / `verification-before-completion` / `requesting-code-review`）；加 AC 双通道验证约定；加 auto-mode 与人工关卡的边界；加 OQ 类型字段；加 bug 回路 commit 规范；加 2 条新失败模式（来自 001 复盘）。

## 目录

- [1. 这份文档是什么](#1-这份文档是什么)
- [2. 九个阶段总览](#2-九个阶段总览)
- [3. 如何运行这套流程：三条总规则](#3-如何运行这套流程三条总规则)
- [4. 三个人工关卡](#4-三个人工关卡)
- [5. 九个阶段详解](#5-九个阶段详解)
- [6. 要避免的常见失败模式](#6-要避免的常见失败模式)
- [7. 配套参考文件](#7-配套参考文件)
- [8. 更新记录](#8-更新记录)

---

## 1. 这份文档是什么

这份文档定义了我们团队进行 AI 原生开发的标准工作流程。它的读者有两类：团队成员（用它来理解流程、对齐预期、把控关卡），以及 AI 编码代理（按它来组织工作，而不是拿到需求就直接写代码）。

**核心理念：代码之前先对齐，完成之前先验证。**

AI 辅助开发的大部分失败，都来自两种情况：AI 充满自信地构建了错误的东西；或者构建了正确的东西，但没有人真正检查过。这套流程把「思考」前置、把「人工确认」后置，正是为了同时防住这两点。

整套流程由九个有意为之的阶段组成，按顺序推进：

> Brainstorm → Grill Me → Prototype → SPEC → Plan → Tasks → Implementation → Human QA → Acceptance

## 2. 九个阶段总览

下表是九个阶段的速查。带 ★ 的阶段是「人工关卡」，详见第 4 节。

| # | 阶段 | 回答的问题 / 目的 | 产出物（Artifact） |
|---|---|---|---|
| 1 | Brainstorm 头脑风暴 | 有哪些可能的路？发散，不收敛。 | 3–5 个不同方向，各附一句核心思路与主要权衡。 |
| 2 | Grill Me 质询拷问 | 这个想法哪里会出问题？暴露假设与风险。 | 按严重程度分组的尖锐问题与风险清单。 |
| 3 | Prototype 原型 | 最不确定的点能否被验证？ | 最小可运行产物 + 一段「验证/证伪了什么」说明。 |
| 4 | SPEC 规格 ★ | 要构建什么？（不是怎么做） | SPEC 文档，含可测试的验收标准。 |
| 5 | Plan 计划 | 怎么做？按什么顺序？ | 技术方案、有序阶段、依赖关系、风险标记。 |
| 6 | Tasks 任务 ★ | 拆成哪些具体可完成的工作项？ | 有序、可勾选的任务清单，每项注明影响范围与「完成标准」。 |
| 7 | Implementation 实现 | 动手把计划变成代码。 | 可运行代码 + 实时更新的任务清单进度。 |
| 8 | Human QA 人工质检 ★ | 真人实际用过了吗？ | AI 的质检就绪摘要 + 人工实测发现。 |
| 9 | Acceptance 验收 ★ | 是否满足最初的 SPEC 契约？ | 逐条验收标准的「满足/未满足」核对表 + 证据。 |

> ★ = 人工关卡，AI 不得在未获得明确确认前推进。

## 3. 如何运行这套流程：三条总规则

默认按顺序走完九个阶段，但要保持务实。三条规则约束着流程的推进方式。

### 规则一：按任务规模伸缩

一行 bug 修复不需要 Brainstorm 或 Prototype；一个新子系统则需要每个阶段。开始之前，先判断任务的体量，并明确告诉对方你打算走哪些阶段、跳过哪些、为什么。让对方有机会纠正你。

### 规则二：在每个人工关卡停下

有三个阶段是硬性停止点，未获得明确确认不得推进：**SPEC 结束**、**Tasks 结束**、**Human QA / Acceptance**。产出 artifact 是 AI 的工作，批准 artifact 是人的工作。AI 永远不能批准自己的 SPEC，也不能验收自己的成果。

### 规则三：每个阶段都要产出可见的 artifact

每个阶段都以一件具体的、对方能读到的东西收尾——一份想法清单、一份尖锐问题清单、一个可运行原型、一份 SPEC 文档、一份计划、一份任务清单、一份代码 diff、一份质检报告。「我想过了」不算一个阶段产出。如果某个阶段的 artifact 确实很简单，就直说，然后继续——而不是硬凑内容。

开始一项任务时，先简要说明计划：走哪些阶段、什么顺序、人工关卡在哪。然后从第一个阶段开始。

### 规则四（v1.2 新增）：Auto-mode 不能凌驾人工关卡

当宿主环境处于 "auto mode"（连续自治执行）时：

- **可应用 auto-mode 的**：阶段内部的例行决策（选哪个文件改、用哪个变量名、用哪个 lib 版本）
- **不可应用 auto-mode 的**：四个人工关卡（SPEC / Tasks / Human QA / Acceptance）。auto-mode 不覆写经过深思熟虑设计的安全停止
- 关卡处有疑虑就停下问。在设计好的停止点上停一下的成本很低；绕过它的成本可能是构建错的功能 / 推出未被认可的版本

### 规则五（v1.3 新增）：每个项目必须建 `workflow/` 文件夹持久化阶段 artifact

工作流的九个阶段产出**不能只活在聊天上下文里**——session 结束后无法被新会话 / 新协作者 / 自己一周后看到。**所有 artifact 必须落到一个可读、可被未来的人和 AI 找到、可被 git 追踪的持久位置**。

**约定**：

在项目代码（通常 `src/`）的**同级目录**建一个 `workflow/` 文件夹，作为本项目所有任务的工作流持久化容器：

```
your-project/
├── src/                       # 代码
├── workflow/                  # ← 本规则要求建
│   ├── _template/             # 9 个 stage md 模板 (从 workflow-spec/templates/ 拷)
│   │   ├── 01-brainstorm.md
│   │   ├── 02-grill-me.md
│   │   ├── 03-prototype.md
│   │   ├── 04-spec.md         ★
│   │   ├── 05-plan.md
│   │   ├── 06-tasks.md        ★
│   │   ├── 07-implementation.md
│   │   ├── 08-qa.md           ★
│   │   └── 09-acceptance.md   ★
│   ├── 001-first-task/        # 每个任务一个子目录
│   │   ├── 01-brainstorm.md   # 同 9 个文件名 (跳过的阶段也保留 md, 开头写 "已跳过 + 理由")
│   │   ├── 02-grill-me.md
│   │   └── ...
│   ├── 002-second-task/
│   └── ...
├── CLAUDE.md                  # AI agent 项目级指令 (含工作流规则简述)
└── README.md                  # 任务台账登记新/已完成任务
```

**任务子目录命名**：`NNN-kebab-case-短名/`（NNN 是 3 位编号，按完成/开始顺序递增；短名 ≤ 4 个词）。

**`_template/` 的来源**：从本仓库 [`workflow-spec/templates/`](./templates/) 一次性拷贝，含 9 个阶段的 markdown 骨架（带 v1.2 约定：AC 双通道 / OQ type / skill 调用记录槽位等）。

**为什么强制**：

1. **新会话 / 跨人协作的可恢复性**：另一个 AI session（或人）打开 `workflow/002-name/` 立即知道这个任务走到哪、SPEC 是什么、AC 满足了几条。**对话历史不可靠 / 不可分享**，markdown artifact 是持久 source of truth。
2. **git history 可追溯**：每个 commit 映射到具体 stage 或 task（按 §5 阶段 7 的 commit prefix 表），翻 git log 能重建项目演进。
3. **回溯防漂移**：Stage 9 Acceptance 验收时对照 04-spec.md，确认 SPEC 没被实现静默改写（§6 失败模式「SPEC 静默漂移」的结构性预防）。
4. **新任务复用模板**：`_template/` 在 git 里，新任务 `cp -r _template NNN-task-name/` 一行起步，不必每次重组结构。

**第一次接到任务时（AI 与人共同的开场动作）**：

```bash
# 项目根（src/ 的同级）
mkdir -p workflow/_template
# 从 workflow-spec 拷模板 (一次性, 后续 _template 跟着项目走)
cp -r path/to/workflow-spec/templates/. workflow/_template/

# 起新任务
cp -r workflow/_template workflow/001-your-task-name
```

后续每个阶段在 `workflow/NNN-task-name/0X-stage.md` 内填写，**跳过的阶段保留文件**（开头写「已跳过 + 理由」即可，符合规则三）。

**与 CLAUDE.md / AGENTS.md 的关系**：项目根 `CLAUDE.md` 应当**指向** `workflow/` 而非重复其内容；后者是 git-tracked 的事实源。

## 4. 三个人工关卡

人工关卡是这套流程的安全机制。它们存在的理由是：AI 的自信和人的认可不是一回事。

| 人工关卡 | 对齐的是什么 | 为什么必须停 |
|---|---|---|
| SPEC 结束 | 「做什么」的对齐 | AI 的自信不等于团队的认可。验收标准是契约，写错了后面全错。 |
| Tasks 结束 | 「怎么做」与范围的对齐 | 任务清单是最后一个「改范围还很便宜」的时点。 |
| Human QA / Acceptance | 确认「真的能用」 | 自动化测试通过 ≠ 完成。必须有人实际操作、对照 SPEC 逐条确认。 |

## 5. 九个阶段详解

### 阶段 1 ｜ Brainstorm 头脑风暴

**目的**：先发散，再收敛。为问题生成多种方法、框架与可能性，而不是一个被钦定的方案。目标是把选项空间摊开，让对方看见那些没走的路。

**推荐工具：`brainstorming` skill**（v1.2 新增）。当环境中可用时，优先调用该 skill 驱动发散思考，比 AI 自由列方向更能强制覆盖真实选项空间，避免过早收敛。

**产出**：一份简短清单，列出 3–5 个不同的方法，每个配一句核心思路的勾勒和它的主要权衡。如果这个任务确实只有一种合理方法，明说，而不是硬造出几个站不住脚的替代方案。

**注意**：此阶段不要评判出胜者——那是对方的决定，并且要由下一阶段的信息来支撑。

### 阶段 2 ｜ Grill Me 质询拷问

**目的**：在构建之前进行压力测试。拿起领先的想法，拷问它：暴露隐藏的假设、边界情况、失败模式、集成风险、未回答的问题。这个名字是字面意思——AI 应该拷问这个「想法」，并邀请对方反过来拷问。

**强制工具：`grill-me` skill**（v1.1 新增）。本阶段必须通过 `grill-me` skill 驱动，由 skill 以「不依不饶」的方式逐条审问用户的方案 / 设计，把决策树的每一个分支都问到落地。AI 自由发挥地"列几个问题"覆盖不到决策树的所有分支，不能替代该 skill。详见 [`references/tooling.md`](./references/tooling.md#阶段-2--grill-me-质询拷问)。

**产出**：一份尖锐问题与已识别风险的清单，大致按严重程度分组（由 `grill-me` 交互过程沉淀）。每一条都要具体到能据此行动（「迁移过程中正在处理的请求会怎样？」而不是「我们考虑过边界情况了吗？」）。Stage 2 的 artifact 还要附一段「skill 调用记录」：触发时间、轮数、覆盖的关键决策分支。

**Open Questions 必须标类型（v1.2 新增）**：`technical`（有客观正确答案的技术决策）vs `taste`（主观偏好——AI 推荐只是占位，用户应自己改）。Taste 类 OQ 在 SPEC 中默认带「AI 起草仅占位，用户应自行替换以匹配本人语气」的提示。这条规则是为了避免「用户接受 AI 推荐 → AI 起草内容 → 上线后用户发现品味不符必须重写」的反复成本。

**注意**：此阶段结束时，请对方回答这些开放问题，或确认哪些可以接受暂时搁置。他们的回答会喂给 SPEC。

### 阶段 3 ｜ Prototype 原型

**目的**：构建最小的、粗糙的、能解决最大不确定性的东西。原型默认是用完即弃的——它的工作是把一个开放问题转化为一个确定答案，或者给对方一个可触摸的东西去反应。它不是最终实现。

**产出**：一个最小的可运行产物（一段脚本、一个草图、一个 spike 分支），加上一段话说明它验证或证伪了什么。

**注意**：当没有任何东西真正不确定时，跳过这个阶段——路径清晰时，做原型只是更慢的实现。明说并继续。

### 阶段 4 ｜ SPEC 规格（人工关卡）

**目的**：写下「要构建什么」——不是怎么做。SPEC 捕获已达成一致的范围：行为、输入与输出、边界、明确的非目标，以及阶段 9 将据以核对的验收标准。

**AC 双通道验证约定（v1.2 新增）**：每条 Acceptance Criterion 必须显式标「AI 如何验证 / 人工如何验证」两栏。它们是不同的验证通道，**只有两边都 PASS，AC 才算 PASS**：
- AI 通道：`grep` / `curl` / build 结果等字符级、结构级检查 → 适合验证「不含 X」「URL 返回 200」「文件齐」等
- 人工通道：浏览器实测、点击交互、文案审美 → 适合验证运行时行为（点击、切换、JS 解码内容、动画、表单提交、UI 体感）

如果一条 AC 写不出人工验证路径，它通常不够"行为化"，需要重写。本规则的具体动机见 §6「字面 AC vs 行为 AC 脱节」失败模式。

**产出**：一份 SPEC 文档。结构见 [`references/spec-template.md`](./references/spec-template.md)。

**硬性停止**：把 SPEC 呈现给对方，在做任何规划之前获得确认。这里写下的验收标准是一份契约——阶段 9（Acceptance）会对照「这份」文档核对结果，所以它必须具体、可测试。如果对方之后修改 SPEC，没问题，但那是一个可见的、刻意的动作，不是悄无声息的漂移。

### 阶段 5 ｜ Plan 计划

**目的**：决定「怎么做」和「按什么顺序」。从已确认的 SPEC 出发，铺开技术方案、工作的先后顺序、各部分之间的依赖、以及需要小心对待的风险点。Plan 回答的是「我们将如何从零走到 SPEC」。

**推荐工具：`writing-plans` skill**（v1.2 新增）。该 skill 提供多步实现计划的结构化框架（phase 排序、风险标记、测试策略），比 AI 自由写计划更稳。

**产出**：一份计划文档——架构决策、有序的阶段、依赖说明，以及对任何仍有风险之处的标记。结构见 [`references/plan-and-tasks.md`](./references/plan-and-tasks.md)。

### 阶段 6 ｜ Tasks 任务（人工关卡）

**目的**：把 Plan 拆解成一份具体的、可单独完成的工作项清单。每个任务都应足够小，能够被追踪、被验证、并且——原则上——能交给一个独立的代理。每个任务都注明它影响什么、它的「完成」意味着什么。

**产出**：一份有序的、可勾选的任务清单。结构见 [`references/plan-and-tasks.md`](./references/plan-and-tasks.md)。

**硬性停止**：任务清单是范围变更还很便宜的最后一个时点。把它呈现出来，在编写实现代码之前获得对方确认。一旦他们批准，这份清单就成为阶段 7 进度追踪的单位。

### 阶段 7 ｜ Implementation 实现

**目的**：把它构建出来。按已批准的任务清单顺序推进，一次完成一个任务，并随做随更新清单上的进度。待在 SPEC 之内——如果发现 SPEC 错了或不完整，停下来提出，而不是悄悄构建出不一样的东西。一个被发现的 SPEC 缺口会把你送回阶段 4，而不是让你脱稿发挥。

**Commit 信息规范（v1.2 更新）**：
- 新 task 工作：`task-TX: 简述`
- 阶段转换 / artifact 提交：`stage-N: 简述`
- 已完成 task 的 bug 修复（通常来自 Stage 8 回路）：**`fix(TX): 简述`**——不要复用 `task-TX` 前缀，区分「首次实现」和「修复回路」让 git 历史诚实记录迭代

**进入 Stage 8 前必须调 `verification-before-completion` skill（v1.2 新增）**。在声明 Stage 7 完成、或宣称所有 AC 通过之前，调用该 skill 强制要求每条「PASS」断言都有对应的验证命令输出作为证据。没有这一道约束，AI 容易把字面 AC 的 grep 通过当成行为 AC 的通过——见 §6「字面 AC vs 行为 AC 脱节」失败模式。

**产出**：可运行的代码，加上更新后、显示哪些已完成的任务清单。保持改动可审查——映射到任务的、小而连贯的提交，胜过一个巨大的 diff。

### 阶段 8 ｜ Human QA 人工质检（人工关卡）

**目的**：由人来检查结果。这区别于自动化测试——后者 AI 也应该跑。Human QA 是一个人真正地操作这个东西：试用功能、检查体验、命中自动化测试漏掉的情况。AI 在这里的角色是让质检变容易：总结改了什么、列出要测什么、指向相关入口、报告哪些自动化检查已经通过。

**推荐工具：`requesting-code-review` skill**（v1.2 新增）。该 skill 模仿"工程师准备 PR 给 reviewer"的格式来组织质检就绪摘要，让用户更快扫到重点。

**产出**：一份来自 AI 的「质检就绪摘要」（改了什么、如何操作、已测了什么），然后是人的实测发现。

**硬性停止**：不要因为测试通过就宣布工作完成。必须有人去看。如果用户发现阻塞 bug，回到 Stage 7 修（commit 用 `fix(TX):` 前缀），然后重新做 Stage 8 入场摘要再次交付质检。

### 阶段 9 ｜ Acceptance 验收

**目的**：对照契约确认。逐条走过阶段 4 中 SPEC 的验收标准，把构建出的结果对照每一条核对。验收对每一条标准而言是二元的——满足或未满足——而工作「完成」，当且仅当对方同意每一条标准都已满足。

**产出**：一份核对表，把每条 SPEC 验收标准映射到「满足/未满足」，并附证据。如果有任何未满足项，它会被路由回相应的较早阶段（通常是 Tasks 或 Implementation），而不是被放行。

**注意**：验收是对方的决定，不是 AI 的。AI 呈现证据，人来验收。

## 6. 要避免的常见失败模式

- **直接跳到 Implementation。** 最常见、也最昂贵的错误。即使在时间压力下，一份快速的 SPEC 和任务清单也胜过快速地构建错误的东西。
- **自我批准关卡。** AI 写了一份 SPEC，然后当作它已被确认一样继续推进。关卡的存在恰恰是因为 AI 的自信不等于对方的同意。
- **隐形的阶段。** 声称某个阶段发生了，却没有产出它的 artifact。如果没有东西可以展示，那这个阶段就没有发生。
- **SPEC 静默漂移。** 在实现中途发现 SPEC 错了，然后就……构建了别的东西。修改 SPEC 是允许的；悄悄地做不允许。
- **给小任务硬凑流程。** 强迫一个微小的修复走完九个仪式性的阶段。按任务规模伸缩——流程服务于工作，而不是反过来。
- **把「测试通过」当成「完成」。** 自动化测试是必要的，不是充分的。阶段 8 和阶段 9 是人工阶段，这是有意为之。
- **字面 AC vs 行为 AC 脱节（v1.2 新增，来自 vibe-coding-lab 001 复盘）。** 一条 AC「HTML 不能含明文邮箱」可以被 grep 验证通过，但实际用户面前的邮箱链接完全坏（脚本没加载、fallback 文字永远显示）。当 AC 涉及运行时行为（点击、切换、JS 解码内容、动画、表单提交）时，AI 的自动检查是必要而非充分的。AC artifact **必须**显式标人工验证路径（见 §5 阶段 4 的「AC 双通道验证约定」），且 Stage 8 必须实际执行那条人工验证路径。仅靠 AI grep 打勾的 AC 一律可疑。`verification-before-completion` skill（Stage 7→8 过渡强制）是这条问题的结构化解药。
- **SPEC 早于栈选定（v1.2 新增）。** 在选定 starter / 框架之前，就把详细路径、URL、文件约定写进 SPEC，几乎一定会出后续 patch（本仓库 v1.0.1 `/blog`→`/posts` 就是教科书案例）。两种应对：要么在轻量的预 SPEC 步骤里锁定栈，要么接受「SPEC 命名层 patch」常态化并显式给版本号标记（v1.0.1、v1.0.2 等）——**永远不要静默更新**。

## 7. 配套参考文件

这份规范文档配有一套面向 AI 编码代理的技能文件（SKILL.md 格式），它们让 AI 在编码时自动遵循本流程：

- [`SKILL.md`](./SKILL.md) — 主技能文件，定义完整九步流程与三个人工关卡，AI 编码时自动加载。
- [`references/spec-template.md`](./references/spec-template.md) — SPEC 阶段的文档结构，重点是如何编写可测试的验收标准。
- [`references/plan-and-tasks.md`](./references/plan-and-tasks.md) — Plan 与 Tasks 阶段的结构与任务拆分准则。
- [`references/tooling.md`](./references/tooling.md) — 每个阶段推荐的现成工具（聚焦 Claude Code 与 Codex 两个环境）。
- [`templates/`](./templates/) — **(v1.3 新增)** 9 个阶段的 markdown 模板（去项目化通用版）。新项目按 §3 规则五拷到 `workflow/_template/` 起步。

## 8. 更新记录

### v1.3（2026-05-25）

**触发**：vibe-coding-lab 任务 002-account-rate-limit 端到端完成后做复盘，发现 v1.2 spec 没明示「阶段 artifact 必须存哪里」——vibe-coding-lab 各项目都建了 `workflow/<NNN-task>/0X-stage.md` 持久化结构，但 spec 把这只当「项目级惯例」而非「spec 级要求」，导致：（a）新项目可能漏建 `workflow/`，artifact 散落在 chat 上下文里丢失；（b）每个项目要自己从其他项目 `_template/` 拷一份没有正式来源；（c）AI session 之间无法跨会话继续推进任务。

**主要变更**：

1. **规则五（v1.3 新增）**：每个项目必须建 `workflow/` 文件夹持久化阶段 artifact，作为「规则三 artifact 必产」的具体物理落点。详见 [§3 规则五](#规则五v13-新增每个项目必须建-workflow-文件夹持久化阶段-artifact)。

2. **新增 [`templates/`](./templates/) 子目录**：含 9 个阶段的 markdown 模板（去项目化版本，spec 引用用绝对 URL），新项目拷到 `workflow/_template/` 即可起步：
   ```
   templates/01-brainstorm.md          # 含规则三 + 4 个方向占位
   templates/02-grill-me.md            # 含 grill-me skill 调用记录槽 + OQ type 表
   templates/03-prototype.md           # 含跳过决定
   templates/04-spec.md          ★    # 含 8 节结构 + AC 双通道表 + 用户确认槽
   templates/05-plan.md                # 含 Approach / Phases / Risk / Test
   templates/06-tasks.md         ★    # 含 task 表 (Touches / Done when / Depends on) + 确认槽
   templates/07-implementation.md      # 含 verification-before-completion 调用记录槽
   templates/08-qa.md            ★    # 含质检就绪摘要 + 实测发现
   templates/09-acceptance.md    ★    # 含 AC 满足核对表 + 验收槽
   templates/README.md                 # 用法说明 + 路径适配指南
   ```
   模板里 spec 引用用绝对 URL `https://github.com/znlm1229/vibe-coding-lab/blob/main/workflow-spec/...`，**任何项目布局都能直接点开**，避免每个项目自己计算相对路径深度。

3. **`SKILL.md` 同步升级**：version 1.2 → 1.3；description 加触发场景「项目根没 `workflow/` 时主动建」；changelog 加 v1.3 条目。

4. **`README.md` 文件索引 + 「在新项目落地」段同步更新**：加 templates/ 行；落地步骤显式含 `mkdir workflow/_template + cp templates/`。

5. **`specification.docx` 待同步**：本次 md 改完后需重跑 `pandoc specification.md -o specification.docx --toc --toc-depth=2`（README 命令）。

### v1.2（2026-05-19）

**触发**：vibe-coding-lab 任务 001-personal-website 端到端完成后做复盘（见 [`projects/personal-website/workflow/001-personal-website/10-retrospective.md`](../projects/personal-website/workflow/001-personal-website/10-retrospective.md)），暴露多个可改进点 + 用户提出整合 superpowers 系列 skill。

**主要变更**：

1. **新增 4 个 stage-skill 绑定**（基于 superpowers 生态）：
   - Stage 1 Brainstorm → 推荐 `brainstorming`
   - Stage 5 Plan → 推荐 `writing-plans`
   - Stage 7 → Stage 8 过渡 → **强制 `verification-before-completion`**
   - Stage 8 Human QA → 推荐 `requesting-code-review`

2. **AC 双通道验证约定**：每条 AC 必须显式标「AI 如何验证 / 人工如何验证」两栏，两边都 PASS 才算 PASS（见 §5 阶段 4）。

3. **OQ 必须标类型**：`technical`（客观技术决策）vs `taste`（主观偏好——AI 推荐仅占位，用户应自己改）。Taste 类 OQ 默认带「请用户改写」提示（见 §5 阶段 2）。

4. **Commit 信息规范扩展**：bug 修复（Stage 8 回路）用 `fix(TX):` 前缀，与新 task 的 `task-TX:` 区分（见 §5 阶段 7）。

5. **规则四 Auto-mode 与人工关卡边界**：auto-mode 仅对阶段内例行决策应用，**不可凌驾四个人工关卡**（见 §3 规则四）。

6. **新增 2 条失败模式**（见 §6）：
   - 字面 AC vs 行为 AC 脱节（本次 EmailLink bug 的根因）
   - SPEC 早于栈选定（v1.0.1 patch 的根因）

7. **`SKILL.md` 同步升级**：加 frontmatter version/maintainer/homepage 字段；加中文 trigger phrases；加 anti-trigger；加顶部 stage cheat sheet；扩展 description 关键词覆盖。

8. **`tooling.md` 各阶段补 superpowers skill** 候选。

9. **`specification.docx` 已同步到 v1.2**：用 pandoc 从本文件重生成（命令见 README）。原 v1.0 / v1.1 期间的"docx 滞后"问题至此解决；以后 md 改动只需重跑一次 pandoc。

### v1.1（2026-05-18）

- **Stage 2 Grill Me 绑定强制 skill `grill-me`**。本阶段必须由 `grill-me` skill 驱动，覆盖决策树的每个分支；自由列问题的方式不再视为合格 artifact。Stage 2 artifact 新增「skill 调用记录」字段。
- 配套更新：[`SKILL.md`](./SKILL.md)、[`references/tooling.md`](./references/tooling.md) 同步反映；项目模板 [`personal-website/workflow/_template/02-grill-me.md`](../projects/personal-website/workflow/_template/02-grill-me.md) 加入调用记录槽位。
- `specification.docx` **暂未同步**（仍为 v1.0）。需要分发 docx 前请重新生成。

### v1.0（初版）

- 完整定义九步流程：Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★
- 三条总规则：按规模伸缩、人工关卡停下、阶段必有可见 artifact
- 配套模板：`spec-template.md`、`plan-and-tasks.md`、`tooling.md`

---

—— 文档结束 ——
