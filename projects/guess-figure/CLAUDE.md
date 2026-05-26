# CLAUDE.md — projects/guess-figure

> 本文件是 projects/guess-figure 的**项目级 AI 指令**。Claude Code / Codex 等 agent 在本目录及子目录下工作时自动加载，规则优先级高于全局默认行为。
>
> **本文件的内容均派生自** [`../../workflow-spec/`](../../workflow-spec/) **v1.2**。workflow-spec 是单点权威源；本文件只做两件事：(1) 把权威规则的项目级约束变成「在 guess-figure 里具体怎么落」；(2) 补充 workflow-spec 不管的仓库级惯例（编码、命名、artifact 存放结构）。**任何与 workflow-spec 冲突之处以 workflow-spec 为准。**

## 1. 项目状态

🟢 **V3 上线运行中** —— V1 + 002 + 003 全部上线 [guess-figure.pages.dev](https://guess-figure.pages.dev)（最新 2026-05-26）。

- **001-guess-figure ✅ 已完成（2026-05-22 用户验收通过，15/15 AC）**
- **002-account-rate-limit ✅ 已完成（2026-05-25 用户验收通过，22/22 AC）**
  - 账号：HMAC signed UUID cookie + 滚动续期 365d + 共享 normalize lib
  - 限流：CF Pages free plan 不支持 dashboard rate limit → SPEC v1.0.1 acknowledge，用 Workers KV 计数器（IP/user 日窗口）覆盖
  - LLM 成本兜底：KV 缓存（key 含 figure_id + aliases_hash）+ 全局/单点日预算 + degraded/network_error 不消耗线索
  - 持久化：CF D1 users + games 表（预留 003 邮箱迁移字段）+ 2 KV namespaces
  - 单测:54/54 passed
- **003-clue-optimization ✅ 已完成（2026-05-26 用户验收通过，15/18 AC + 3 偏差 accept = SPEC v1.1）**
  - **3 步 LLM pipeline**:三源材料(维基全文 5K + Wikidata 6 字段 + 二十四史 Wikisource 5K)→ 强 LLM (deepseek-v3.2) 产 8-section markdown 画像 → flash-lite 产 clues (inject banlist + few-shot) → flash-lite judge (区分 d1-5/d6-7) + 自动重试 N=2
  - **题库 50→65**:31 v2 + 19 v1 旧版混合(regression 兜底)+ 15 新皇帝;5 缺失皇帝(刘协/杨广/柴荣/万历/雍正)留 006 补
  - **数据资产**:`src/lib/data/profiles/*.md` × 69 (8 sections 结构化画像);`figures.v1.json` baseline
  - **quality_check 升级 4 项**:d6/7 alias 子串(后改 d1-5 ≥3字)+ 典故 banlist + 信息密度启发式 + LLM-as-judge `--with-judge`;最终 62/65 = 95.4% 满分率
  - **prompt 调优 2 轮**:profile aliases ≤ 5 + clue 用代称避 alias + judge d6/7 整字放可疑
  - **强约束防御**:thinking model detect + clue prompt inject banlist
  - LLM 总成本 ¥2.61(< ¥10 hard cap),无新 deps
  - 单测:66/66 vitest + 39 quality_check + 18 generate_figures = 123/123 全 pass
- 公网 URL：https://guess-figure.pages.dev
- **技术栈**:SvelteKit 5 + adapter-cloudflare + CF Pages Functions + CF D1 + CF Workers KV + gemini-3.1-flash-lite(flash 用)+ **deepseek-v3.2(强 LLM 产画像)** via 云雾中转 + JSON-in-git 题库 + **profiles markdown-in-git 画像数据资产** + Python 内容生产 v2 pipeline(`generate_figures.py` 3 步)+ wrangler.toml `[vars]` env vars
- **004-turtle-soup-rag 🟡 进行中（Stage 1 起，2026-05-26）** — 新玩法海龟汤模式 + RAG 史料库（向量召回 + LLM 三态总结「是/否/无关」）
- 后续候选任务:005（自定义域名 + 品牌化）、006(补 5 缺失皇帝 + V3 题库扩 200 人 + 修 3 旧 figure quality warning)、007 候选(邮箱 magic link + 排行榜,原 004 占位顺延)
- 任务台账：见 [`README.md#任务台账`](./README.md#任务台账)

## 2. 必须遵循的工作流（强制）

本项目所有非琐碎开发任务，强制按 [`../../workflow-spec/specification.md`](../../workflow-spec/specification.md) 的九步流程执行：

```
Brainstorm → Grill Me → Prototype → SPEC ★ → Plan → Tasks ★ → Implementation → Human QA ★ → Acceptance ★
```

> ★ = 人工关卡（共 4 个：SPEC / Tasks / Human QA / Acceptance），未经用户**明确确认**不得跨越。完整规则见 [`specification.md#4-三个人工关卡`](../../workflow-spec/specification.md#4-三个人工关卡)（注：文件里实际是 4 个关卡，标题名沿用历史）。

### 阶段绑定的 skill（workflow-spec v1.2）

| 阶段 | skill | 级别 | 不调用的后果 |
|---|---|---|---|
| Stage 1 ｜ Brainstorm | `brainstorming` | 推荐 | AI 易锚定第一个想法、跳过真实选项空间 |
| Stage 2 ｜ Grill Me | `grill-me` | **强制** | 自由列问题覆盖不到决策树所有分支；本仓库 001 复盘明确：该 skill 不可用时 **必须停下报告**而非降级 |
| Stage 5 ｜ Plan | `writing-plans` | 推荐 | 缺 phase 排序 / 风险标记 / 测试策略结构 |
| Stage 7 → 8 过渡 | `verification-before-completion` | **强制** | 字面 AC 通过 / 行为 AC 破洞的盲区（v1.2 因 EmailLink bug 新增） |
| Stage 8 ｜ Human QA | `requesting-code-review` | 推荐 | 用户难快速扫到 QA 重点 |

新增 skill 绑定需同步修改 [`specification.md`](../../workflow-spec/specification.md) + [`SKILL.md`](../../workflow-spec/SKILL.md) + [`references/tooling.md`](../../workflow-spec/references/tooling.md)，不要在本文件单方面声明。

**完整规则与定义请阅读**（按重要性排序）：
- 总规范：[`../../workflow-spec/specification.md`](../../workflow-spec/specification.md)
- AI 行为细则（含 trigger / anti-trigger）：[`../../workflow-spec/SKILL.md`](../../workflow-spec/SKILL.md)
- SPEC 模板：[`../../workflow-spec/references/spec-template.md`](../../workflow-spec/references/spec-template.md)
- Plan / Tasks 模板（含 commit 前缀全表）：[`../../workflow-spec/references/plan-and-tasks.md`](../../workflow-spec/references/plan-and-tasks.md)
- 各阶段工具推荐：[`../../workflow-spec/references/tooling.md`](../../workflow-spec/references/tooling.md)

**接到任务时，第一句话不是开始干，而是宣布计划**（SKILL.md "How to run the workflow"）：哪些阶段会走、哪些会跳过、为什么、人工关卡在哪。等用户确认后再开始 Stage 1。

## 3. Artifact 存放约定（vibe-coding-lab 仓库惯例）

> 这一节是仓库级补充，workflow-spec 没强制具体的目录命名 —— 但 vibe-coding-lab 沿用此惯例。

每个任务在 [`workflow/`](./workflow/) 下建独立子目录，命名 `NNN-短名称/`（如 `001-user-login/`）：

- `NNN` 是 3 位编号，按完成或开始顺序递增（guess-figure 项目内部从 001 重新计数）
- `短名称` 用 kebab-case，≤ 4 个词

**起步**：复制 [`workflow/_template/`](./workflow/_template/) 到 `workflow/NNN-task-name/`，再按阶段填写。`_template/` 里每个阶段文件顶部已链回对应的 workflow-spec 章节与权威模板。

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

可跳过的阶段（按规模伸缩规则）：**不要删除文件**，在文件开头写「**已跳过 + 理由**」即可（符合 workflow-spec 规则三「每个阶段可见 artifact」）。

## 4. 代码组织（待第一个任务 Stage 4 SPEC 确定）

- 实际实现代码统一放 `src/`（约定，未来 SPEC 可改）
- 测试位置、构建工具、依赖管理、目录结构 —— **必须在第一个任务的 Stage 4 SPEC 的 `Constraints` 节写明**
- 在 SPEC 没定下这些之前，不要在 `src/` 里凭空创建文件（避免「SPEC 早于栈选定」失败模式，见 [`specification.md#6-要避免的常见失败模式`](../../workflow-spec/specification.md#6-要避免的常见失败模式)）

## 5. 通用约定（vibe-coding-lab 仓库惯例）

- **编码**：所有文件 UTF-8 no BOM
- **语言**：文档、代码注释、commit 信息使用**中文**（例外：`SKILL.md` 等需要保留 AI 标准 frontmatter 格式的文件保持英文）
- **commit 信息前缀**（v1.2 规范，来源 [`plan-and-tasks.md#commit-conventions-v12`](../../workflow-spec/references/plan-and-tasks.md)）：

  | 前缀 | 用于 | 例 |
  |---|---|---|
  | `task-TX:` | 新 task 首次实现 | `task-T5: 实现登录表单校验` |
  | `stage-N:` | 阶段产出 / 转换 / 确认 | `stage-4: SPEC 已确认，OQ1-4 已定` |
  | `fix(TX):` | 已完成 task 的 bug 修复（Stage 8 回路用） | `fix(T5): 登录后 redirect 死循环` |
  | `chore:` | 仓库治理 / 依赖 / 配置（非业务 task） | `chore: pin node 20.11` |
  | `docs:` | 仅文档改动 | `docs: 更新 README 任务台账` |
  | `spec(vX.Y):` | workflow-spec 自身的版本演化（**通常不发生在本项目**） | — |

- **粒度**：每个 commit 对应一个明确的 artifact 或一个 task 的可验证进度
- **分支**：默认在 `main` 直接提交；如任务涉及风险，开 `feature/NNN-task-name` 分支

## 6. AI 硬性禁止行为

> 直接对应 workflow-spec [§3 三条总规则](../../workflow-spec/specification.md#3-如何运行这套流程三条总规则) + [§4 三个人工关卡](../../workflow-spec/specification.md#4-三个人工关卡) + [§6 失败模式](../../workflow-spec/specification.md#6-要避免的常见失败模式) + [SKILL.md "Common failure modes"](../../workflow-spec/SKILL.md)。这里只列可执行的「不要做」断言，方便 AI 自查。

- ❌ 在用户确认 SPEC（Stage 4）之前编写**任何实现代码**
- ❌ 在用户确认 Tasks（Stage 6）之前进入 Implementation
- ❌ 在人工 QA（Stage 8）没实际操作过之前宣布工作"完成"
- ❌ 自我批准任何人工关卡（4 个：SPEC / Tasks / Human QA / Acceptance）
- ❌ 跳过 artifact 文件说"我想过了"—— 必须有可读的产出（哪怕一句「已跳过 + 理由」）
- ❌ 给一行 bug 修复硬凑 9 个阶段（按规模伸缩，但要明说跳了哪些和为什么）
- ❌ 在实现中途**静默修改** SPEC ——发现 SPEC 错了或不全，**停下来回 Stage 4 显式修订**并取得再确认
- ❌ 在 Stage 2 Grill Me **不调用 `grill-me` skill** 而靠自由列问题敷衍（除非整个 Stage 2 按规模伸缩规则被显式跳过并写明理由）
- ❌ 在 Stage 7 → 8 过渡 **不调用 `verification-before-completion` skill** 就声明完成（v1.2 强制；防 AC 字面通过 / 行为破洞的盲区）
- ❌ 写 AC 时只标「AI 如何验证」一栏（v1.2 要求每条 AC 必须双通道：AI 验证 + 人工验证，两边都 PASS 才 PASS）
- ❌ Stage 8 发现 bug 修完后，commit 信息复用 `task-TX:` 而不用 `fix(TX):`（v1.2 规范：诚实记录"首次实现 vs 修复回路"）
- ❌ 把 auto-mode 当作绕过人工关卡的借口（v1.2 规则四：auto-mode 仅适用于阶段内例行决策）
- ❌ 把 workflow-spec 的规则**复制**到本文件 —— 永远引用，不要复制（避免分叉腐烂）

## 7. 第一次接到任务时的开场动作

1. 读 [`README.md`](./README.md) 看项目当前状态（任务台账、技术栈是否已定）
2. 读 [`../../workflow-spec/specification.md`](../../workflow-spec/specification.md) §1–4（理念、九个阶段、三条总规则、人工关卡）
3. **评估任务规模**，向用户宣布：
   - 打算走哪些阶段
   - 打算跳过哪些阶段、为什么
   - 4 个人工关卡的位置
4. 等用户确认 → 复制 [`workflow/_template/`](./workflow/_template/) 到 `workflow/NNN-task-name/` → 开始 Stage 1
5. 在 [`README.md`](./README.md) 的「任务台账」里登记新任务

## 8. 后续维护

- **项目状态有重大变化**（确定了正式名 / 选定了技术栈 / 完成第一个任务）→ 更新本文件第 1 节与 [`README.md`](./README.md) 的任务台账
- **工作流规则有变化** → 直接修改 [`../../workflow-spec/`](../../workflow-spec/)（必要时同步 `specification.md` / `SKILL.md` / `references/`），**而不是在本文件复制或覆盖规则**
- **出现新的项目级约定**（如固定技术栈、特定测试框架）→ 在本文件追加新章节，标明"项目级补充"

---

> **本文件维护者**：随项目走，每次任务结束的 Stage 10 retrospective（如有）回看一遍是否有项目级约定需要追加。
