# Stage 7 - Implementation 实现

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-7--implementation-实现)
>
> 要点：按任务清单顺序；一次一个；commit 映射到 task；发现 SPEC 缺口立即回 Stage 4，不静默偏离。
>
> v1.2 强制约定：进入 Stage 8 前必须调用 `verification-before-completion` skill 核对每条 AC 的 AI 验证证据。

---

## 进度

- [ ] T1 - Cloudflare 资源与绑定契约 - commit: `df2d459` + `5988d12`。代码配置完成；远端资源验证被 Cloudflare 认证阻塞，当前 `pnpm exec wrangler whoami` 输出 `Failed to fetch auth token: 400 Bad Request` / `Not logged in`，背景中的已知输出为 `Invalid access token [code: 9109]`。
- [x] T2 - 本地语料构建与 chunk 校验 - commit: `642dc73` + `5bed5e8`。SPEC review PASS；code-quality re-review APPROVED。
- [ ] T3 - Cloudflare 入库链路 - commit: `c283155` + `0fac610` + `76f360e` + `1c70e68`。代码链路复审 PASS；真实 `--cloud` 写入仍被 Cloudflare 认证阻塞，Stage 8/9 需要补远端证据。
- [x] T4 - RAG 问题校验与缓存核心 - commit: `1963aca` + `e8a4795`。SPEC review PASS；code-quality re-review APPROVED。
- [x] T5 - RAG 检索、rerank 与三态裁判 - commit: `1598f8f` + `91da358`。SPEC review PASS；code-quality re-review APPROVED。
- [x] T6 - 海龟汤问答 API - commit: `e385921` + `d4e19b8`。SPEC review PASS；code-quality re-review APPROVED。
- [x] T7 - 答案提交与持久化状态 - commit: `b52508d` + `e21bc26` + `462e540`。SPEC re-review PASS；code-quality second re-review APPROVED。
- [x] T8 - 极短隐晦汤面数据与校验 - commit: `d4064fb` + `0b4057f`。SPEC/code-quality re-review APPROVED。
- [x] T9 - 主游戏嵌入式 UI - commit: `eefd16a` + `e344533`。SPEC re-review PASS；code-quality re-review APPROVED。
- [x] T10 - 独立 `/turtle-soup` 玩法 UI - commit: `b378644` + `e344533`。SPEC re-review PASS；code-quality re-review APPROVED。
- [x] T11 - AC 验证脚本与 Stage 8 证据包 - commit: pending。

## 偏离 SPEC 的发现

- 无。T11 只补 004 AC 验证脚本和 Stage 8 证据包，不修改业务行为。

## 当前阻塞

- Cloudflare 真实远端验收仍阻塞：`pnpm exec wrangler whoami` 失败。当前实际输出为 `Failed to fetch auth token: 400 Bad Request` / `Not logged in`；任务背景中的已知输出为 `Invalid access token [code: 9109]`。两者都表示当前认证不可用，因此 AC1/T1 和 AC2/T3 的真实远端资源、R2/Vectorize/D1 写入证据不得标 PASS。
- AC4 自动化仅覆盖 sample 的 `profile`、`wikipedia`、`wikisource` 三类 source type；完整 AC4 还需要全量二十四史 processed/failed 统计报告确认，当前不得标完整 PASS。
- Stage 8 是人工关卡，浏览器人工主路径尚未由用户实测；AC20 保持 MANUAL。

## 已运行的自动化检查

- `C:\Program Files\Git\bin\bash.exe scripts/verify_ac.sh`：exit code `2`；summary `PASS=16 FAIL=0 BLOCKED=3 MANUAL=1 SKIP=0`。PowerShell 中 `bash` 命令不存在，已改用 Git Bash。
- `pnpm test`：17 test files passed，147 tests passed。
- `pnpm run check`：0 errors，2 existing warnings：
  - `src/routes/play/+page.svelte:310` unused CSS selector `.result small`
  - `tsconfig.json:1` cannot find type definition file for `node`
- `pnpm run build`：pass；构建期间仍报告同一个既有 `.result small` unused CSS warning。
- `python -m unittest scripts.tests.test_turtle_cloudflare scripts.tests.test_turtle_corpus scripts.tests.test_turtle_intro`：Ran 24 tests，OK。

## Stage 7 -> 8 verification-before-completion 核对

已使用 `verification-before-completion` skill。下表只记录 AI 验证通道；人工通道见 `08-qa.md`。

| AC | AI 验证命令 | 输出证据 | 状态 |
|---|---|---|---|
| AC1 | `pnpm exec wrangler whoami`; 恢复认证后继续跑 `pnpm exec wrangler vectorize list`; `pnpm exec wrangler r2 bucket list`; `pnpm exec wrangler d1 execute guess-figure-db --remote --command "SELECT name FROM sqlite_master WHERE name LIKE 'turtle_%';"` | 当前 `whoami` 为 Cloudflare 认证失败：`Failed to fetch auth token: 400 Bad Request` / `Not logged in`；背景已知 blocker 为 `Invalid access token [code: 9109]`。恢复认证后脚本只自动检查资源存在和 D1 manifest 表，Vectorize 1024/cosine 仍需 Dashboard/manual 取证。 | BLOCKED |
| AC2 | `python scripts/build_turtle_corpus.py --sample --mock-embedding --output <repo外临时目录>`；恢复认证后跑 `python scripts/build_turtle_corpus.py --sample --cloud --mock-embedding --output <repo外临时目录>` | 本地 dry-run 生成 `corpus_version`、`index_version`、`build-report.json` 和 `chunks.jsonl`；真实 R2/Vectorize/D1 写入因认证不可用未跑通。恢复认证后还需 report/stdout 证明 version、source counts、R2 object keys、Vectorize/D1/cloud summary。 | BLOCKED |
| AC3 | `git ls-files | rg '(^|/)(raw|normalized|chunks|wikisource|r2-cache).*\.(jsonl|txt|md)$|(^|/)corpus/|r2-cache'` | `scripts/verify_ac.sh` 报 `git 未跟踪全量原始/清洗语料、chunk JSONL 或 R2 cache`。 | PASS |
| AC4 | `python scripts/build_turtle_corpus.py --sample --mock-embedding --output <repo外临时目录>` 后检查 `build-report.json` | 自动化仅覆盖 sample source type coverage：`profile`、`wikipedia`、`wikisource` 三类来源；完整 AC4 待全量二十四史 processed/failed 统计报告确认。 | BLOCKED |
| AC5 | `python -m unittest scripts.tests.test_turtle_corpus` | Python corpus 测试覆盖 chunk 长度、overlap、metadata <10KiB 与来源追溯；相关总 Python suite 24 passed。 | PASS |
| AC6 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts` | RAG 单测覆盖 query expansion、目标人物姓名/aliases 注入与跨人物污染约束。 | PASS |
| AC7 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts src/routes/api/turtle/question/server.test.ts` | RAG/API 单测覆盖可见回答枚举只允许“是/否/无关”。 | PASS |
| AC8 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts` | 证据不足 fixture 返回“无关”，不猜成“否”。 | PASS |
| AC9 | `pnpm exec vitest run src/lib/server/turtle-question.test.ts src/routes/api/turtle/question/server.test.ts` | invalid 不扣次数、不进入 RAG/LLM。 | PASS |
| AC10 | `pnpm exec vitest run src/lib/server/turtle-cache.test.ts src/routes/api/turtle/question/server.test.ts` | 缓存 key 含 figure/question/index/prompt version；TTL 30 天；hit 不查 Vectorize/LLM。 | PASS |
| AC11 | `pnpm exec vitest run src/lib/game-state.svelte.test.ts` | 主游戏状态测试覆盖第 1-5 条不显示入口、第 6 条后显示入口。 | PASS |
| AC12 | `pnpm exec vitest run src/lib/game-state.svelte.test.ts src/routes/api/game/finish/server.test.ts` | 嵌入式海龟汤最多 5 问；用后 finish payload / 持久化为 0 分。 | PASS |
| AC13 | `pnpm exec vitest run src/lib/turtle-soup-state.test.ts`; `python -m unittest scripts.tests.test_turtle_intro` | 首屏 round 只下发 `turtle_intro`，不暴露人物答案材料；65 人 intro 校验通过。 | PASS |
| AC14 | `pnpm exec vitest run src/lib/turtle-soup-state.test.ts src/routes/api/turtle/answer/server.test.ts` | 独立模式 15 问、3 次答案机会；错答只扣答案次数，不扣提问次数。 | PASS |
| AC15 | `pnpm exec vitest run src/routes/api/turtle/answer/server.test.ts` | 答案 API 只判目标人物命中，不读取 RAG 证据或要求解释故事。 | PASS |
| AC16 | `pnpm exec vitest run src/lib/server/turtle-question.test.ts` | 直接猜姓名/别名类 yes/no 问题不被 invalid 拦截。 | PASS |
| AC17 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts src/routes/api/turtle/question/server.test.ts` | Workers AI/Vectorize/预算失败走 degraded；不误记为“否”或错误答案。 | PASS |
| AC18 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts` | 关羽“后世尊为武圣”维基 fixture 回归为“是”。 | PASS |
| AC19 | `pnpm test`; `pnpm run check`; `pnpm run build`; `python -m unittest scripts.tests.test_turtle_cloudflare scripts.tests.test_turtle_corpus scripts.tests.test_turtle_intro` | `pnpm test` 147 passed；`check` 0 errors/2 existing warnings；`build` pass；Python 24 passed。 | PASS |
| AC20 | `scripts/verify_ac.sh` 只生成人工路径提示；浏览器主路径需 Stage 8 真人实测 | 脚本标 `MANUAL`，指向 `08-qa.md`。 | MANUAL |

## Stage 8 入场摘要预备

T11 已把旧 002 AC 验证脚本替换为 004 专用脚本。影响：`scripts/verify_ac.sh` 现在验证 `workflow/004-turtle-soup-rag` 的 AC1-AC20，不再假装旧 002 AC 是当前任务。Stage 8 需要用户重点补齐 Cloudflare Dashboard 远端资源截图/记录、真实 R2/Vectorize/D1 入库证据，以及两条浏览器主路径实测。

阶段尚未满足 committed 条件：T11 改动尚未提交，Stage 8 人工关卡也尚未由用户确认。
