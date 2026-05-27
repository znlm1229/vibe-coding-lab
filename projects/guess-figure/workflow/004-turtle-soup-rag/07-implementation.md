# Stage 7 ｜ Implementation 实现

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-7--implementation-实现)
>
> **要点**：按任务清单顺序；一次一个；commit 映射到 task；**发现 SPEC 缺口立即停下回 Stage 4**，不要静默偏离。
>
> **v1.2 强制约定**：
> - 进入 Stage 8 之前**必须调 `verification-before-completion` skill** 核对每条 AC 的 AI 验证证据
> - Bug 修复回路 commit 用 **`fix(TX):`** 前缀，不要复用 `task-TX:`

---

## 进度（与 [`06-tasks.md`](./06-tasks.md) 同步）

- [ ] T1 — Cloudflare 资源与绑定契约  ｜ commit: `df2d459` + `5988d12` ｜ 代码配置完成；远端资源验证被 Cloudflare token `Invalid access token [code: 9109]` 阻塞
- [x] T2 — 本地语料构建与 chunk 校验  ｜ commit: `642dc73` + `5bed5e8` ｜ SPEC review: PASS；code-quality re-review: APPROVED
- [ ] T3 — Cloudflare 入库链路  ｜ commit: `c283155` + `0fac610` + `76f360e` + `1c70e68` ｜ 代码链路复审 PASS；真实 Cloudflare `--cloud` 写入受 token `Invalid access token [code: 9109]` 阻塞，Stage 8/9 需补远端证据
- [x] T4 — RAG 问题校验与缓存核心  ｜ commit: `1963aca` + `e8a4795` ｜ SPEC review: PASS；code-quality re-review: APPROVED
- [x] T5 — RAG 检索、rerank 与三态裁判  ｜ commit: `1598f8f` + `91da358` ｜ SPEC review: PASS；code-quality re-review: APPROVED
- [x] T6 — 海龟汤问答 API  ｜ commit: `e385921` + `d4e19b8` ｜ SPEC review: PASS；code-quality re-review: APPROVED
- [ ] T7 — 答案提交与持久化状态  ｜ commit: pending
- [x] T8 — 极短隐晦汤面数据与校验  ｜ commit: `d4064fb` + `0b4057f` ｜ SPEC/code-quality re-review: APPROVED
- [ ] T9 — 主游戏嵌入式 UI  ｜ commit: pending
- [ ] T10 — 独立 `/turtle-soup` 玩法 UI  ｜ commit: pending
- [ ] T11 — AC 验证脚本与 Stage 8 证据包  ｜ commit: pending

## 偏离 SPEC 的发现

<!-- 实现中如发现 SPEC 错 / 不全，记录在此并触发 SPEC 修订（回 Stage 4） -->

- 无

## 当前阻塞

- Cloudflare 远端资源验证暂时阻塞：`pnpm exec wrangler whoami` 返回 `Invalid access token [code: 9109]`。因此 T1 的代码配置已通过测试，但 `vectorize list`、`r2 bucket list`、远端 D1 schema 证据尚未取得；T3 可以完成 mock/可恢复入库链路，真实 `--cloud` 入库需 token 恢复后验收。

## 已运行的自动化检查

- [x] 单元测试：`pnpm test` → 11 files / 108 tests passed；`python -m unittest scripts.tests.test_turtle_cloudflare scripts.tests.test_turtle_corpus` → 15 tests passed；`python -m unittest scripts.tests.test_turtle_intro` → 9 tests passed
- [x] 集成测试：T2 sample dry-run 生成 `profile/wikipedia/wikisource` report；T1 `wrangler types` 由 worker 验证 bindings 可识别；T3 mock runner 覆盖 R2/Vectorize/D1 命令编排
- [ ] Linter
- [x] 类型检查：`pnpm run check` → 0 errors，2 个既有 warnings
- [x] 构建通过：`pnpm run build` → pass

## Stage 7 → 8 过渡前 verification-before-completion 核对（v1.2 强制）

> 调 `verification-before-completion` skill 之后填。每条 AI 验证通道的 AC 都要有验证命令 + 输出证据。
>
> 这一步是为了挡住「AI 自报 PASS 但实际没跑过验证」的盲区。

| AC | AI 验证命令 | 输出证据 | PASS? |
|---|---|---|---|
| AC1 | <例：`curl https://...`> | <粘贴 HTTP 200> | ✅/❌ |
| AC2 | ... | | |

## Stage 8 入场摘要预备

> 完成本阶段前先准备好给 Stage 8 的"质检就绪摘要"草稿（建议用 `requesting-code-review` skill 的结构）：改了什么、入口在哪、自动化通过情况、建议人工重点测什么。
