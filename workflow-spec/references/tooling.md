# AI 原生开发工作流程 —— 现成工具推荐

本文档为九步工作流程的每个阶段推荐现成的工具与产品,聚焦你们的两个主要环境:**Claude Code** 和 **Codex**。

> 说明:AI 编码工具的生态变化很快。文中的产品名是评估起点,不是背书——采用前请自行核实其当前能力与维护状态。本文档信息截至 2026 年 5 月。

---

## 先看全局:这套流程处在什么位置

你们这套九步流程,属于 2025–2026 年兴起的 **Spec-Driven Development(SDD,规格驱动开发)** 流派。它最知名的现成实现是 **GitHub Spec Kit**(`github/spec-kit`)——一个与具体 agent 无关的开源工具包,核心循环是 `specify → plan → tasks → implement`,阶段之间带审查关卡(review gate)。这几乎就是你们的第 4–7 步。

Spec Kit 的关键特性:

- **与 agent 无关**:同时支持 Claude Code、Codex、Copilot、Gemini CLI 等 30 多种集成,`specify init` 时选择 agent,它会自动配好对应的命令文件、上下文规则和目录结构。
- **每个阶段产出一份 Markdown artifact**,喂给下一阶段——和你们「每阶段都要有可见 artifact」的要求一致。
- **庞大的社区扩展生态**:90+ 社区扩展,涵盖对抗式 spec 审查、架构漂移治理、spec 遵从度评分、实现中途自动提交等。

**实操建议**:不要重造管道。你们可以把九步流程**构建在 Spec Kit 之上**(作为 preset 或一组 extension),或做成 Claude Code 插件。Spec Kit 覆盖了中间的 SPEC→Plan→Tasks→Implementation,而你们流程里它最不重视的部分——**前置的 Brainstorm / Grill Me / Prototype,以及末尾作为硬关卡的 Human QA + Acceptance**——恰恰是需要你们自己补强的地方。

### Claude Code 与 Codex 的环境差异

| 维度 | Claude Code | Codex |
|---|---|---|
| 形态 | 终端 agent,也有 IDE 扩展 | 终端 CLI + IDE 扩展 + 云端 agent |
| 持久化上下文 | `CLAUDE.md`(每次会话自动加载,压缩后重载) | `AGENTS.md`(同类机制) |
| 子代理 / 并行 | 原生 subagent、agent teams、worktree 隔离 | 云端可并行跑多个任务 |
| 自定义指令 | Skills、slash commands、hooks、plugins | 自定义提示与配置文件 |
| Spec Kit 支持 | 是 | 是 |

两个环境都能用 Spec Kit,也都支持 MCP 连接外部工具。下面每个阶段的推荐会标注它在哪个环境下怎么用。

---

## 阶段 1 — Brainstorm 头脑风暴

发散式构思不需要特殊工具,需要的是一个不受约束的模型 + 一个明确要求「多个方案」的提示。

- **Claude Code**:用 subagent / agent teams,一次性并行启动多个研究代理,各自调查问题的不同框架。比单线程串行地想要快,而且能压住「锚定第一个想法」的倾向。
- **Codex**:用云端并行任务能力同时跑多个探索方向。
- **通用**:配合白板工具(Excalidraw、tldraw、FigJam)给团队和 AI 一起发散时用。
- **Spec Kit 相关**:Spec Kit 的 `spec-driven.md` 里提到「Branching for Exploration」——从同一份 spec 生成多个面向不同优化目标(性能、可维护性、成本)的实现方案,可作为后期发散的手段。

---

## 阶段 2 — Grill Me 质询拷问

- **`grill-me` skill（本流程强制，v1.1+）**:Claude Code 内置 skill,以「不依不饶」的方式逐条审问用户的方案 / 设计,把决策树的每个分支都问到落地。触发方式:用户说「grill me」/「grill 这个设计」,或 AI 在本阶段主动调用 (`/grill-me`)。这是本流程在 Stage 2 的**默认且强制工具**——决策树的覆盖度是自由发挥的"列几个问题"做不到的。Stage 2 artifact 中需附 skill 调用记录。
- **Spec Kit `/speckit.clarify`**:交互式地识别并解决 spec 里的歧义,可指定关注领域(如「聚焦安全与性能要求」)。可与 `grill-me` 互补——`grill-me` 拷问方向 / 设计,`clarify` 收紧已成形的 spec。
- **Spec Kit `/speckit.analyze`**:跨 artifact 的一致性与缺口分析。
- **Spec Kit 对抗式审查扩展**:社区里有「lens agent」风格的扩展,并行跑多个批判性代理,专门暴露 `clarify`/`analyze` 结构上抓不到的风险——prompt injection、完整性缺口、跨 spec 漂移、静默失败等,产出结构化的发现报告。
- **Claude Code / Codex 通用模式**:红队 / 批判者 subagent——一个唯一职责就是攻击领先想法的子代理。Claude Code 可直接用 subagent 实现;Codex 可用独立任务实现。可作为 `grill-me` 之外的补充。

---

## 阶段 3 — Prototype 原型

- **Claude Code**:做快速的一次性 spike;配合 `git worktree` 把 spike 分支隔离开,不污染主工作树。
- **Codex**:云端任务适合并行跑几个不同的原型方向再对比。
- **UI 原型**:当不确定性在于「长什么样」时,用 v0、Bolt、Lovable 等快速出 UI 原型。
- **数据 / 算法 spike**:用 Jupyter notebook。
- **可交互原型**:Claude.ai 的 Artifacts 能直接产出对方可点击的交互原型。

---

## 阶段 4 — SPEC 规格(人工关卡)

- **GitHub Spec Kit `/speckit.specify`**:把一句话的功能描述转成完整、结构化的 spec,并自动管理仓库(自动功能编号、自动建分支)。
- **Spec Kit `/speckit.constitution`**:建立一个持久的「宪法」文件——项目的基本规则,后续每个命令都会引用它。这个模式本身就值得借鉴,无论你是否采用整个工具包。
- **Claude Code `CLAUDE.md`**:一个精简的顶层文件,索引到更深的 spec markdown 文件;每次会话自动加载进系统提示,上下文压缩后重新加载。常见做法是顶层当「地图」,Claude Code 按需读取子目录。
- **Codex `AGENTS.md`**:Codex 侧的等价机制,作用类似。
- **重型 PRD 模板**:如果想要更重的产品 spec 格式,可参考 BMAD Method 的 PRD 模板(它有 Analyst / PM / Architect 等虚拟团队角色)。

---

## 阶段 5 — Plan 计划

- **Spec Kit `/speckit.plan`**:接收已确认的 spec 加上你提供的技术栈 / 架构方向,产出尊重这些约束的详细技术计划。
- **Claude Code「Plan 模式」**:在做任何编辑之前,先做一次只读的规划 pass。
- **架构治理扩展**:Spec Kit 社区有持续架构治理类扩展,审查 spec、plan 和代码的架构漂移,产出结构化的重构任务与演进提案。

---

## 阶段 6 — Tasks 任务(人工关卡)

- **Spec Kit `/speckit.tasks`**:把 spec + plan 拆成一份可执行的任务清单。
- **Claude Code 原生任务追踪**:Claude Code 有内建的 task / todo 追踪,适合实时反映 Implementation 阶段的进度。
- **Codex**:云端任务本身就是工作单元,适合把任务清单逐项派发。
- **团队级 issue 追踪**:当任务需要进入团队工具时,用 Linear、GitHub Issues、Jira——通过 **MCP** 连接,让 Claude Code / Codex 能直接读写它们。

---

## 阶段 7 — Implementation 实现

- **Claude Code**:目前最成熟的终端 agent,适合按任务清单逐项推进;支持 subagent、hooks、worktree 隔离、以及对每个代理的工具权限做细粒度配置。
- **Codex**:终端 + IDE + 云端三种形态;云端 agent 适合把多个独立任务并行交出去跑。
- **Spec Kit `/speckit.implement`**:按计划执行整个任务清单。
- **实现中途提交扩展**:Spec Kit 社区有扩展会在实现过程中途提交,让你最后得到一串映射到任务的、可审查的提交,而不是一个巨大的 diff。
- **底层自动化**:无论哪个环境,Implementation 阶段都应让 agent 同时跑测试运行器、linter、类型检查器。

---

## 阶段 8 — Human QA 人工质检(人工关卡)

- **Spec Kit 实现后质量门扩展**:审查改动、自动修掉琐碎问题、为中等问题建任务、为大问题生成分析报告。
- **Staff 级代码审查 subagent**:Spec Kit 社区有「staff-engineer-level code review」扩展,对照 spec 验证实现,并检查安全、性能、测试覆盖率。Claude Code 可直接用 subagent 跑这种审查代理。
- **人工检查之下的自动化层**:测试运行器、linter、类型检查器、CI;端到端用 Playwright / Cypress;UI 状态用 Storybook。这些是必要的底座,但不替代「人去看」。

---

## 阶段 9 — Acceptance 验收

- **Spec 遵从度评分 / 复盘扩展**:Spec Kit 社区有实现后复盘扩展,带 spec 遵从度评分、漂移分析、以及「人工把关的 spec 更新」。
- **可追溯性扩展**:把需求 → 任务 → 测试映射起来的扩展,便于逐条核对验收标准。
- **一个值得知道的行业空白**:目前 Claude Code、Codex、Cursor、Windsurf、Aider 等都**没有可靠的「spec 到实现」自动验证**——没有哪个工具能自动确认实现是否匹配最初的 spec。所以一个刻意设计的 Acceptance 环节(哪怕是半自动的)是真正在填补一个空缺,值得你们重视。

---

## 推荐落地路径

1. **先评估 GitHub Spec Kit**——它直接覆盖你们的第 4–7 步,且同时支持 Claude Code 和 Codex,能省掉大量自建管道的工作。`specify init` 时分别选 Claude Code 和 Codex 各试一次。
2. **借鉴「constitution / CLAUDE.md / AGENTS.md」模式**——无论是否全量采用 Spec Kit,持久化的项目规则文件这个模式都值得用起来。
3. **用 MCP 把团队工具接进来**——issue 追踪、文档、CI,让两个环境都能读写。
4. **重点补强 Spec Kit 不覆盖的两端**——前置的 Brainstorm / Grill Me / Prototype,和末尾的 Human QA / Acceptance。这部分可以靠 Spec Kit 的对抗式审查扩展、staff 级审查扩展、复盘扩展拼起来,也可以自建(自建技能的部分见随附的 SKILL.md 技能文件)。
5. **两个环境并存时,统一 spec 作为契约**——Spec Kit 的价值正在于此:spec 稳定后,Claude Code 和 Codex 可以互换,不同的人用不同的工具,但大家都在对照同一份契约实现。提速来自对齐,而不是打字更快。
