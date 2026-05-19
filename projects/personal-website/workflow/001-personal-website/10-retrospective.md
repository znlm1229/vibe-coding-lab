# Stage 10 ｜ Retrospective 复盘

> v1.1 工作流规范里没有这个阶段（计划在 v1.2 / v2.0 加入）。本任务 001 完成后，用户提出做这次复盘以喂给工作流自身的下一版。
>
> **要点**：诚实记录赢点 + 摩擦点 + 意外发现 + 给下任务的提醒。复盘的产出比"任务完成"本身更长尾。

---

## 复盘对象

任务 **001-personal-website**（2026-05-19 完成）。详细见同目录 [01–09 artifact](.)。

## 1. 工作流验证的 7 个赢点

| # | 赢点 | 关键证据 |
|---|---|---|
| 1 | **人工关卡真的拦住了 bug** | Stage 8 抓到 EmailLink 漏洞。AI grep AC10「邮箱不明文」显示通过，但 UI 完全坏。**没有 Stage 8 这个硬停，bug 会以"已验收"假阳性带上线**。这是工作流第一次证明它价值的关键时刻 |
| 2 | **artifact 让推理可见** | 用户能读到 brainstorm 5 个方向、grill 10 轮拷问、SPEC 13 条 AC，而不是被迫信任 AI 黑箱 |
| 3 | **SPEC 修订保持显式** | v1.0.1（路径）+ v1.0.2（URL）两次 patch 都进了修订日志，无静默漂移 |
| 4 | **grill-me 拷问深度可观** | Q3 用户主动从「低频维护」翻成「长期高频 + 加博客」—— AI 自由列问题不会拷问到这种自我矛盾的回流 |
| 5 | **per-task commit 映射** | ~30 个 commit 可逐条 review / bisect / revert |
| 6 | **自举验证** | 用九步工作流端到端建出一个项目，证明流程本身能工业化运行 |
| 7 | **按规模伸缩落地** | Stage 3 Prototype 跳过有理有据，没硬凑 |

## 2. 5 个明显的摩擦点

| # | 摩擦 | 现象 | 改进方向 |
|---|---|---|---|
| 1 | **AC 字面 vs 行为脱节** | AC10「HTML 不含明文邮箱」字面通过 ≠ 用户能用。AI 自动验证存在系统性盲区 | v1.2 改良：每条 AC 显式标「AI 验证 / 人工验证」两通道 |
| 2 | **SPEC 早于 starter 现实** | SPEC 写 `/blog`，starter 用 `/posts` → 必须 patch | v2.0 考虑：Stage 3.5 Tech Selection（在 SPEC 前定栈）|
| 3 | **CF 平台外部依赖卡 2 次** | T17 用户先误选 Worker、又遇 pnpm 配置不兼容，各来回一次。AI 无法预演 CF 部署 | 给「外部平台对接 task」单独定 SOP；本次留进 references/tooling.md |
| 4 | **OQ 机制处理「品味决策」较弱** | OQ3/OQ4 用户采纳 AI 推荐 → AI 起草文案 → 最后还得自己改 | v1.2 改良：OQ 加「类型」字段标 technical / taste，taste 类默认警告"AI 起草仅占位" |
| 5 | **auto mode 与人工关卡内在冲突** | auto mode 说「减少打断」，工作流说「每关卡停」 | v1.2 文档化「auto 仅对例行决策应用，人工关卡始终硬停」|

## 3. 1 个意外发现

**Astro 6 + ClientRouter + MDX import 的组合让组件 `<script>` 被 tree-shake**。这种「框架级隐性陷阱」靠 SPEC 阶段几乎不可能预知，只有 Stage 8 真人在生产页面点击时才暴露。

**强化的原则**：自动化验证 ≠ 验收。任何依赖客户端 JS 行为的功能（mailto 触发、暗黑切换、表单提交、动效等），SPEC 写 AC 时必须把"行为发生"写进去，AI 验证之外强制有人工验证通道。

## 4. SPEC patch 的成本核算

本任务总共 2 次 SPEC patch + 1 次 Stage 8 回路 fix：

| 触发 | 阶段 | 工作量 | 性质 |
|---|---|---|---|
| starter 路径约定不符 | T2 期间 | 5 处文本替换 + 1 commit | 命名层、无行为影响 |
| CF 项目名选定 | T17 期间 | 1 个 URL 替换 + 1 commit | URL 层、无行为影响 |
| EmailLink 客户端 script 没 bundle | Stage 8 期间 | 1 次组件重写 + 1 commit | 行为层 bug，AI 漏判 AC10 |

**结论**：前 2 个 patch 是「SPEC 提前于现实」的合理成本，属于工作流接受范围。第 3 个是「AI 自检盲区」的损失，属于工作流要进化的部分。

## 5. 给下次任务（002 / 003）的 reminder

1. **任何前端动态行为 AC**（点击触发、状态切换、JS 解码等）必须有「在浏览器里实际操作过」的人工验证步骤，不能只 grep HTML
2. **starter / 框架选型应优先于 SPEC 细节**，或接受 SPEC 会有命名层 patch
3. **OQ 表格里把 taste 类问题标记出来**，让用户知道 AI 给的只是占位
4. **CF Pages 项目类型必须是 Pages（不是 Worker）**，否则强塞 Cloudflare adapter 破 SSG
5. **pnpm 版本固定靠 `packageManager` 字段**，跨环境兼容
6. **Astro 6 组件里的 `<script>`** 在 .mdx import + ClientRouter 同时存在时，要 `is:inline` + 监听 `astro:page-load`
7. **`pnpm approve-builds` 会生成不兼容 pnpm 10 的 workspace.yaml**，要么不用要么 packageManager pin 到 pnpm 10
8. **Stage 8 入场摘要应该标准化模板**，避免临场拼凑
9. **bug 回路的 commit 前缀用 `fix(TX):`**，区分原 task vs 修复

## 6. 给 workflow-spec 自身的反推

本次复盘的全部内容反推为 workflow-spec v1.2 的输入：

- **v1.2 加 superpowers skill 绑定**：Stage 1 `brainstorming`、Stage 5 `writing-plans`、Stage 7→8 过渡 `verification-before-completion`、Stage 8 `requesting-code-review`
- **v1.2 改良 AC 写法约定**：模板加「AI 验证 / 人工验证」两列
- **v1.2 加 OQ 类型字段**：technical / taste
- **v1.2 加 bug 回路 commit 前缀**：`fix(TX):` 规范
- **v1.2 加 Stage 8 入场摘要标准模板**
- **v2.0 考虑结构性扩展**：Stage 3.5 Tech Selection、Stage 10 Retrospective 正式入规范
- **v1.2 文档化 auto-mode 与人工关卡的边界**：auto 仅适用于例行决策

具体见同次提交的 workflow-spec v1.2 patch。
